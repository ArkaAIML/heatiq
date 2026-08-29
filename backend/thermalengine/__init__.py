"""
HeatIQ Thermal Engine

Contract-compliant module for calculating physical thermal indices and human thermal stress:
- Heat Index (NOAA NWS Rothfusz 1990)
- Wet Bulb Globe Temperature (ISO 7243:2017 / Liljegren et al. 2008)
- Universal Thermal Climate Index (COST Action 730 6th-order polynomial)
- Human Thermal Stress Index (Composite 0-100 score & risk categories)

Primary Contract Interface:
- `calculate_thermal_indices()`: Primary function for computing structured thermal outputs from structured inputs.
- `ThermalEngineService`: Service boundary class for single/batch processing.
- `ThermalInput`: Canonical environmental input record (§7, §8, §26).
- `ThermalOutput`: Canonical structured output record (§9, §20, §25, §28).
- `ThermalInputValidationError`: Exception raised for schema / range violations (§27).
"""

# ── Primary Public Contract Boundary ─────────────────────────────────────────
from .schemas import (
    ThermalInput,
    ThermalOutput,
    ThermalInputValidationError,
)
from .service import (
    ThermalEngineService,
    calculate_thermal_indices,
    calculate_thermal_indices_batch,
)

# ── Computational Engines & Implementation Models ───────────────────────────
from .heat_index import (
    HeatIndexEngine,
    CanonicalThermalInput as HeatIndexInput,
    HeatIndexDerived,
    HeatIndexValidationError,
    compute_heat_index,
)
from .wbgt import (
    WBGTEngine,
    CanonicalThermalInput as WBGTInput,
    WBGTDerived,
    WBGTValidationError,
    compute_wbgt_outdoor,
    compute_wbgt_indoor,
)
from .utci import (
    UTCIEngine,
    CanonicalThermalInput as UTCIInput,
    UTCIDerived,
    UTCIValidationError,
    compute_utci,
)
from .htsi import (
    HTSIEngine,
    HTSIInput,
    HTSIDerived,
    compute_htsi,
    normalize_heat_index,
    normalize_wbgt,
    normalize_utci,
    NOMINAL_WEIGHTS,
)

# Alias for backward compatibility
CanonicalThermalInput = ThermalInput

__all__ = [
    # ── Recommended Public API ──
    "calculate_thermal_indices",
    "calculate_thermal_indices_batch",
    "ThermalEngineService",
    "ThermalInput",
    "ThermalOutput",
    "ThermalInputValidationError",

    # ── Underlying Computational Components ──
    "HTSIEngine",
    "HeatIndexEngine",
    "WBGTEngine",
    "UTCIEngine",

    # ── Low-level Schemas & DTOs ──
    "CanonicalThermalInput",
    "HTSIInput",
    "HTSIDerived",
    "HeatIndexInput",
    "HeatIndexDerived",
    "WBGTInput",
    "WBGTDerived",
    "UTCIInput",
    "UTCIDerived",

    # ── Direct Calculation Functions ──
    "compute_htsi",
    "compute_heat_index",
    "compute_wbgt_outdoor",
    "compute_wbgt_indoor",
    "compute_utci",

    # ── Normalization Utilities ──
    "normalize_heat_index",
    "normalize_wbgt",
    "normalize_utci",
    "NOMINAL_WEIGHTS",
]
