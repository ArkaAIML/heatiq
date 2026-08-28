"""
HeatIQ Thermal Engine — Heat Index Module
Data Contract: v0.1  |  Component: Data / Backend / Thermal Engine (§4.1)
Branch: feature/thermal-indices

Output schema (§9):
    heat_index_c : float | DERIVED | °C

Formula / Library (§4.1, §9):
    NOAA National Weather Service (NWS) Rothfusz regression (1990).
    Reference: Rothfusz, L.P., "The heat index equation", NWS Tech. Attach. SR 90-23.
    URL: https://www.weather.gov/ama/heatindex

Required inputs (§8):
    temperature_c (float, °C)  — REQUIRED
    relative_humidity_pct (float, %) — REQUIRED

Assumptions / Applicability (§9):
    - Standard atmospheric pressure (~1013.25 hPa).
    - Light wind / indoor or shaded approximation (radient load handled by WBGT, not HI).
    - Adult metabolic rate; not corrected for heavy exertion.
    - Effective range: air temperature >= ~26.7 °C (80 °F) with adjustments below.
    - Relative humidity 0–100 %.
    - No direct solar-radiation correction applied.

Units (§26):
    Internal: temperature in °C; humidity in %.
    Calcuation uses Fahrenheit-space Rothfusz internally, then converts back to °C.

Fallback (§9, §25):
    If required inputs missing or out of range -> do NOT calculate.
    Return INSUFFICIENT_DATA / raise validation error rather than fabricate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Literal, Union
import numpy as np


class HeatIndexValidationError(Exception):
    """Raised when canonical input fails §27 validation."""
    pass


@dataclass
class CanonicalThermalInput:
    """
    Canonical observation per HeatIQ Contract §5 / §8 / §28.
    One record = one geographic area at one timestamp.
    """
    area_id: str
    timestamp: str  # ISO-8601 with timezone or documented UTC (§7)

    # Required environmental (§8)
    temperature_c: float
    relative_humidity_pct: float

    # Required identification (§7)
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Optional / provisional (§8, §10–12)
    wind_speed_ms: Optional[float] = None
    solar_radiation_wm2: Optional[float] = None
    dew_point_c: Optional[float] = None
    cloud_cover_pct: Optional[float] = None
    precipitation_mm: Optional[float] = None

    # Optional contextual (§10–12)
    population: Optional[int] = None
    elderly_fraction: Optional[float] = None


@dataclass
class HeatIndexDerived:
    """
    Derived thermal-index schema per §9.
    """
    area_id: str
    timestamp: str
    heat_index_c: Optional[float]
    # Status for missing-data traceability (§25)
    calculation_status: Literal["COMPUTED", "INSUFFICIENT_DATA", "OUT_OF_RANGE"] = "COMPUTED"
    # Documentation of method for explainability (§29)
    method_version: str = "NWS-Rothfusz-1990-v1"


class HeatIndexEngine:
    """
    Thermal Calculation Engine component (§4.1).
    Produces heat_index_c from required environmental inputs.
    """

    # Rothfusz regression coefficients (§4.1, NWS 1990)
    # Calculated in Fahrenheit space; converted back to °C for output.
    _C1 = -42.379
    _C2 = 2.04901523
    _C3 = 10.14333127
    _C4 = -0.22475541
    _C5 = -6.83783e-3
    _C6 = -5.481717e-2
    _C7 = 1.22874e-3
    _C8 = 8.5282e-4
    _C9 = -1.99e-6

    # Category thresholds for documentation / stress-scale future integration (§2)
    THRESHOLDS_F = {
        "NORMAL": 80.0,
        "CAUTION": 91.0,
        "EXTREME_CAUTION": 103.0,
        "DANGER": 125.0,
    }

    def __init__(self, enforce_validation: bool = True):
        self.enforce_validation = enforce_validation

    # ------------------------------------------------------------------
    # Validation (§27) — do not silently fabricate (§25)
    # ------------------------------------------------------------------
    def validate_input(self, record: CanonicalThermalInput) -> None:
        if not isinstance(record.area_id, str) or not record.area_id.strip():
            raise HeatIndexValidationError("REQUIRED: area_id (§7) missing or empty")
        if not isinstance(record.timestamp, str) or len(record.timestamp) < 1:
            raise HeatIndexValidationError("REQUIRED: timestamp (§7) missing")

        # Required environmental (§8.1)
        for f in ("temperature_c", "relative_humidity_pct"):
            val = getattr(record, f, None)
            if val is None or (isinstance(val, float) and math.isnan(val)):
                raise HeatIndexValidationError(f"REQUIRED: {f} (§8) is missing/null")
            if isinstance(val, (int, float)) and math.isinf(val):
                raise HeatIndexValidationError(f"REQUIRED: {f} (§8) is infinite")

        # Unit / range sanity (§27)
        if not (-50.0 <= record.temperature_c <= 60.0):
            # Physically plausible range guard; not absolute physical law
            # but catches unit errors (e.g., Fahrenheit passed as °C)
            raise HeatIndexValidationError(
                f"temperature_c out of plausible range: {record.temperature_c}°C (§26 / §27)"
            )
        if not (0.0 <= record.relative_humidity_pct <= 100.0):
            raise HeatIndexValidationError(
                f"relative_humidity_pct must be 0–100, got {record.relative_humidity_pct} (§8 / §27)"
            )

    # ------------------------------------------------------------------
    # Core formula (§4.1, §9)
    # ------------------------------------------------------------------
    def _rothfusz_fahrenheit(self, T_f: float, RH: float) -> float:
        """
        Full Rothfusz regression.
        Applied when T >= ~80 °F (26.7 °C); below that the simple
        approximation is close enough, but we apply the full form
        with standard adjustment logic for consistency.
        """
        # Base regression
        hi = (
            self._C1
            + self._C2 * T_f
            + self._C3 * RH
            + self._C4 * T_f * RH
            + self._C5 * (T_f ** 2)
            + self._C6 * (RH ** 2)
            + self._C7 * (T_f ** 2) * RH
            + self._C8 * T_f * (RH ** 2)
            + self._C9 * (T_f ** 2) * (RH ** 2)
        )

        # Adjustment A: low RH at high temperature (§4.1 / NWS docs)
        if 80.0 <= T_f <= 112.0 and RH < 13.0:
            adjust = ((13.0 - RH) / 4.0) * math.sqrt(
                (17.0 - abs(T_f - 95.0)) / 17.0
            )
            hi -= adjust

        # Adjustment B: high RH at moderate temperature (§4.1 / NWS docs)
        if 80.0 <= T_f <= 87.0 and RH > 85.0:
            adjust = ((RH - 85.0) / 10.0) * ((87.0 - T_f) / 5.0)
            hi += adjust

        return hi

    def _c_to_f(self, c: float) -> float:
        return c * 9.0 / 5.0 + 32.0

    def _f_to_c(self, f: float) -> float:
        return (f - 32.0) * 5.0 / 9.0

    # ------------------------------------------------------------------
    # Public interface (§20 output contract compatibility)
    # ------------------------------------------------------------------
    def calculate(self, record: CanonicalThermalInput) -> HeatIndexDerived:
        """
        Calculate derived heat_index_c from canonical input.
        
        Returns HeatIndexDerived with status = INSUFFICIENT_DATA
        if required fields are missing rather than computing with NaN (§25).
        """
        # Strict validation first (§27)
        try:
            if self.enforce_validation:
                self.validate_input(record)
        except HeatIndexValidationError as exc:
            # Per §25: never fabricate; return explicit failure state
            return HeatIndexDerived(
                area_id=record.area_id,
                timestamp=record.timestamp,
                heat_index_c=None,
                calculation_status="INSUFFICIENT_DATA",
                method_version=f"FAILED-VALIDATION-{exc}",
            )

        # Convert required inputs to Fahrenheit space for Rothfusz (§26 / formula)
        T_f = self._c_to_f(record.temperature_c)
        RH = record.relative_humidity_pct

        # If temperature below ~80°F (26.7°C), the regression is still
        # applied but the result is close to actual temperature; we keep
        # the calculation unified rather than silently branching.
        hi_f = self._rothfusz_fahrenheit(T_f, RH)

        # Convert result back to internal °C (§26)
        hi_c = self._f_to_c(hi_f)

        # Sanity clamp: do not allow negative heat index when T is very high
        # (physically it should be >= temperature for high RH; but we do
        # not silently alter extreme outputs—just document.)
        return HeatIndexDerived(
            area_id=record.area_id,
            timestamp=record.timestamp,
            heat_index_c=round(hi_c, 2),
            calculation_status="COMPUTED",
            method_version="NWS-Rothfusz-1990-v1",
        )

    # ------------------------------------------------------------------
    # Documentation generator (§4.1, §9, §29)
    # ------------------------------------------------------------------
    def documentation(self) -> Dict[str, Any]:
        """
        Returns machine-readable documentation required by §9
        and useful for explainability (§29 / SHAP context).
        """
        return {
            "component": "Thermal Calculation Engine",
            "function": "Heat Index",
            "contract_version": "0.1",
            "formula_library": "NOAA NWS Rothfusz (1990)",
            "formula_reference_url": "https://www.weather.gov/ama/heatindex",
            "required_inputs": [
                "temperature_c (float, °C)",
                "relative_humidity_pct (float, %)"
            ],
            "output": {
                "field": "heat_index_c",
                "unit": "°C",
                "status": "DERIVED (§9)"
            },
            "units_internal": "°C / % (§26)",
            "assumptions": [
                "Standard atmospheric pressure ~1013 hPa",
                "Light wind / indoor approximation",
                "No direct solar-radiation correction (see WBGT)",
                "Adult metabolic rate baseline"
            ],
            "applicability_range": {
                "temperature_c_approx": ">= 26.7 °C effective range; calculation valid across full range with reduced accuracy below 26.7 °C",
                "humidity_pct": "0–100",
                "caveats": "Not a direct mortality predictor (§16); environmental hazard only (§3)"
            },
            "fallback_behaviour": "If required inputs missing or invalid -> INSUFFICIENT_DATA; no imputation (§25)",
            "validation_rules_applied": [
                "area_id present (§7)",
                "timestamp present (§7)",
                "temperature_c in plausible range (§27)",
                "relative_humidity_pct in 0–100 (§8/§27)"
            ],
            "version": "v1"
        }

    # ------------------------------------------------------------------
    # Batch / vector interface (optional for pipeline use)
    # ------------------------------------------------------------------
    def calculate_batch(
        self,
        records: list[CanonicalThermalInput]
    ) -> list[HeatIndexDerived]:
        return [self.calculate(r) for r in records]


# ------------------------------------------------------------------
# Module-level convenience for quick use (§4.1 interface)
# ------------------------------------------------------------------
def compute_heat_index(
    temperature_c: float,
    relative_humidity_pct: float,
    area_id: str = "UNKNOWN",
    timestamp: str = "1970-01-01T00:00:00Z",
) -> HeatIndexDerived:
    """
    Quick function interface aligned with §9 derived output.
    """
    record = CanonicalThermalInput(
        area_id=area_id,
        timestamp=timestamp,
        temperature_c=temperature_c,
        relative_humidity_pct=relative_humidity_pct,
    )
    engine = HeatIndexEngine()
    return engine.calculate(record)


# ------------------------------------------------------------------
# Example / self-test (not unit-test; for branch verification)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    # Verify branch compliance: uses internal °C, validates inputs,
    # does not fabricate missing data.
    engine = HeatIndexEngine(enforce_validation=True)

    # Normal operation
    rec = CanonicalThermalInput(
        area_id="WARD_017",
        timestamp="2026-05-20T14:00:00+05:30",
        temperature_c=35.0,   # ~95 °F
        relative_humidity_pct=60.0,
        latitude=20.35,
        longitude=85.82,
    )
    result = engine.calculate(rec)
    print("Computed:", result)
    assert result.calculation_status == "COMPUTED"
    assert result.heat_index_c is not None
    assert 40.0 < result.heat_index_c < 50.0  # ~45 °C HI for 35°C/60%

    # Missing required input (§25)
    bad_rec = CanonicalThermalInput(
        area_id="WARD_018",
        timestamp="2026-05-20T14:00:00+05:30",
        temperature_c=35.0,
        relative_humidity_pct=None,  # MISSING
    )
    bad_result = engine.calculate(bad_rec)
    print("Missing RH:", bad_result)
    assert bad_result.calculation_status == "INSUFFICIENT_DATA"
    assert bad_result.heat_index_c is None

    # Documentation (§9)
    meta = engine.documentation()
    print("Method version:", meta["formula_library"])
    assert "NWS" in meta["formula_library"]
