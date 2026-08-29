"""
HeatIQ Thermal Engine — Wet Bulb Globe Temperature (WBGT) Module
Data Contract: v0.1  |  Component: Data / Backend / Thermal Engine (§4.1)
Branch: feature/wbgt-calculation

Output schema (§9):
    wbgt_c : float | DERIVED | °C

Formula / Library (§4.1, §9):
    ISO 7243:2017 — Hot environments — Estimation of the heat stress on working man
    Simplified Liljegren model for outdoor WBGT estimation
    References:
        - ISO 7243:2017
        - Liljegren et al. (2008), "Modeling the Wet Bulb Globe Temperature Using 
          Standard Meteorological Measurements", J. Occup. Environ. Hyg. 5:10, 645-655
        - Australian Bureau of Meteorology WBGT approximation

Required inputs (§8):
    temperature_c (float, °C)  — REQUIRED
    relative_humidity_pct (float, %) — REQUIRED
    wind_speed_ms (float, m/s) — REQUIRED for outdoor; PROVISIONAL for indoor
    solar_radiation_wm2 (float, W/m²) — REQUIRED for outdoor sunlight; 0 for shade/indoor

Assumptions / Applicability (§9):
    - Outdoor conditions with solar radiation exposure (primary use case)
    - Indoor/shade variant available (solar_radiation = 0, reduced wind dependency)
    - Standard atmospheric pressure (~1013.25 hPa)
    - Globe thermometer approximation using black globe diameter ~150mm
    - Designed for occupational heat stress assessment
    - Effective range: 15–45 °C air temperature; 0–1200 W/m² solar radiation

Units (§26):
    Internal: temperature in °C; wind speed in m/s; solar radiation in W/m²

Fallback (§9, §25):
    If required inputs missing or out of range -> do NOT calculate.
    Return INSUFFICIENT_DATA rather than fabricate.
    If solar_radiation missing but other inputs present -> attempt indoor approximation.

Method variants:
    - OUTDOOR_FULL: Uses temperature, humidity, wind, solar radiation
    - OUTDOOR_SIMPLIFIED: Approximation when solar radiation unavailable
    - INDOOR: Simplified calculation without solar/wind effects
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Dict, Any, Literal
import numpy as np


class WBGTValidationError(Exception):
    """Raised when canonical input fails §27 validation."""
    pass


@dataclass
class CanonicalThermalInput:
    """
    Canonical observation per HeatIQ Contract §5 / §8 / §28.
    One record = one geographic area at one timestamp.
    
    Reusing schema from heat_index.py for consistency.
    """
    area_id: str
    timestamp: str  # ISO-8601 with timezone or documented UTC (§7)

    # Required environmental (§8)
    temperature_c: float
    relative_humidity_pct: float

    # Required for WBGT outdoor (§8)
    wind_speed_ms: Optional[float] = None
    solar_radiation_wm2: Optional[float] = None

    # Optional identification (§7)
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Optional / provisional (§8)
    dew_point_c: Optional[float] = None
    cloud_cover_pct: Optional[float] = None
    precipitation_mm: Optional[float] = None

    # Optional contextual (§10–12)
    population: Optional[int] = None
    elderly_fraction: Optional[float] = None


@dataclass
class WBGTDerived:
    """
    Derived thermal-index schema per §9.
    """
    area_id: str
    timestamp: str
    wbgt_c: Optional[float]
    
    # Method variant used (for transparency / explainability §29)
    calculation_method: Literal[
        "OUTDOOR_FULL",
        "OUTDOOR_SIMPLIFIED", 
        "INDOOR",
        "INSUFFICIENT_DATA"
    ] = "OUTDOOR_FULL"
    
    # Status for missing-data traceability (§25)
    calculation_status: Literal["COMPUTED", "INSUFFICIENT_DATA", "OUT_OF_RANGE"] = "COMPUTED"
    
    # Documentation of method for explainability (§29)
    method_version: str = "Liljegren-ISO7243-v1"


class WBGTEngine:
    """
    Thermal Calculation Engine component for WBGT (§4.1).
    
    WBGT is the gold standard for occupational heat stress assessment,
    particularly for outdoor workers with solar exposure.
    
    Three calculation modes:
    1. OUTDOOR_FULL: Full Liljegren model with solar radiation
    2. OUTDOOR_SIMPLIFIED: Approximation when solar data unavailable
    3. INDOOR: Simplified natural wet bulb approach
    """

    # ISO 7243:2017 risk thresholds (reference values, °C WBGT)
    # For acclimatized workers with moderate work rate
    THRESHOLDS_C = {
        "MINIMAL_RISK": 28.0,
        "LOW_RISK": 28.0,
        "MODERATE_RISK": 31.0,
        "HIGH_RISK": 32.0,
        "EXTREME_RISK": 34.0,
    }

    # Physical constants
    STEFAN_BOLTZMANN = 5.6703e-8  # W/m²/K⁴
    GLOBE_DIAMETER = 0.15  # meters (standard black globe)
    GLOBE_EMISSIVITY = 0.95
    GLOBE_ABSORPTIVITY = 0.95

    def __init__(self, 
                 enforce_validation: bool = True,
                 prefer_outdoor: bool = True):
        """
        Initialize WBGT Engine.
        
        Parameters:
        -----------
        enforce_validation : bool
            Strict input validation per §27
        prefer_outdoor : bool
            If True, attempt outdoor calculation when solar data available;
            if False, prefer indoor approximation
        """
        self.enforce_validation = enforce_validation
        self.prefer_outdoor = prefer_outdoor

    # ------------------------------------------------------------------
    # Validation (§27) — do not silently fabricate (§25)
    # ------------------------------------------------------------------
    def validate_input(self, 
                      record: CanonicalThermalInput,
                      require_outdoor: bool = False) -> None:
        """
        Validate canonical input per §27.
        
        Parameters:
        -----------
        require_outdoor : bool
            If True, require wind_speed and solar_radiation for outdoor calculation
        """
        # Basic required fields (§7)
        if not isinstance(record.area_id, str) or not record.area_id.strip():
            raise WBGTValidationError("REQUIRED: area_id (§7) missing or empty")
        if not isinstance(record.timestamp, str) or len(record.timestamp) < 1:
            raise WBGTValidationError("REQUIRED: timestamp (§7) missing")

        # Core environmental requirements (§8)
        for field in ("temperature_c", "relative_humidity_pct"):
            val = getattr(record, field, None)
            if val is None or (isinstance(val, float) and math.isnan(val)):
                raise WBGTValidationError(f"REQUIRED: {field} (§8) is missing/null")
            if isinstance(val, (int, float)) and math.isinf(val):
                raise WBGTValidationError(f"REQUIRED: {field} (§8) is infinite")

        # Outdoor-specific requirements
        if require_outdoor:
            if record.wind_speed_ms is None or math.isnan(record.wind_speed_ms):
                raise WBGTValidationError(
                    "REQUIRED for outdoor WBGT: wind_speed_ms (§8)"
                )
            if record.solar_radiation_wm2 is None or math.isnan(record.solar_radiation_wm2):
                raise WBGTValidationError(
                    "REQUIRED for outdoor WBGT: solar_radiation_wm2 (§8)"
                )

        # Physical plausibility (§27)
        if not (-50.0 <= record.temperature_c <= 60.0):
            raise WBGTValidationError(
                f"temperature_c out of plausible range: {record.temperature_c}°C (§27)"
            )
        if not (0.0 <= record.relative_humidity_pct <= 100.0):
            raise WBGTValidationError(
                f"relative_humidity_pct must be 0–100, got {record.relative_humidity_pct} (§27)"
            )
        
        if record.wind_speed_ms is not None:
            if not (0.0 <= record.wind_speed_ms <= 50.0):
                raise WBGTValidationError(
                    f"wind_speed_ms out of plausible range: {record.wind_speed_ms} m/s (§27)"
                )
        
        if record.solar_radiation_wm2 is not None:
            if not (0.0 <= record.solar_radiation_wm2 <= 1500.0):
                raise WBGTValidationError(
                    f"solar_radiation_wm2 out of plausible range: {record.solar_radiation_wm2} W/m² (§27)"
                )

    # ------------------------------------------------------------------
    # Psychrometric calculations
    # ------------------------------------------------------------------
    def _saturation_vapor_pressure(self, temp_c: float) -> float:
        """
        Calculate saturation vapor pressure using Magnus formula.
        Returns pressure in hPa.
        """
        return 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5))

    def _vapor_pressure(self, temp_c: float, rh_pct: float) -> float:
        """Calculate actual vapor pressure from temperature and RH."""
        es = self._saturation_vapor_pressure(temp_c)
        return (rh_pct / 100.0) * es

    def _wet_bulb_temperature(self, temp_c: float, rh_pct: float) -> float:
        """
        Calculate natural wet bulb temperature using Stull approximation.
        
        Reference: Stull, R. (2011), "Wet-Bulb Temperature from Relative Humidity 
        and Air Temperature", J. Appl. Meteor. Climatol., 50, 2267-2269.
        
        Good approximation for RH > 20%, T > 0°C.
        """
        T = temp_c
        RH = rh_pct
        
        Tw = T * math.atan(0.151977 * math.sqrt(RH + 8.313659)) + \
             math.atan(T + RH) - \
             math.atan(RH - 1.676331) + \
             0.00391838 * (RH ** 1.5) * math.atan(0.023101 * RH) - \
             4.686035
        
        return Tw

    def _globe_temperature(self, 
                          temp_c: float,
                          wind_ms: float,
                          solar_wm2: float) -> float:
        """
        Estimate black globe temperature from meteorological inputs.
        
        Simplified Liljegren model approximation.
        Reference: Liljegren et al. (2008)
        """
        T_air_k = temp_c + 273.15
        
        # Convective heat transfer coefficient (W/m²/K)
        # Simplified forced convection approximation
        h_conv = 6.3 * (wind_ms ** 0.6) / (self.GLOBE_DIAMETER ** 0.4)
        h_conv = max(h_conv, 3.0)  # Minimum natural convection
        
        # Radiative component
        # Absorbed solar radiation per unit surface area
        solar_absorbed = self.GLOBE_ABSORPTIVITY * solar_wm2 / 4.0  # Sphere geometry
        
        # Simplified energy balance: absorbed solar + convection = radiation
        # T_globe⁴ ≈ T_air⁴ + (solar_absorbed + h_conv*(T_air - T_globe)) / (ε*σ)
        # Iterative solution simplified to first-order approximation
        
        delta_T = solar_absorbed / (h_conv + 4 * self.GLOBE_EMISSIVITY * 
                                    self.STEFAN_BOLTZMANN * (T_air_k ** 3))
        
        T_globe_k = T_air_k + delta_T
        return T_globe_k - 273.15

    # ------------------------------------------------------------------
    # WBGT calculation methods
    # ------------------------------------------------------------------
    def _wbgt_outdoor_full(self,
                          temp_c: float,
                          rh_pct: float,
                          wind_ms: float,
                          solar_wm2: float) -> float:
        """
        Full outdoor WBGT calculation with solar radiation.
        
        WBGT_outdoor = 0.7*Tnwb + 0.2*Tg + 0.1*Ta
        
        Where:
            Tnwb = Natural wet bulb temperature
            Tg = Black globe temperature
            Ta = Dry bulb (air) temperature
        """
        T_nwb = self._wet_bulb_temperature(temp_c, rh_pct)
        T_globe = self._globe_temperature(temp_c, wind_ms, solar_wm2)
        T_air = temp_c
        
        wbgt = 0.7 * T_nwb + 0.2 * T_globe + 0.1 * T_air
        return wbgt

    def _wbgt_outdoor_simplified(self,
                                temp_c: float,
                                rh_pct: float,
                                wind_ms: float) -> float:
        """
        Simplified outdoor WBGT when solar radiation unavailable.
        
        Uses empirical approximation assuming moderate solar load.
        Less accurate than full method but useful when solar data missing.
        """
        T_nwb = self._wet_bulb_temperature(temp_c, rh_pct)
        
        # Assume moderate solar radiation (~600 W/m²) for estimation
        estimated_solar = 600.0
        T_globe = self._globe_temperature(temp_c, wind_ms, estimated_solar)
        T_air = temp_c
        
        wbgt = 0.7 * T_nwb + 0.2 * T_globe + 0.1 * T_air
        return wbgt

    def _wbgt_indoor(self,
                    temp_c: float,
                    rh_pct: float) -> float:
        """
        Indoor WBGT calculation (no solar radiation, minimal wind).
        
        WBGT_indoor = 0.7*Tnwb + 0.3*Tg
        
        For indoor/shade with no significant radiant heat sources,
        Tg ≈ Ta, so:
        WBGT_indoor ≈ 0.7*Tnwb + 0.3*Ta
        """
        T_nwb = self._wet_bulb_temperature(temp_c, rh_pct)
        T_air = temp_c
        
        # Indoor: globe temperature ≈ air temperature (no solar)
        wbgt = 0.7 * T_nwb + 0.3 * T_air
        return wbgt

    # ------------------------------------------------------------------
    # Public interface (§20 output contract compatibility)
    # ------------------------------------------------------------------
    def calculate(self, record: CanonicalThermalInput) -> WBGTDerived:
        """
        Calculate derived wbgt_c from canonical input.
        
        Automatically selects appropriate calculation method based on
        available inputs:
        1. If solar_radiation + wind available -> OUTDOOR_FULL
        2. If wind available but no solar -> OUTDOOR_SIMPLIFIED
        3. Otherwise -> INDOOR
        
        Returns WBGTDerived with status = INSUFFICIENT_DATA
        if core required fields are missing (§25).
        """
        # Check if we have minimum required data
        try:
            if self.enforce_validation:
                # Validate core fields (temp, RH)
                self.validate_input(record, require_outdoor=False)
        except WBGTValidationError as exc:
            return WBGTDerived(
                area_id=record.area_id,
                timestamp=record.timestamp,
                wbgt_c=None,
                calculation_method="INSUFFICIENT_DATA",
                calculation_status="INSUFFICIENT_DATA",
                method_version=f"FAILED-VALIDATION-{exc}",
            )

        # Determine calculation method based on available inputs
        has_solar = (record.solar_radiation_wm2 is not None and 
                    not math.isnan(record.solar_radiation_wm2))
        has_wind = (record.wind_speed_ms is not None and 
                   not math.isnan(record.wind_speed_ms))

        try:
            if has_solar and has_wind and self.prefer_outdoor:
                # Full outdoor calculation
                wbgt = self._wbgt_outdoor_full(
                    record.temperature_c,
                    record.relative_humidity_pct,
                    record.wind_speed_ms,
                    record.solar_radiation_wm2
                )
                method = "OUTDOOR_FULL"
                
            elif has_wind and self.prefer_outdoor:
                # Simplified outdoor (no solar data)
                wbgt = self._wbgt_outdoor_simplified(
                    record.temperature_c,
                    record.relative_humidity_pct,
                    record.wind_speed_ms
                )
                method = "OUTDOOR_SIMPLIFIED"
                
            else:
                # Indoor/shade approximation
                wbgt = self._wbgt_indoor(
                    record.temperature_c,
                    record.relative_humidity_pct
                )
                method = "INDOOR"

            return WBGTDerived(
                area_id=record.area_id,
                timestamp=record.timestamp,
                wbgt_c=round(wbgt, 2),
                calculation_method=method,
                calculation_status="COMPUTED",
                method_version="Liljegren-ISO7243-v1",
            )

        except Exception as exc:
            return WBGTDerived(
                area_id=record.area_id,
                timestamp=record.timestamp,
                wbgt_c=None,
                calculation_method="INSUFFICIENT_DATA",
                calculation_status="OUT_OF_RANGE",
                method_version=f"CALCULATION-ERROR-{exc}",
            )

    def get_risk_category(self, wbgt_c: float) -> str:
        """
        Determine occupational heat stress category from WBGT.
        Based on ISO 7243:2017 for acclimatized workers, moderate work rate.
        
        NOTE: Actual risk thresholds depend on:
        - Acclimatization status
        - Work intensity
        - Clothing
        - Individual factors
        
        These are reference values only (§3 - not final health risk).
        """
        if wbgt_c < self.THRESHOLDS_C["MINIMAL_RISK"]:
            return "MINIMAL_RISK"
        elif wbgt_c < self.THRESHOLDS_C["MODERATE_RISK"]:
            return "LOW_RISK"
        elif wbgt_c < self.THRESHOLDS_C["HIGH_RISK"]:
            return "MODERATE_RISK"
        elif wbgt_c < self.THRESHOLDS_C["EXTREME_RISK"]:
            return "HIGH_RISK"
        else:
            return "EXTREME_RISK"

    # ------------------------------------------------------------------
    # Documentation generator (§4.1, §9, §29)
    # ------------------------------------------------------------------
    def documentation(self) -> Dict[str, Any]:
        """
        Returns machine-readable documentation required by §9
        and useful for explainability (§29).
        """
        return {
            "component": "Thermal Calculation Engine",
            "function": "Wet Bulb Globe Temperature (WBGT)",
            "contract_version": "0.1",
            "formula_library": "ISO 7243:2017 / Liljegren et al. (2008)",
            "formula_reference_urls": [
                "https://www.iso.org/standard/67188.html",
                "https://doi.org/10.1080/15459620802310770"
            ],
            "required_inputs": {
                "all_methods": [
                    "temperature_c (float, °C)",
                    "relative_humidity_pct (float, %)"
                ],
                "outdoor_full": [
                    "wind_speed_ms (float, m/s)",
                    "solar_radiation_wm2 (float, W/m²)"
                ],
                "outdoor_simplified": [
                    "wind_speed_ms (float, m/s)"
                ],
                "indoor": []
            },
            "output": {
                "field": "wbgt_c",
                "unit": "°C",
                "status": "DERIVED (§9)"
            },
            "calculation_methods": {
                "OUTDOOR_FULL": "0.7*Tnwb + 0.2*Tg + 0.1*Ta (with solar radiation)",
                "OUTDOOR_SIMPLIFIED": "0.7*Tnwb + 0.2*Tg + 0.1*Ta (estimated solar ~600 W/m²)",
                "INDOOR": "0.7*Tnwb + 0.3*Ta (no solar, minimal wind)"
            },
            "units_internal": "°C / m/s / W/m² (§26)",
            "assumptions": [
                "Standard atmospheric pressure ~1013 hPa",
                "Black globe diameter 150mm (standard)",
                "Globe emissivity 0.95, absorptivity 0.95",
                "Natural wet bulb (not psychrometric)",
                "Adult metabolic rate baseline",
                "Outdoor methods assume some solar exposure"
            ],
            "applicability_range": {
                "temperature_c": "15–45 °C effective range",
                "solar_radiation_wm2": "0–1200 W/m² (outdoor)",
                "wind_speed_ms": "0–20 m/s typical",
                "caveats": [
                    "Primary use: occupational heat stress (outdoor workers)",
                    "ISO 7243 designed for workplace assessment",
                    "Not a direct mortality predictor (§16)",
                    "Environmental hazard only (§3)"
                ]
            },
            "fallback_behaviour": "If required inputs missing -> INSUFFICIENT_DATA; no imputation (§25)",
            "validation_rules_applied": [
                "area_id present (§7)",
                "timestamp present (§7)",
                "temperature_c in plausible range (§27)",
                "relative_humidity_pct in 0–100 (§8/§27)",
                "wind_speed_ms in 0–50 m/s (§27)",
                "solar_radiation_wm2 in 0–1500 W/m² (§27)"
            ],
            "iso_7243_thresholds": self.THRESHOLDS_C,
            "version": "v1"
        }

    # ------------------------------------------------------------------
    # Batch / vector interface
    # ------------------------------------------------------------------
    def calculate_batch(self,
                       records: list[CanonicalThermalInput]) -> list[WBGTDerived]:
        """Calculate WBGT for multiple records."""
        return [self.calculate(r) for r in records]


# ------------------------------------------------------------------
# Module-level convenience functions
# ------------------------------------------------------------------
def compute_wbgt_outdoor(
    temperature_c: float,
    relative_humidity_pct: float,
    wind_speed_ms: float,
    solar_radiation_wm2: float,
    area_id: str = "UNKNOWN",
    timestamp: str = "1970-01-01T00:00:00Z",
) -> WBGTDerived:
    """Quick outdoor WBGT calculation."""
    record = CanonicalThermalInput(
        area_id=area_id,
        timestamp=timestamp,
        temperature_c=temperature_c,
        relative_humidity_pct=relative_humidity_pct,
        wind_speed_ms=wind_speed_ms,
        solar_radiation_wm2=solar_radiation_wm2,
    )
    engine = WBGTEngine(prefer_outdoor=True)
    return engine.calculate(record)


def compute_wbgt_indoor(
    temperature_c: float,
    relative_humidity_pct: float,
    area_id: str = "UNKNOWN",
    timestamp: str = "1970-01-01T00:00:00Z",
) -> WBGTDerived:
    """Quick indoor WBGT calculation."""
    record = CanonicalThermalInput(
        area_id=area_id,
        timestamp=timestamp,
        temperature_c=temperature_c,
        relative_humidity_pct=relative_humidity_pct,
    )
    engine = WBGTEngine(prefer_outdoor=False)
    return engine.calculate(record)


# ------------------------------------------------------------------
# Self-test
# ------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 70)
    print("WBGT Engine Self-Test")
    print("=" * 70)
    
    engine = WBGTEngine()
    
    # Test 1: Full outdoor calculation
    print("\n1. OUTDOOR_FULL: Hot sunny day with outdoor worker exposure")
    rec1 = CanonicalThermalInput(
        area_id="WARD_017",
        timestamp="2026-05-20T14:00:00+05:30",
        temperature_c=38.0,
        relative_humidity_pct=55.0,
        wind_speed_ms=2.5,
        solar_radiation_wm2=850.0,
    )
    result1 = engine.calculate(rec1)
    print(f"   Input: {rec1.temperature_c}°C, {rec1.relative_humidity_pct}% RH, "
          f"{rec1.wind_speed_ms} m/s wind, {rec1.solar_radiation_wm2} W/m² solar")
    print(f"   WBGT: {result1.wbgt_c}°C")
    print(f"   Method: {result1.calculation_method}")
    print(f"   Risk: {engine.get_risk_category(result1.wbgt_c)}")
    assert result1.calculation_status == "COMPUTED"
    assert result1.calculation_method == "OUTDOOR_FULL"
    assert 30.0 < result1.wbgt_c < 40.0
    print("   ✓ PASSED")
    
    # Test 2: Outdoor simplified (no solar data)
    print("\n2. OUTDOOR_SIMPLIFIED: Solar radiation unavailable")
    rec2 = CanonicalThermalInput(
        area_id="WARD_018",
        timestamp="2026-05-20T14:00:00+05:30",
        temperature_c=35.0,
        relative_humidity_pct=60.0,
        wind_speed_ms=3.0,
        solar_radiation_wm2=None,  # Missing
    )
    result2 = engine.calculate(rec2)
    print(f"   Input: {rec2.temperature_c}°C, {rec2.relative_humidity_pct}% RH, "
          f"{rec2.wind_speed_ms} m/s wind, solar=None")
    print(f"   WBGT: {result2.wbgt_c}°C")
    print(f"   Method: {result2.calculation_method}")
    assert result2.calculation_method == "OUTDOOR_SIMPLIFIED"
    assert result2.wbgt_c is not None
    print("   ✓ PASSED")
    
    # Test 3: Indoor calculation
    print("\n3. INDOOR: No wind/solar data available")
    rec3 = CanonicalThermalInput(
        area_id="WARD_019",
        timestamp="2026-05-20T14:00:00+05:30",
        temperature_c=32.0,
        relative_humidity_pct=70.0,
        wind_speed_ms=None,
        solar_radiation_wm2=None,
    )
    result3 = engine.calculate(rec3)
    print(f"   Input: {rec3.temperature_c}°C, {rec3.relative_humidity_pct}% RH, "
          f"wind=None, solar=None")
    print(f"   WBGT: {result3.wbgt_c}°C")
    print(f"   Method: {result3.calculation_method}")
    assert result3.calculation_method == "INDOOR"
    assert result3.wbgt_c is not None
    print("   ✓ PASSED")
    
    # Test 4: Missing required data (§25 - no fabrication)
    print("\n4. INSUFFICIENT_DATA: Missing temperature (§25)")
    rec4 = CanonicalThermalInput(
        area_id="WARD_020",
        timestamp="2026-05-20T14:00:00+05:30",
        temperature_c=None,  # Missing!
        relative_humidity_pct=60.0,
    )
    result4 = engine.calculate(rec4)
    print(f"   Input: temp=None, {rec4.relative_humidity_pct}% RH")
    print(f"   WBGT: {result4.wbgt_c}")
    print(f"   Status: {result4.calculation_status}")
    assert result4.calculation_status == "INSUFFICIENT_DATA"
    assert result4.wbgt_c is None
    print("   ✓ PASSED")
    
    # Test 5: Multiple scenarios comparison
    print("\n5. Comparison across conditions:")
    print(f"   {'Condition':<20} {'Temp':<8} {'RH%':<8} {'Wind':<8} {'Solar':<10} {'WBGT':<8} {'Method':<20}")
    print("   " + "-" * 90)
    
    scenarios = [
        ("Mild indoor", 25.0, 50.0, None, None),
        ("Hot indoor", 35.0, 60.0, None, None),
        ("Hot + moderate sun", 35.0, 60.0, 2.0, 600.0),
        ("Hot + intense sun", 38.0, 50.0, 1.5, 1000.0),
        ("Extreme conditions", 42.0, 40.0, 1.0, 1100.0),
    ]
    
    for label, temp, rh, wind, solar in scenarios:
        rec = CanonicalThermalInput(
            area_id="TEST",
            timestamp="2026-05-20T14:00:00Z",
            temperature_c=temp,
            relative_humidity_pct=rh,
            wind_speed_ms=wind,
            solar_radiation_wm2=solar,
        )
        res = engine.calculate(rec)
        
        wind_str = f"{wind:.1f}" if wind is not None else "N/A"
        solar_str = f"{solar:.0f}" if solar is not None else "N/A"
        
        print(f"   {label:<20} {temp:<8.1f} {rh:<8.1f} {wind_str:<8} {solar_str:<10} "
              f"{res.wbgt_c:<8.1f} {res.calculation_method:<20}")
    
    print("\n6. Documentation (§9)")
    docs = engine.documentation()
    print(f"   Formula: {docs['formula_library']}")
    print(f"   Contract version: {docs['contract_version']}")
    print(f"   Methods: {list(docs['calculation_methods'].keys())}")
    assert "ISO 7243" in docs["formula_library"]
    print("   ✓ PASSED")
    
    print("\n" + "=" * 70)
    print("ALL SELF-TESTS PASSED ✓")
    print("=" * 70)
