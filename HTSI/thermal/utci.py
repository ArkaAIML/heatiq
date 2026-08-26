"""
HeatIQ Thermal Engine — Universal Thermal Climate Index (UTCI) Module
Data Contract: v0.1  |  Component: Data / Backend / Thermal Engine (§4.1)
Branch: feature/utci-calculation

Output schema (§9):
    utci_c : float | DERIVED | °C

Formula / Library (§4.1, §9):
    Universal Thermal Climate Index (UTCI)
    COST Action 730 — validated polynomial approximation
    
    References:
        - Bröde P. et al. (2012), "Deriving the operational procedure for the 
          Universal Thermal Climate Index (UTCI)", Int J Biometeorol 56:481-494
        - Błażejczyk K. et al. (2013), "An introduction to the Universal Thermal 
          Climate Index (UTCI)", Geographia Polonica 86(1):5-10
        - UTCI Official: http://www.utci.org/
        - pythermalcomfort library implementation reference

Required inputs (§8):
    temperature_c (float, °C)  — REQUIRED
    relative_humidity_pct (float, %) — REQUIRED (converted to vapor pressure)
    wind_speed_ms (float, m/s) — REQUIRED
    
    Optional for enhanced accuracy:
    solar_radiation_wm2 (float, W/m²) — PROVISIONAL (mean radiant temp approximation)

Assumptions / Applicability (§9):
    - Designed for outdoor thermal comfort assessment across all climates
    - Valid range: -50°C to +50°C; 5% to 100% RH; 0.5 to 30 m/s wind
    - Assumes standard clothing insulation (adaptive based on outdoor temp)
    - Walking metabolic rate (2.3 MET ≈ 135 W/m²)
    - Mean radiant temperature approximation from solar radiation when available
    - Universal applicability (valid for cold, moderate, and hot stress)

Units (§26):
    Internal: temperature in °C; wind speed in m/s; solar radiation in W/m²

Fallback (§9, §25):
    If required inputs missing or out of range -> do NOT calculate.
    Return INSUFFICIENT_DATA rather than fabricate.
    If solar_radiation missing -> assume Tmrt ≈ Ta (reduced accuracy but valid).

UTCI Thermal Stress Categories (reference):
    Extreme cold stress:      UTCI < -40°C
    Very strong cold stress:  -40°C ≤ UTCI < -27°C
    Strong cold stress:       -27°C ≤ UTCI < -13°C
    Moderate cold stress:     -13°C ≤ UTCI < 0°C
    No thermal stress:        0°C ≤ UTCI < 9°C
    Moderate heat stress:     9°C ≤ UTCI < 26°C
    Strong heat stress:       26°C ≤ UTCI < 32°C
    Very strong heat stress:  32°C ≤ UTCI < 38°C
    Extreme heat stress:      UTCI ≥ 38°C
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Dict, Any, Literal
import numpy as np


class UTCIValidationError(Exception):
    """Raised when canonical input fails §27 validation."""
    pass


@dataclass
class CanonicalThermalInput:
    """
    Canonical observation per HeatIQ Contract §5 / §8 / §28.
    One record = one geographic area at one timestamp.
    
    Reusing schema for consistency across thermal indices.
    """
    area_id: str
    timestamp: str  # ISO-8601 with timezone or documented UTC (§7)

    # Required environmental (§8)
    temperature_c: float
    relative_humidity_pct: float

    # Required for UTCI (§8)
    wind_speed_ms: Optional[float] = None
    
    # Optional but improves accuracy (§8)
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
class UTCIDerived:
    """
    Derived thermal-index schema per §9.
    """
    area_id: str
    timestamp: str
    utci_c: Optional[float]
    
    # Thermal stress category for interpretability
    thermal_stress_category: Optional[str] = None
    
    # Whether mean radiant temperature was estimated or assumed
    tmrt_method: Literal["SOLAR_ESTIMATED", "ASSUMED_EQUAL_TA"] = "ASSUMED_EQUAL_TA"
    
    # Status for missing-data traceability (§25)
    calculation_status: Literal["COMPUTED", "INSUFFICIENT_DATA", "OUT_OF_RANGE"] = "COMPUTED"
    
    # Documentation of method for explainability (§29)
    method_version: str = "COST-Action-730-v1"


class UTCIEngine:
    """
    Thermal Calculation Engine component for UTCI (§4.1).
    
    UTCI is a state-of-the-art thermal comfort index valid across
    all climates (cold to hot) and seasons. Unlike Heat Index (hot only)
    or WBGT (occupational focus), UTCI provides universal applicability
    for general population thermal stress assessment.
    
    The index represents the equivalent air temperature of a reference
    environment that would produce the same physiological response.
    """

    # UTCI thermal stress categories (COST Action 730)
    STRESS_CATEGORIES = [
        (-float('inf'), -40.0, "EXTREME_COLD"),
        (-40.0, -27.0, "VERY_STRONG_COLD"),
        (-27.0, -13.0, "STRONG_COLD"),
        (-13.0, 0.0, "MODERATE_COLD"),
        (0.0, 9.0, "NO_THERMAL_STRESS"),
        (9.0, 26.0, "MODERATE_HEAT"),
        (26.0, 32.0, "STRONG_HEAT"),
        (32.0, 38.0, "VERY_STRONG_HEAT"),
        (38.0, float('inf'), "EXTREME_HEAT"),
    ]

    # Valid ranges per COST Action 730
    VALID_TEMP_RANGE = (-50.0, 50.0)  # °C
    VALID_RH_RANGE = (5.0, 100.0)     # %
    VALID_WIND_RANGE = (0.5, 30.0)    # m/s (below 0.5 assumed 0.5)

    def __init__(self, enforce_validation: bool = True):
        """
        Initialize UTCI Engine.
        
        Parameters:
        -----------
        enforce_validation : bool
            Strict input validation per §27
        """
        self.enforce_validation = enforce_validation

    # ------------------------------------------------------------------
    # Validation (§27) — do not silently fabricate (§25)
    # ------------------------------------------------------------------
    def validate_input(self, record: CanonicalThermalInput) -> None:
        """Validate canonical input per §27."""
        
        # Basic required fields (§7)
        if not isinstance(record.area_id, str) or not record.area_id.strip():
            raise UTCIValidationError("REQUIRED: area_id (§7) missing or empty")
        if not isinstance(record.timestamp, str) or len(record.timestamp) < 1:
            raise UTCIValidationError("REQUIRED: timestamp (§7) missing")

        # Core environmental requirements (§8)
        for field in ("temperature_c", "relative_humidity_pct", "wind_speed_ms"):
            val = getattr(record, field, None)
            if val is None or (isinstance(val, float) and math.isnan(val)):
                raise UTCIValidationError(f"REQUIRED: {field} (§8) is missing/null")
            if isinstance(val, (int, float)) and math.isinf(val):
                raise UTCIValidationError(f"REQUIRED: {field} (§8) is infinite")

        # Physical plausibility (§27)
        if not (self.VALID_TEMP_RANGE[0] <= record.temperature_c <= self.VALID_TEMP_RANGE[1]):
            raise UTCIValidationError(
                f"temperature_c out of UTCI valid range "
                f"{self.VALID_TEMP_RANGE}: {record.temperature_c}°C (§27)"
            )
        
        if not (self.VALID_RH_RANGE[0] <= record.relative_humidity_pct <= self.VALID_RH_RANGE[1]):
            raise UTCIValidationError(
                f"relative_humidity_pct out of UTCI valid range "
                f"{self.VALID_RH_RANGE}: {record.relative_humidity_pct}% (§27)"
            )
        
        if not (0.0 <= record.wind_speed_ms <= 50.0):  # Extended beyond UTCI valid for catching errors
            raise UTCIValidationError(
                f"wind_speed_ms out of plausible range: {record.wind_speed_ms} m/s (§27)"
            )
        
        if record.solar_radiation_wm2 is not None:
            if not (0.0 <= record.solar_radiation_wm2 <= 1500.0):
                raise UTCIValidationError(
                    f"solar_radiation_wm2 out of plausible range: "
                    f"{record.solar_radiation_wm2} W/m² (§27)"
                )

    # ------------------------------------------------------------------
    # Psychrometric calculations
    # ------------------------------------------------------------------
    def _saturation_vapor_pressure(self, temp_c: float) -> float:
        """
        Saturation vapor pressure using Magnus formula.
        Returns pressure in Pa.
        """
        return 610.78 * math.exp((17.27 * temp_c) / (temp_c + 237.3))

    def _vapor_pressure_from_rh(self, temp_c: float, rh_pct: float) -> float:
        """Calculate vapor pressure from temperature and RH in Pa."""
        es = self._saturation_vapor_pressure(temp_c)
        return (rh_pct / 100.0) * es

    def _estimate_mean_radiant_temp(self,
                                    temp_c: float,
                                    solar_wm2: float,
                                    wind_ms: float) -> float:
        """
        Estimate mean radiant temperature from solar radiation.
        
        Simplified approximation for outdoor conditions.
        More accurate methods require surface albedo, sky view factor, etc.
        
        Reference: ISO 7726 / empirical approximations
        """
        # Simplified model: Tmrt increases above Ta based on solar absorption
        # Assumes standing person, average clothing absorptivity ~0.7
        
        # Solar altitude and geometry effects ignored for simplification
        # Typical approximation: ΔT ≈ solar_absorbed / (h_conv + h_rad)
        
        absorptivity = 0.7  # Typical clothing
        area_factor = 0.06  # Effective area ratio for standing person
        
        # Convective heat transfer coefficient (simplified)
        h_conv = 8.3 * (wind_ms ** 0.6)
        h_conv = max(h_conv, 4.0)  # Minimum natural convection
        
        # Radiative heat transfer coefficient (linearized)
        h_rad = 4.7  # Typical for human skin/clothing temperature
        
        # Temperature increase due to solar absorption
        delta_t = (absorptivity * area_factor * solar_wm2) / (h_conv + h_rad)
        
        return temp_c + delta_t

    # ------------------------------------------------------------------
    # UTCI polynomial approximation (COST Action 730)
    # ------------------------------------------------------------------
    def _utci_polynomial(self,
                        ta: float,
                        va: float,
                        pa: float,
                        tmrt: float) -> float:
        """
        UTCI polynomial approximation.
        
        Parameters:
        -----------
        ta : float
            Air temperature (°C)
        va : float
            Wind speed at 10m height (m/s)
        pa : float
            Water vapor pressure (Pa)
        tmrt : float
            Mean radiant temperature (°C)
            
        Returns:
        --------
        utci : float
            Universal Thermal Climate Index (°C)
            
        Reference:
        ----------
        Bröde P. et al. (2012), Int J Biometeorol 56:481-494
        6th order polynomial regression
        """
        # Ensure wind speed is at least 0.5 m/s (UTCI requirement)
        va = max(va, 0.5)
        
        # Delta between mean radiant and air temperature
        Dtmrt = tmrt - ta
        
        # Convert vapor pressure from Pa to kPa for polynomial
        pa_kpa = pa / 1000.0
        
        # UTCI polynomial coefficients (6th order)
        # This is the official COST Action 730 approximation
        
        utci = ta + \
            0.607562052 + \
            -0.0227712343 * ta + \
            8.06470249e-4 * ta * ta + \
            -1.54271372e-4 * ta * ta * ta + \
            -3.24651735e-6 * ta * ta * ta * ta + \
            7.32602852e-8 * ta * ta * ta * ta * ta + \
            1.35959073e-9 * ta * ta * ta * ta * ta * ta + \
            -2.25836520 * va + \
            0.0880326035 * ta * va + \
            0.00216844454 * ta * ta * va + \
            -1.53347087e-5 * ta * ta * ta * va + \
            -5.72983704e-7 * ta * ta * ta * ta * va + \
            -2.55090145e-9 * ta * ta * ta * ta * ta * va + \
            -0.751269505 * va * va + \
            -0.00408350271 * ta * va * va + \
            -5.21670675e-5 * ta * ta * va * va + \
            1.94544667e-6 * ta * ta * ta * va * va + \
            1.14099531e-8 * ta * ta * ta * ta * va * va + \
            0.158137256 * va * va * va + \
            -6.57263143e-5 * ta * va * va * va + \
            2.22697524e-7 * ta * ta * va * va * va + \
            -4.16117031e-8 * ta * ta * ta * va * va * va + \
            -0.0127762753 * va * va * va * va + \
            9.66891875e-6 * ta * va * va * va * va + \
            2.52785852e-9 * ta * ta * va * va * va * va + \
            4.56306672e-4 * va * va * va * va * va + \
            -1.74202546e-7 * ta * va * va * va * va * va + \
            -5.91491269e-6 * va * va * va * va * va * va + \
            0.398374029 * Dtmrt + \
            1.83945314e-4 * ta * Dtmrt + \
            -1.73754510e-4 * ta * ta * Dtmrt + \
            -7.60781159e-7 * ta * ta * ta * Dtmrt + \
            3.77830287e-8 * ta * ta * ta * ta * Dtmrt + \
            5.43079673e-10 * ta * ta * ta * ta * ta * Dtmrt + \
            -0.0200518269 * va * Dtmrt + \
            8.92859837e-4 * ta * va * Dtmrt + \
            3.45433048e-6 * ta * ta * va * Dtmrt + \
            -3.77925774e-7 * ta * ta * ta * va * Dtmrt + \
            -1.69699377e-9 * ta * ta * ta * ta * va * Dtmrt + \
            1.69992415e-4 * va * va * Dtmrt + \
            -4.99204314e-5 * ta * va * va * Dtmrt + \
            2.47417178e-7 * ta * ta * va * va * Dtmrt + \
            1.07596466e-8 * ta * ta * ta * va * va * Dtmrt + \
            8.49242932e-5 * va * va * va * Dtmrt + \
            1.35191328e-6 * ta * va * va * va * Dtmrt + \
            -6.21531254e-9 * ta * ta * va * va * va * Dtmrt + \
            -4.99410301e-6 * va * va * va * va * Dtmrt + \
            -1.89489258e-8 * ta * va * va * va * va * Dtmrt + \
            8.15300114e-8 * va * va * va * va * va * Dtmrt + \
            7.55043090e-4 * Dtmrt * Dtmrt + \
            -5.65095215e-5 * ta * Dtmrt * Dtmrt + \
            -4.52166564e-7 * ta * ta * Dtmrt * Dtmrt + \
            2.46688878e-8 * ta * ta * ta * Dtmrt * Dtmrt + \
            2.42674348e-10 * ta * ta * ta * ta * Dtmrt * Dtmrt + \
            1.54547250e-4 * va * Dtmrt * Dtmrt + \
            5.24110970e-6 * ta * va * Dtmrt * Dtmrt + \
            -8.75874982e-8 * ta * ta * va * Dtmrt * Dtmrt + \
            -1.50743064e-9 * ta * ta * ta * va * Dtmrt * Dtmrt + \
            -1.56236307e-5 * va * va * Dtmrt * Dtmrt + \
            -1.33895614e-7 * ta * va * va * Dtmrt * Dtmrt + \
            2.49709824e-9 * ta * ta * va * va * Dtmrt * Dtmrt + \
            6.51711721e-7 * va * va * va * Dtmrt * Dtmrt + \
            1.94960053e-9 * ta * va * va * va * Dtmrt * Dtmrt + \
            -1.00361113e-8 * va * va * va * va * Dtmrt * Dtmrt + \
            -1.21206673e-5 * Dtmrt * Dtmrt * Dtmrt + \
            -2.18203660e-7 * ta * Dtmrt * Dtmrt * Dtmrt + \
            7.51269482e-9 * ta * ta * Dtmrt * Dtmrt * Dtmrt + \
            9.79063848e-11 * ta * ta * ta * Dtmrt * Dtmrt * Dtmrt + \
            1.25006734e-6 * va * Dtmrt * Dtmrt * Dtmrt + \
            -1.81584736e-9 * ta * va * Dtmrt * Dtmrt * Dtmrt + \
            -3.52197671e-10 * ta * ta * va * Dtmrt * Dtmrt * Dtmrt + \
            -3.36514630e-8 * va * va * Dtmrt * Dtmrt * Dtmrt + \
            1.35908359e-10 * ta * va * va * Dtmrt * Dtmrt * Dtmrt + \
            4.17032620e-10 * va * va * va * Dtmrt * Dtmrt * Dtmrt + \
            -1.30369025e-9 * Dtmrt * Dtmrt * Dtmrt * Dtmrt + \
            4.13908461e-10 * ta * Dtmrt * Dtmrt * Dtmrt * Dtmrt + \
            9.22652254e-12 * ta * ta * Dtmrt * Dtmrt * Dtmrt * Dtmrt + \
            -5.08220384e-9 * va * Dtmrt * Dtmrt * Dtmrt * Dtmrt + \
            -2.24730961e-11 * ta * va * Dtmrt * Dtmrt * Dtmrt * Dtmrt + \
            1.17139133e-10 * va * va * Dtmrt * Dtmrt * Dtmrt * Dtmrt + \
            6.62154879e-10 * Dtmrt * Dtmrt * Dtmrt * Dtmrt * Dtmrt + \
            4.03863260e-13 * ta * Dtmrt * Dtmrt * Dtmrt * Dtmrt * Dtmrt + \
            1.95087203e-12 * va * Dtmrt * Dtmrt * Dtmrt * Dtmrt * Dtmrt + \
            -4.73602469e-12 * Dtmrt * Dtmrt * Dtmrt * Dtmrt * Dtmrt * Dtmrt + \
            5.12733497 * pa_kpa + \
            -0.312788561 * ta * pa_kpa + \
            -0.0196701861 * ta * ta * pa_kpa + \
            9.99690870e-4 * ta * ta * ta * pa_kpa + \
            9.51738512e-6 * ta * ta * ta * ta * pa_kpa + \
            -4.66426341e-7 * ta * ta * ta * ta * ta * pa_kpa + \
            0.548050612 * va * pa_kpa + \
            -0.00330552823 * ta * va * pa_kpa + \
            -0.00164119440 * ta * ta * va * pa_kpa + \
            -5.16670694e-6 * ta * ta * ta * va * pa_kpa + \
            9.52692432e-7 * ta * ta * ta * ta * va * pa_kpa + \
            -0.0429223622 * va * va * pa_kpa + \
            0.00500845667 * ta * va * va * pa_kpa + \
            1.00601257e-6 * ta * ta * va * va * pa_kpa + \
            -1.81748644e-6 * ta * ta * ta * va * va * pa_kpa + \
            -1.25813502e-3 * va * va * va * pa_kpa + \
            -1.79330391e-4 * ta * va * va * va * pa_kpa + \
            2.34994441e-6 * ta * ta * va * va * va * pa_kpa + \
            1.29735808e-4 * va * va * va * va * pa_kpa + \
            1.29064870e-6 * ta * va * va * va * va * pa_kpa + \
            -2.28558686e-6 * va * va * va * va * va * pa_kpa + \
            -0.0369476348 * Dtmrt * pa_kpa + \
            0.00162325322 * ta * Dtmrt * pa_kpa + \
            -3.14279680e-5 * ta * ta * Dtmrt * pa_kpa + \
            2.59835559e-6 * ta * ta * ta * Dtmrt * pa_kpa + \
            -4.77136523e-8 * ta * ta * ta * ta * Dtmrt * pa_kpa + \
            8.64203390e-3 * va * Dtmrt * pa_kpa + \
            -6.87405181e-4 * ta * va * Dtmrt * pa_kpa + \
            -9.13863872e-6 * ta * ta * va * Dtmrt * pa_kpa + \
            5.15916806e-7 * ta * ta * ta * va * Dtmrt * pa_kpa + \
            -3.59217476e-5 * va * va * Dtmrt * pa_kpa + \
            3.28696511e-5 * ta * va * va * Dtmrt * pa_kpa + \
            -7.10542454e-7 * ta * ta * va * va * Dtmrt * pa_kpa + \
            -1.24382300e-5 * va * va * va * Dtmrt * pa_kpa + \
            -7.38584400e-9 * ta * va * va * va * Dtmrt * pa_kpa + \
            2.20609296e-7 * va * va * va * va * Dtmrt * pa_kpa + \
            -7.32469180e-4 * Dtmrt * Dtmrt * pa_kpa + \
            -1.87381964e-5 * ta * Dtmrt * Dtmrt * pa_kpa + \
            4.80925239e-6 * ta * ta * Dtmrt * Dtmrt * pa_kpa + \
            -8.75492040e-8 * ta * ta * ta * Dtmrt * Dtmrt * pa_kpa + \
            2.77862930e-5 * va * Dtmrt * Dtmrt * pa_kpa + \
            -5.06004592e-6 * ta * va * Dtmrt * Dtmrt * pa_kpa + \
            1.14325367e-7 * ta * ta * va * Dtmrt * Dtmrt * pa_kpa + \
            2.53016723e-6 * va * va * Dtmrt * Dtmrt * pa_kpa + \
            -1.72857035e-8 * ta * va * va * Dtmrt * Dtmrt * pa_kpa + \
            -3.95079398e-8 * va * va * va * Dtmrt * Dtmrt * pa_kpa + \
            -3.59413173e-7 * Dtmrt * Dtmrt * Dtmrt * pa_kpa + \
            7.04388046e-7 * ta * Dtmrt * Dtmrt * Dtmrt * pa_kpa + \
            -1.89309167e-8 * ta * ta * Dtmrt * Dtmrt * Dtmrt * pa_kpa + \
            -4.79768731e-7 * va * Dtmrt * Dtmrt * Dtmrt * pa_kpa + \
            7.96079978e-9 * ta * va * Dtmrt * Dtmrt * Dtmrt * pa_kpa + \
            1.62897058e-9 * va * va * Dtmrt * Dtmrt * Dtmrt * pa_kpa + \
            3.94367674e-8 * Dtmrt * Dtmrt * Dtmrt * Dtmrt * pa_kpa + \
            -1.18566247e-9 * ta * Dtmrt * Dtmrt * Dtmrt * Dtmrt * pa_kpa + \
            3.34678041e-10 * va * Dtmrt * Dtmrt * Dtmrt * Dtmrt * pa_kpa + \
            -1.15606447e-10 * Dtmrt * Dtmrt * Dtmrt * Dtmrt * Dtmrt * pa_kpa + \
            -2.80626406 * pa_kpa * pa_kpa + \
            0.548712484 * ta * pa_kpa * pa_kpa + \
            -0.00399428410 * ta * ta * pa_kpa * pa_kpa + \
            -9.54009191e-4 * ta * ta * ta * pa_kpa * pa_kpa + \
            1.93090978e-5 * ta * ta * ta * ta * pa_kpa * pa_kpa + \
            -0.308806365 * va * pa_kpa * pa_kpa + \
            0.0116952364 * ta * va * pa_kpa * pa_kpa + \
            4.95271903e-4 * ta * ta * va * pa_kpa * pa_kpa + \
            -1.90710882e-5 * ta * ta * ta * va * pa_kpa * pa_kpa + \
            0.00210787756 * va * va * pa_kpa * pa_kpa + \
            -6.98445738e-4 * ta * va * va * pa_kpa * pa_kpa + \
            2.30109073e-5 * ta * ta * va * va * pa_kpa * pa_kpa + \
            4.17856590e-4 * va * va * va * pa_kpa * pa_kpa + \
            -1.27043871e-5 * ta * va * va * va * pa_kpa * pa_kpa + \
            -3.04620472e-6 * va * va * va * va * pa_kpa * pa_kpa + \
            0.0514507424 * Dtmrt * pa_kpa * pa_kpa + \
            -0.00432510997 * ta * Dtmrt * pa_kpa * pa_kpa + \
            8.99281156e-5 * ta * ta * Dtmrt * pa_kpa * pa_kpa + \
            -7.14663943e-7 * ta * ta * ta * Dtmrt * pa_kpa * pa_kpa + \
            -2.66016305e-4 * va * Dtmrt * pa_kpa * pa_kpa + \
            2.63789586e-4 * ta * va * Dtmrt * pa_kpa * pa_kpa + \
            -7.01199003e-6 * ta * ta * va * Dtmrt * pa_kpa * pa_kpa + \
            -1.06823306e-4 * va * va * Dtmrt * pa_kpa * pa_kpa + \
            3.61341136e-6 * ta * va * va * Dtmrt * pa_kpa * pa_kpa + \
            2.29748967e-7 * va * va * va * Dtmrt * pa_kpa * pa_kpa + \
            3.04788893e-4 * Dtmrt * Dtmrt * pa_kpa * pa_kpa + \
            -6.42070836e-5 * ta * Dtmrt * Dtmrt * pa_kpa * pa_kpa + \
            1.16257971e-6 * ta * ta * Dtmrt * Dtmrt * pa_kpa * pa_kpa + \
            7.68023384e-6 * va * Dtmrt * Dtmrt * pa_kpa * pa_kpa + \
            -5.47446896e-7 * ta * va * Dtmrt * Dtmrt * pa_kpa * pa_kpa + \
            -3.59937910e-8 * va * va * Dtmrt * Dtmrt * pa_kpa * pa_kpa + \
            -4.36497725e-6 * Dtmrt * Dtmrt * Dtmrt * pa_kpa * pa_kpa + \
            1.68737969e-7 * ta * Dtmrt * Dtmrt * Dtmrt * pa_kpa * pa_kpa + \
            2.67489271e-8 * va * Dtmrt * Dtmrt * Dtmrt * pa_kpa * pa_kpa + \
            3.23926897e-9 * Dtmrt * Dtmrt * Dtmrt * Dtmrt * pa_kpa * pa_kpa + \
            -0.0353874123 * pa_kpa * pa_kpa * pa_kpa + \
            -0.221201190 * ta * pa_kpa * pa_kpa * pa_kpa + \
            0.0155126038 * ta * ta * pa_kpa * pa_kpa * pa_kpa + \
            -2.63917279e-4 * ta * ta * ta * pa_kpa * pa_kpa * pa_kpa + \
            0.0453433455 * va * pa_kpa * pa_kpa * pa_kpa + \
            -0.00432943862 * ta * va * pa_kpa * pa_kpa * pa_kpa + \
            1.45389826e-4 * ta * ta * va * pa_kpa * pa_kpa * pa_kpa + \
            2.17508610e-4 * va * va * pa_kpa * pa_kpa * pa_kpa + \
            -6.66724702e-5 * ta * va * va * pa_kpa * pa_kpa * pa_kpa + \
            3.33217140e-5 * va * va * va * pa_kpa * pa_kpa * pa_kpa + \
            -0.00226921615 * Dtmrt * pa_kpa * pa_kpa * pa_kpa + \
            3.80261982e-4 * ta * Dtmrt * pa_kpa * pa_kpa * pa_kpa + \
            -5.45314314e-9 * ta * ta * Dtmrt * pa_kpa * pa_kpa * pa_kpa + \
            -7.96355448e-4 * va * Dtmrt * pa_kpa * pa_kpa * pa_kpa + \
            2.53458034e-5 * ta * va * Dtmrt * pa_kpa * pa_kpa * pa_kpa + \
            -6.31223658e-6 * va * va * Dtmrt * pa_kpa * pa_kpa * pa_kpa + \
            3.02122035e-4 * Dtmrt * Dtmrt * pa_kpa * pa_kpa * pa_kpa + \
            -4.77403547e-6 * ta * Dtmrt * Dtmrt * pa_kpa * pa_kpa * pa_kpa + \
            1.73825715e-6 * va * Dtmrt * Dtmrt * pa_kpa * pa_kpa * pa_kpa + \
            -4.09087898e-7 * Dtmrt * Dtmrt * Dtmrt * pa_kpa * pa_kpa * pa_kpa + \
            0.614155345 * pa_kpa * pa_kpa * pa_kpa * pa_kpa + \
            -0.0616755931 * ta * pa_kpa * pa_kpa * pa_kpa * pa_kpa + \
            0.00133374846 * ta * ta * pa_kpa * pa_kpa * pa_kpa * pa_kpa + \
            0.00355375387 * va * pa_kpa * pa_kpa * pa_kpa * pa_kpa + \
            -5.13027851e-4 * ta * va * pa_kpa * pa_kpa * pa_kpa * pa_kpa + \
            1.02449757e-4 * va * va * pa_kpa * pa_kpa * pa_kpa * pa_kpa + \
            -0.00148526421 * Dtmrt * pa_kpa * pa_kpa * pa_kpa * pa_kpa + \
            -4.11469183e-5 * ta * Dtmrt * pa_kpa * pa_kpa * pa_kpa * pa_kpa + \
            -6.80434415e-6 * va * Dtmrt * pa_kpa * pa_kpa * pa_kpa * pa_kpa + \
            -9.77675906e-6 * Dtmrt * Dtmrt * pa_kpa * pa_kpa * pa_kpa * pa_kpa + \
            0.0882773108 * pa_kpa * pa_kpa * pa_kpa * pa_kpa * pa_kpa + \
            -0.00301859306 * ta * pa_kpa * pa_kpa * pa_kpa * pa_kpa * pa_kpa + \
            0.00104452989 * va * pa_kpa * pa_kpa * pa_kpa * pa_kpa * pa_kpa + \
            2.47090539e-4 * Dtmrt * pa_kpa * pa_kpa * pa_kpa * pa_kpa * pa_kpa + \
            0.00148348065 * pa_kpa * pa_kpa * pa_kpa * pa_kpa * pa_kpa * pa_kpa

        return utci

    # ------------------------------------------------------------------
    # Stress categorization
    # ------------------------------------------------------------------
    def get_stress_category(self, utci_c: float) -> str:
        """
        Determine thermal stress category from UTCI value.
        
        Based on COST Action 730 standard categories.
        """
        for min_val, max_val, category in self.STRESS_CATEGORIES:
            if min_val <= utci_c < max_val:
                return category
        return "UNKNOWN"

    # ------------------------------------------------------------------
    # Public interface (§20 output contract compatibility)
    # ------------------------------------------------------------------
    def calculate(self, record: CanonicalThermalInput) -> UTCIDerived:
        """
        Calculate derived utci_c from canonical input.
        
        Returns UTCIDerived with status = INSUFFICIENT_DATA
        if required fields are missing (§25).
        """
        # Strict validation first (§27)
        try:
            if self.enforce_validation:
                self.validate_input(record)
        except UTCIValidationError as exc:
            return UTCIDerived(
                area_id=record.area_id,
                timestamp=record.timestamp,
                utci_c=None,
                thermal_stress_category=None,
                calculation_status="INSUFFICIENT_DATA",
                method_version=f"FAILED-VALIDATION-{exc}",
            )

        try:
            # Get required inputs
            ta = record.temperature_c
            rh = record.relative_humidity_pct
            va = record.wind_speed_ms
            
            # Ensure wind speed meets minimum UTCI requirement
            va = max(va, 0.5)
            
            # Calculate vapor pressure
            pa = self._vapor_pressure_from_rh(ta, rh)
            
            # Determine mean radiant temperature
            if record.solar_radiation_wm2 is not None:
                tmrt = self._estimate_mean_radiant_temp(
                    ta,
                    record.solar_radiation_wm2,
                    va
                )
                tmrt_method = "SOLAR_ESTIMATED"
            else:
                # No solar data: assume Tmrt ≈ Ta (indoor/shade approximation)
                tmrt = ta
                tmrt_method = "ASSUMED_EQUAL_TA"
            
            # Calculate UTCI using polynomial
            utci = self._utci_polynomial(ta, va, pa, tmrt)
            
            # Get stress category
            category = self.get_stress_category(utci)
            
            return UTCIDerived(
                area_id=record.area_id,
                timestamp=record.timestamp,
                utci_c=round(utci, 2),
                thermal_stress_category=category,
                tmrt_method=tmrt_method,
                calculation_status="COMPUTED",
                method_version="COST-Action-730-v1",
            )
            
        except Exception as exc:
            return UTCIDerived(
                area_id=record.area_id,
                timestamp=record.timestamp,
                utci_c=None,
                thermal_stress_category=None,
                calculation_status="OUT_OF_RANGE",
                method_version=f"CALCULATION-ERROR-{exc}",
            )

    # ------------------------------------------------------------------
    # Documentation generator (§4.1, §9, §29)
    # ------------------------------------------------------------------
    def documentation(self) -> Dict[str, Any]:
        """
        Returns machine-readable documentation required by §9.
        """
        return {
            "component": "Thermal Calculation Engine",
            "function": "Universal Thermal Climate Index (UTCI)",
            "contract_version": "0.1",
            "formula_library": "COST Action 730 (6th order polynomial)",
            "formula_reference_urls": [
                "http://www.utci.org/",
                "https://doi.org/10.1007/s00484-011-0454-1"
            ],
            "required_inputs": [
                "temperature_c (float, °C)",
                "relative_humidity_pct (float, %)",
                "wind_speed_ms (float, m/s)"
            ],
            "optional_inputs": [
                "solar_radiation_wm2 (float, W/m²) — for mean radiant temp estimation"
            ],
            "output": {
                "field": "utci_c",
                "unit": "°C",
                "status": "DERIVED (§9)",
                "interpretation": "Equivalent air temperature of reference environment"
            },
            "units_internal": "°C / m/s / Pa / W/m² (§26)",
            "assumptions": [
                "Adaptive clothing insulation based on outdoor temperature",
                "Walking metabolic rate (2.3 MET ≈ 135 W/m²)",
                "Mean radiant temp estimated from solar or assumed = air temp",
                "Standard atmospheric pressure (no altitude correction)",
                "Valid for general outdoor thermal comfort assessment"
            ],
            "applicability_range": {
                "temperature_c": "-50 to +50 °C (COST Action 730 validated)",
                "relative_humidity_pct": "5 to 100%",
                "wind_speed_ms": "0.5 to 30 m/s (minimum 0.5 enforced)",
                "universal": "Valid for all climates and seasons (cold to hot)",
                "caveats": [
                    "Designed for general population outdoor assessment",
                    "Not specific to occupational heat stress (use WBGT)",
                    "Not a direct mortality predictor (§16)",
                    "Environmental hazard component only (§3)"
                ]
            },
            "thermal_stress_categories": {
                cat: f"{min_val}°C to {max_val}°C"
                for min_val, max_val, cat in self.STRESS_CATEGORIES
            },
            "fallback_behaviour": "If required inputs missing -> INSUFFICIENT_DATA; no imputation (§25)",
            "validation_rules_applied": [
                "area_id present (§7)",
                "timestamp present (§7)",
                "temperature_c in -50 to +50 °C (§27)",
                "relative_humidity_pct in 5–100% (§8/§27)",
                "wind_speed_ms in 0–50 m/s (§27)",
                "solar_radiation_wm2 in 0–1500 W/m² if provided (§27)"
            ],
            "advantages_vs_other_indices": [
                "Universal applicability (cold & hot)",
                "Scientifically validated across climates",
                "Accounts for all key meteorological variables",
                "Adaptive clothing model",
                "Widely adopted internationally"
            ],
            "version": "v1"
        }

    # ------------------------------------------------------------------
    # Batch interface
    # ------------------------------------------------------------------
    def calculate_batch(self,
                       records: list[CanonicalThermalInput]) -> list[UTCIDerived]:
        """Calculate UTCI for multiple records."""
        return [self.calculate(r) for r in records]


# ------------------------------------------------------------------
# Module-level convenience functions
# ------------------------------------------------------------------
def compute_utci(
    temperature_c: float,
    relative_humidity_pct: float,
    wind_speed_ms: float,
    solar_radiation_wm2: Optional[float] = None,
    area_id: str = "UNKNOWN",
    timestamp: str = "1970-01-01T00:00:00Z",
) -> UTCIDerived:
    """Quick UTCI calculation."""
    record = CanonicalThermalInput(
        area_id=area_id,
        timestamp=timestamp,
        temperature_c=temperature_c,
        relative_humidity_pct=relative_humidity_pct,
        wind_speed_ms=wind_speed_ms,
        solar_radiation_wm2=solar_radiation_wm2,
    )
    engine = UTCIEngine()
    return engine.calculate(record)


# ------------------------------------------------------------------
# Self-test
# ------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("UTCI Engine Self-Test")
    print("=" * 70)
    
    engine = UTCIEngine()
    
    # Test 1: Hot conditions with solar
    print("\n1. Hot summer day with sun")
    rec1 = CanonicalThermalInput(
        area_id="WARD_017",
        timestamp="2026-05-20T14:00:00+05:30",
        temperature_c=38.0,
        relative_humidity_pct=50.0,
        wind_speed_ms=2.0,
        solar_radiation_wm2=850.0,
    )
    result1 = engine.calculate(rec1)
    print(f"   Input: {rec1.temperature_c}°C, {rec1.relative_humidity_pct}% RH, "
          f"{rec1.wind_speed_ms} m/s, {rec1.solar_radiation_wm2} W/m²")
    print(f"   UTCI: {result1.utci_c}°C")
    print(f"   Category: {result1.thermal_stress_category}")
    print(f"   Tmrt method: {result1.tmrt_method}")
    assert result1.calculation_status == "COMPUTED"
    assert result1.utci_c > 38.0  # Should be higher than air temp
    print("   ✓ PASSED")
    
    # Test 2: No solar data
    print("\n2. No solar radiation data (Tmrt = Ta)")
    rec2 = CanonicalThermalInput(
        area_id="WARD_018",
        timestamp="2026-05-20T14:00:00+05:30",
        temperature_c=35.0,
        relative_humidity_pct=60.0,
        wind_speed_ms=3.0,
        solar_radiation_wm2=None,
    )
    result2 = engine.calculate(rec2)
    print(f"   Input: {rec2.temperature_c}°C, {rec2.relative_humidity_pct}% RH, "
          f"{rec2.wind_speed_ms} m/s, solar=None")
    print(f"   UTCI: {result2.utci_c}°C")
    print(f"   Tmrt method: {result2.tmrt_method}")
    assert result2.tmrt_method == "ASSUMED_EQUAL_TA"
    assert result2.utci_c is not None
    print("   ✓ PASSED")
    
    # Test 3: Cold stress
    print("\n3. Winter conditions (cold stress)")
    rec3 = CanonicalThermalInput(
        area_id="WARD_019",
        timestamp="2026-01-15T08:00:00+05:30",
        temperature_c=-5.0,
        relative_humidity_pct=70.0,
        wind_speed_ms=5.0,
        solar_radiation_wm2=200.0,
    )
    result3 = engine.calculate(rec3)
    print(f"   Input: {rec3.temperature_c}°C, {rec3.relative_humidity_pct}% RH, "
          f"{rec3.wind_speed_ms} m/s")
    print(f"   UTCI: {result3.utci_c}°C")
    print(f"   Category: {result3.thermal_stress_category}")
    assert "COLD" in result3.thermal_stress_category
    print("   ✓ PASSED")
    
    # Test 4: Missing required data (§25)
    print("\n4. INSUFFICIENT_DATA: Missing wind speed (§25)")
    rec4 = CanonicalThermalInput(
        area_id="WARD_020",
        timestamp="2026-05-20T14:00:00+05:30",
        temperature_c=35.0,
        relative_humidity_pct=60.0,
        wind_speed_ms=None,  # Missing!
    )
    result4 = engine.calculate(rec4)
    print(f"   Input: {rec4.temperature_c}°C, {rec4.relative_humidity_pct}% RH, wind=None")
    print(f"   UTCI: {result4.utci_c}")
    print(f"   Status: {result4.calculation_status}")
    assert result4.calculation_status == "INSUFFICIENT_DATA"
    assert result4.utci_c is None
    print("   ✓ PASSED")
    
    # Test 5: Range of conditions
    print("\n5. UTCI across thermal stress spectrum:")
    print(f"   {'Temp (°C)':<12} {'RH %':<8} {'Wind':<8} {'Solar':<10} {'UTCI':<8} {'Category':<25}")
    print("   " + "-" * 85)
    
    scenarios = [
        (-10.0, 70.0, 5.0, 100.0, "Winter windchill"),
        (0.0, 60.0, 2.0, 300.0, "Cool spring"),
        (15.0, 50.0, 1.5, 500.0, "Mild conditions"),
        (25.0, 60.0, 2.0, 700.0, "Warm summer"),
        (35.0, 50.0, 1.5, 900.0, "Hot day"),
        (40.0, 40.0, 1.0, 1000.0, "Extreme heat"),
    ]
    
    for temp, rh, wind, solar, label in scenarios:
        rec = CanonicalThermalInput(
            area_id="TEST",
            timestamp="2026-05-20T14:00:00Z",
            temperature_c=temp,
            relative_humidity_pct=rh,
            wind_speed_ms=wind,
            solar_radiation_wm2=solar,
        )
        res = engine.calculate(rec)
        
        print(f"   {temp:<12.1f} {rh:<8.1f} {wind:<8.1f} {solar:<10.0f} "
              f"{res.utci_c:<8.1f} {res.thermal_stress_category:<25}")
    
    # Test 6: Verify monotonicity
    print("\n6. Verify UTCI increases with temperature")
    temps = [25.0, 30.0, 35.0, 40.0]
    utcis = []
    
    for temp in temps:
        rec = CanonicalThermalInput(
            area_id="TEST",
            timestamp="2026-05-20T14:00:00Z",
            temperature_c=temp,
            relative_humidity_pct=60.0,
            wind_speed_ms=2.0,
            solar_radiation_wm2=700.0,
        )
        res = engine.calculate(rec)
        utcis.append(res.utci_c)
    
    monotonic = all(utcis[i] < utcis[i+1] for i in range(len(utcis)-1))
    print(f"   Temps: {temps}")
    print(f"   UTCIs: {[round(u, 1) for u in utcis]}")
    print(f"   Monotonic: {monotonic}")
    assert monotonic
    print("   ✓ PASSED")
    
    # Test 7: Documentation
    print("\n7. Documentation (§9)")
    docs = engine.documentation()
    print(f"   Formula: {docs['formula_library']}")
    print(f"   Valid range: {docs['applicability_range']['temperature_c']}")
    print(f"   Categories: {len(docs['thermal_stress_categories'])} defined")
    assert "COST Action 730" in docs["formula_library"]
    print("   ✓ PASSED")
    
    print("\n" + "=" * 70)
    print("ALL SELF-TESTS PASSED ✓")
    print("=" * 70)