"""
HeatIQ Mortality Risk Index — Service Layer
Data Contract: v0.1

Provides the public boundary for processing mortality risk.
Handles batch/multi-ward collection processing and matching inputs by area_id.
"""

from typing import Union, List, Sequence, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

from backend.thermalengine import ThermalOutput
from .schemas import InfoPoolRecord, ResourcePoolRecord, MortalityOutput, MortalityInputValidationError
from .calculator import BaseMortalityRiskCalculator, RuleBasedMortalityRiskCalculator


class MortalityService:
    """
    Coordinates matching thermal, info, and resource records for wards,
    and invoking the configured MortalityRiskCalculator.
    """

    def __init__(self, calculator: Optional[BaseMortalityRiskCalculator] = None):
        self._calculator = calculator or RuleBasedMortalityRiskCalculator()

    def _parse_info_records(
        self,
        info_data: Union[Sequence[Union[InfoPoolRecord, Dict[str, Any]]], None]
    ) -> Dict[str, InfoPoolRecord]:
        """Convert a list of InfoPool records into a dict keyed by area_id."""
        if not info_data:
            return {}
        info_map = {}
        for item in info_data:
            if isinstance(item, dict):
                item = InfoPoolRecord.from_dict(item)
            if not isinstance(item, InfoPoolRecord):
                raise MortalityInputValidationError(f"Invalid info record type: {type(item)}")
            info_map[item.area_id] = item
        return info_map

    def _parse_resource_records(
        self,
        resource_data: Union[Sequence[Union[ResourcePoolRecord, Dict[str, Any]]], None]
    ) -> Dict[str, ResourcePoolRecord]:
        """Convert a list of ResourcePool records into a dict keyed by area_id."""
        if not resource_data:
            return {}
        res_map = {}
        for item in resource_data:
            if isinstance(item, dict):
                item = ResourcePoolRecord.from_dict(item)
            if not isinstance(item, ResourcePoolRecord):
                raise MortalityInputValidationError(f"Invalid resource record type: {type(item)}")
            res_map[item.area_id] = item
        return res_map

    def calculate_mortality_risk(
        self,
        thermal: ThermalOutput,
        info: Union[InfoPoolRecord, Dict[str, Any], None] = None,
        resource: Union[ResourcePoolRecord, Dict[str, Any], None] = None
    ) -> MortalityOutput:
        """Process mortality risk for a single ward."""
        if isinstance(info, dict):
            info = InfoPoolRecord.from_dict(info)
        if isinstance(resource, dict):
            resource = ResourcePoolRecord.from_dict(resource)
            
        return self._calculator.calculate(thermal, info, resource)

    def calculate_mortality_risk_batch(
        self,
        thermal_outputs: Sequence[ThermalOutput],
        info_records: Optional[Sequence[Dict[str, Any]]],
        resource_records: Optional[Sequence[Dict[str, Any]]],
        max_workers: int = 4,
        allow_partial_failures: bool = True
    ) -> List[MortalityOutput]:
        """
        Process a batch of wards concurrently using ThreadPoolExecutor.
        Matches thermal, info, and resource records internally by area_id.
        Preserves the input order of thermal_outputs.
        """
        from concurrent.futures import ThreadPoolExecutor
        
        info_map = self._parse_info_records(info_records)
        res_map = self._parse_resource_records(resource_records)

        # Detect duplicates in the primary driver (thermal_outputs)
        seen_area_ids = set()
        duplicates = set()
        for t in thermal_outputs:
            if hasattr(t, "area_id"):
                if t.area_id in seen_area_ids:
                    duplicates.add(t.area_id)
                seen_area_ids.add(t.area_id)

        def _process_single(thermal: Any) -> MortalityOutput:
            if not isinstance(thermal, ThermalOutput):
                if not allow_partial_failures:
                    raise MortalityInputValidationError(f"Expected ThermalOutput, got {type(thermal)}")
                return MortalityOutput(
                    area_id="UNKNOWN",
                    timestamp="",
                    calculation_status="INSUFFICIENT_DATA",
                    method_version="INVALID_INPUT_TYPE"
                )

            if thermal.area_id in duplicates:
                if not allow_partial_failures:
                    raise MortalityInputValidationError(f"Duplicate area_id found: {thermal.area_id}")
                return MortalityOutput(
                    area_id=thermal.area_id,
                    timestamp=thermal.timestamp,
                    calculation_status="INSUFFICIENT_DATA",
                    method_version="DUPLICATE_AREA_ID_IN_BATCH"
                )
                
            try:
                info = info_map.get(thermal.area_id)
                res = res_map.get(thermal.area_id)
                return self._calculator.calculate(thermal, info, res)
            except Exception as e:
                logger.error(f"stage=Mortality area_id={thermal.area_id} reason=CALCULATION_ERROR details='{str(e)}'")
                if not allow_partial_failures:
                    raise e
                return MortalityOutput(
                    area_id=thermal.area_id,
                    timestamp=thermal.timestamp,
                    calculation_status="INSUFFICIENT_DATA",
                    method_version=f"BATCH_PROCESSING_ERROR: {str(e)}"
                )

        # Execute concurrently while preserving order
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(_process_single, thermal_outputs))

        return results


# ── Global Default Instance & Convenience Functions ─────────────────────────

_default_service = MortalityService()


def calculate_mortality_risk(
    thermal: ThermalOutput,
    info: Union[InfoPoolRecord, Dict[str, Any], None] = None,
    resource: Union[ResourcePoolRecord, Dict[str, Any], None] = None
) -> MortalityOutput:
    """Calculate mortality risk for a single ward."""
    return _default_service.calculate_mortality_risk(thermal, info, resource)


def calculate_mortality_risk_batch(
    thermal_outputs: Sequence[ThermalOutput],
    info_records: Union[Sequence[Union[InfoPoolRecord, Dict[str, Any]]], None] = None,
    resource_records: Union[Sequence[Union[ResourcePoolRecord, Dict[str, Any]]], None] = None,
    max_workers: Optional[int] = 4,
    allow_partial_failures: bool = True
) -> List[MortalityOutput]:
    """Calculate mortality risk for multiple wards concurrently, matching by area_id."""
    return _default_service.calculate_mortality_risk_batch(
        thermal_outputs, info_records, resource_records, max_workers, allow_partial_failures
    )
