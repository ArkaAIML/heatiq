"""
HeatIQ Thermal Engine — Primary Service and Boundary Layer
Data Contract: v0.1  |  Component: Data / Backend / Thermal Engine (§4.1)

Provides a clean, contract-compliant entry point for all other backend modules.
Isolates callers from internal calculation engine classes and supports single & multi-ward batch processing.
"""

from __future__ import annotations

import json
import logging
from typing import Union, Dict, Any, List, Sequence, Optional

logger = logging.getLogger(__name__)

from .schemas import ThermalInput, ThermalOutput, ThermalInputValidationError
from .htsi import HTSIEngine, HTSIInput, HTSIDerived


class ThermalEngineService:
    """
    Primary service boundary for the Thermal Engine.
    
    Responsibilities:
    1. Input Structuring: Accepts ThermalInput, dict, JSON string, or kwargs and validates schema.
    2. Adapter: Maps canonical contract input to internal computation representations.
    3. Computation: Executes verified physical algorithms (WBGT, UTCI, Heat Index, HTSI).
    4. Output Structuring: Maps internal computation results to canonical ThermalOutput.
    5. Multi-Ward Gate: Iterates across area/ward records with fault tolerance & order preservation.
    """

    def __init__(self, htsi_engine: Optional[HTSIEngine] = None):
        self._engine = htsi_engine or HTSIEngine()

    def _structure_input(
        self,
        input_data: Union[ThermalInput, Dict[str, Any], str, None] = None,
        **kwargs: Any
    ) -> ThermalInput:
        """
        Coerce and validate arbitrary single caller input into a canonical ThermalInput instance.
        """
        if isinstance(input_data, ThermalInput):
            input_data.validate()
            return input_data

        if isinstance(input_data, str):
            return ThermalInput.from_json(input_data)

        if isinstance(input_data, dict):
            merged = {**input_data, **kwargs}
            return ThermalInput.from_dict(merged)

        if kwargs:
            return ThermalInput.from_dict(kwargs)

        raise ThermalInputValidationError("No thermal input data provided")

    def _map_to_internal_input(self, canonical: ThermalInput) -> HTSIInput:
        """
        Map canonical ThermalInput to internal calculation record HTSIInput.
        """
        return HTSIInput(
            area_id=canonical.area_id,
            timestamp=canonical.timestamp,
            temperature_c=canonical.temperature_c,
            relative_humidity_pct=canonical.relative_humidity_pct,
            wind_speed_ms=canonical.wind_speed_ms,
            solar_radiation_wm2=canonical.solar_radiation_wm2,
            latitude=canonical.latitude,
            longitude=canonical.longitude,
            dew_point_c=canonical.dew_point_c,
            population=canonical.population,
            elderly_fraction=canonical.elderly_fraction,
        )

    def _structure_output(self, internal_result: HTSIDerived) -> ThermalOutput:
        """
        Map internal calculation result HTSIDerived to canonical ThermalOutput.
        """
        return ThermalOutput(
            area_id=internal_result.area_id,
            timestamp=internal_result.timestamp,
            heat_index_c=internal_result.heat_index_c,
            utci_c=internal_result.utci_c,
            wbgt_c=internal_result.wbgt_c,
            htsi=internal_result.htsi,
            htsi_category=internal_result.htsi_category,
            hi_score=internal_result.hi_score,
            wbgt_score=internal_result.wbgt_score,
            utci_score=internal_result.utci_score,
            calculation_status=internal_result.calculation_status,
            weights_used=internal_result.weights_used,
            indices_computed=internal_result.indices_computed,
            indices_skipped=internal_result.indices_skipped,
            method_version=internal_result.method_version,
        )

    def calculate(
        self,
        input_data: Union[ThermalInput, Dict[str, Any], str, None] = None,
        **kwargs: Any
    ) -> ThermalOutput:
        """
        Process single structured environmental input and return canonical thermal outputs.

        Parameters
        ----------
        input_data : ThermalInput, dict, or JSON string (optional if kwargs provided)
        **kwargs : Individual field values (e.g., temperature_c=35.0, relative_humidity_pct=60.0, ...)

        Returns
        -------
        ThermalOutput
            Canonical structured output containing WBGT, UTCI, Heat Index, HTSI, and metadata.
        """
        # 1. Structure and validate incoming input
        canonical_input = self._structure_input(input_data, **kwargs)

        # 2. Map to internal calculation model
        internal_input = self._map_to_internal_input(canonical_input)

        # 3. Execute calculations
        internal_result = self._engine.calculate(internal_input)

        # 4. Structure output to canonical data contract
        return self._structure_output(internal_result)

    def _extract_identification_fallback(
        self,
        record: Any
    ) -> tuple[str, str]:
        """Helper to safely extract area_id and timestamp from a failed record for traceability."""
        area_id = "UNKNOWN"
        timestamp = ""
        if isinstance(record, ThermalInput):
            area_id = getattr(record, "area_id", "UNKNOWN") or "UNKNOWN"
            timestamp = getattr(record, "timestamp", "") or ""
        elif isinstance(record, dict):
            area_id = str(record.get("area_id", "UNKNOWN") or "UNKNOWN")
            timestamp = str(record.get("timestamp", "") or "")
        elif isinstance(record, str):
            try:
                parsed = json.loads(record)
                if isinstance(parsed, dict):
                    area_id = str(parsed.get("area_id", "UNKNOWN") or "UNKNOWN")
                    timestamp = str(parsed.get("timestamp", "") or "")
            except Exception:
                pass
        return area_id, timestamp

    def calculate_batch(
        self,
        records: Union[Sequence[Union[ThermalInput, Dict[str, Any], str]], str],
        allow_partial_failures: bool = True,
    ) -> List[ThermalOutput]:
        """
        Process a collection of structured environmental inputs (e.g., multiple wards/areas).

        Parameters
        ----------
        records : Sequence of ThermalInput / dict / JSON string, or a single JSON string array
        allow_partial_failures : bool, default True
            If True, invalid ward records produce an INSUFFICIENT_DATA ThermalOutput record
            preserving ward identity (§25) while allowing all valid wards to be computed.
            If False, any invalid record raises ThermalInputValidationError (strict mode).

        Returns
        -------
        List[ThermalOutput]
            A list of ThermalOutput items preserving input order and ward identity.
        """
        # Handle string input representing JSON array
        if isinstance(records, str):
            try:
                parsed = json.loads(records)
                if isinstance(parsed, list):
                    records = parsed
                else:
                    raise ThermalInputValidationError(f"Expected a JSON list of records, got {type(parsed).__name__}")
            except Exception as exc:
                if not allow_partial_failures:
                    raise ThermalInputValidationError(f"Malformed JSON batch input: {exc}")
                return [
                    ThermalOutput(
                        area_id="UNKNOWN",
                        timestamp="",
                        heat_index_c=None,
                        utci_c=None,
                        wbgt_c=None,
                        htsi=None,
                        htsi_category=None,
                        calculation_status="INSUFFICIENT_DATA",
                        indices_computed=[],
                        indices_skipped=["HI", "WBGT", "UTCI"],
                        method_version=f"FAILED-VALIDATION: {exc}",
                    )
                ]

        if not records:
            return []

        outputs: List[ThermalOutput] = []

        for record in records:
            if allow_partial_failures:
                try:
                    out = self.calculate(record)
                    outputs.append(out)
                except Exception as exc:
                    area_id, timestamp = self._extract_identification_fallback(record)
                    logger.error(f"stage=Thermal area_id={area_id} reason=CALCULATION_ERROR details='{str(exc)}'")
                    failed_out = ThermalOutput(
                        area_id=area_id,
                        timestamp=timestamp,
                        heat_index_c=None,
                        utci_c=None,
                        wbgt_c=None,
                        htsi=None,
                        htsi_category=None,
                        calculation_status="INSUFFICIENT_DATA",
                        indices_computed=[],
                        indices_skipped=["HI", "WBGT", "UTCI"],
                        method_version=f"FAILED-VALIDATION: {exc}",
                    )
                    outputs.append(failed_out)
            else:
                outputs.append(self.calculate(record))

        return outputs


# ── Global default service instance and convenience functions ───────────────

_default_service = ThermalEngineService()


def calculate_thermal_indices(
    input_data: Union[ThermalInput, Dict[str, Any], Sequence[Union[ThermalInput, Dict[str, Any], str]], str, None] = None,
    allow_partial_failures: bool = True,
    **kwargs: Any
) -> Union[ThermalOutput, List[ThermalOutput]]:
    """
    Primary public entry point for calculating thermal indices and human thermal stress.

    Supports both single-record and multi-ward collection operations:
    - If passed a single record / dict / kwargs -> returns ThermalOutput
    - If passed a list / tuple / JSON array -> returns List[ThermalOutput]

    Parameters
    ----------
    input_data : ThermalInput, dict, list/tuple of records, or JSON string
    allow_partial_failures : bool, default True (for batch processing)
    **kwargs : Keyword arguments for single-record calculation

    Returns
    -------
    ThermalOutput or List[ThermalOutput]
    """
    # 1. Multi-record collection (list or tuple)
    if isinstance(input_data, (list, tuple)):
        return _default_service.calculate_batch(input_data, allow_partial_failures=allow_partial_failures)

    # 2. JSON array string
    if isinstance(input_data, str) and input_data.strip().startswith("["):
        return _default_service.calculate_batch(input_data, allow_partial_failures=allow_partial_failures)

    # 3. Single record
    return _default_service.calculate(input_data, **kwargs)


def calculate_thermal_indices_batch(
    records: Union[Sequence[Union[ThermalInput, Dict[str, Any], str]], str],
    allow_partial_failures: bool = True,
) -> List[ThermalOutput]:
    """
    Explicit multi-ward batch calculation function.

    Parameters
    ----------
    records : List/Sequence of ThermalInput records, dicts, or JSON string array
    allow_partial_failures : bool, default True

    Returns
    -------
    List[ThermalOutput]
    """
    return _default_service.calculate_batch(records, allow_partial_failures=allow_partial_failures)
