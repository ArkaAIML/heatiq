"""
HeatIQ Thermal Engine — Human Thermal Stress Index (HTSI)
Data Contract: v0.1  |  Component: Data / Backend / Thermal Engine (§4.1)
Branch: feature/htsi-combined-index

Output schema (§9):
    htsi : float | DERIVED | 0–100

Description:
    HTSI is a composite thermal stress index that combines three validated
    thermal indices — Heat Index (HI), Wet Bulb Globe Temperature (WBGT),
    and Universal Thermal Climate Index (UTCI) — into a single
    dimensionless 0–100 score.

    0   = No thermal stress
    100 = Extreme human thermal stress (life-threatening)

Weights (rationale):
    UTCI  (40%) — Most scientifically rigorous; validated across all climates
                   and seasons; 6th-order COST Action 730 polynomial.
    WBGT  (35%) — ISO 7243 occupational standard; highest relevance to
                   physiological heat load (wet bulb + globe + solar).
    HI    (25%) — NOAA NWS Rothfusz; widely understood public-facing metric;
                   strong humidity–temperature coupling.

Normalization:
    Each index is independently piece-wise normalized to 0–100 using its
    own published risk/threshold boundaries, so that equal-severity conditions
    contribute equal weight regardless of unit differences.

Units (§26):
    Internal: temperature in °C; output: dimensionless 0–100

Fallback (§9, §25):
    If an index cannot be computed (missing inputs), its score is omitted and
    the remaining indices are re-weighted proportionally. Never fabricated.
    If all three fail → HTSI = None, status = INSUFFICIENT_DATA.
"""

from __future__ import annotations

import os
import sys
import math
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Literal

# Ensure HTSI root is on sys.path whether run directly or as a module
_pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _pkg_root not in sys.path:
    sys.path.insert(0, _pkg_root)

from thermal.heat_index import (
    HeatIndexEngine,
    CanonicalThermalInput as HI_Input,
)
from thermal.wbgt import (
    WBGTEngine,
    CanonicalThermalInput as WBGT_Input,
)
from thermal.utci import (
    UTCIEngine,
    CanonicalThermalInput as UTCI_Input,
)


# ── Canonical input ────────────────────────────────────────────────────────

@dataclass
class HTSIInput:
    """
    Unified canonical input for all three thermal engines.
    temperature_c and relative_humidity_pct are always required.
    wind_speed_ms required for UTCI and outdoor WBGT.
    solar_radiation_wm2 improves WBGT and UTCI accuracy.
    """
    area_id: str
    timestamp: str

    # Always required
    temperature_c: float
    relative_humidity_pct: float

    # Required for UTCI; improves WBGT (outdoor)
    wind_speed_ms: Optional[float] = None

    # Improves WBGT (outdoor) and UTCI Tmrt estimate
    solar_radiation_wm2: Optional[float] = None

    # Optional identification
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Optional contextual
    dew_point_c: Optional[float] = None
    population: Optional[int] = None
    elderly_fraction: Optional[float] = None


# ── Output ────────────────────────────────────────────────────────────────

@dataclass
class HTSIDerived:
    """HTSI combined output schema (§9)."""
    area_id: str
    timestamp: str

    # ── Final composite score ────────────────────────────────────────────
    htsi: Optional[float]                  # 0–100, None if insufficient data
    htsi_category: Optional[str]           # LOW / MODERATE / HIGH / VERY_HIGH / EXTREME

    # ── Component scores (0–100 each, before weighting) ─────────────────
    hi_score: Optional[float] = None       # Normalized HI
    wbgt_score: Optional[float] = None     # Normalized WBGT
    utci_score: Optional[float] = None     # Normalized UTCI

    # ── Raw computed index values ────────────────────────────────────────
    heat_index_c: Optional[float] = None
    wbgt_c: Optional[float] = None
    utci_c: Optional[float] = None

    # ── Effective weights used (may differ from nominal if data missing) ─
    weights_used: Dict[str, float] = field(default_factory=dict)

    # ── Status ──────────────────────────────────────────────────────────
    calculation_status: Literal["COMPUTED", "PARTIAL", "INSUFFICIENT_DATA"] = "COMPUTED"
    indices_computed: list = field(default_factory=list)
    indices_skipped: list = field(default_factory=list)
    method_version: str = "HTSI-v1"


# ── Normalization functions ────────────────────────────────────────────────

def _piecewise_linear(value: float, breakpoints: list[tuple[float, float]]) -> float:
    """
    Map a value to 0–100 using piecewise linear interpolation.
    breakpoints: list of (raw_value, normalized_score) in ascending raw_value order.
    Values below first breakpoint → 0. Values above last → 100.
    """
    if value <= breakpoints[0][0]:
        return breakpoints[0][1]
    if value >= breakpoints[-1][0]:
        return 100.0
    for i in range(len(breakpoints) - 1):
        x0, y0 = breakpoints[i]
        x1, y1 = breakpoints[i + 1]
        if x0 <= value <= x1:
            t = (value - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return 100.0


def normalize_heat_index(hi_c: float) -> float:
    """
    Normalize Heat Index (°C) to 0–100.

    Breakpoints derived from NWS Rothfusz risk thresholds:
        <27°C  : No significant heat stress            → 0
        27°C   : Caution begins                        → 15
        33°C   : Extreme Caution begins                → 40
        40°C   : Danger begins                         → 60
        52°C   : Extreme Danger begins                 → 80
        60°C   : Physical limit / lethal zone          → 100
    """
    bp = [
        (20.0,  0.0),
        (27.0, 15.0),
        (33.0, 40.0),
        (40.0, 60.0),
        (52.0, 80.0),
        (60.0, 100.0),
    ]
    return round(_piecewise_linear(hi_c, bp), 2)


def normalize_wbgt(wbgt_c: float) -> float:
    """
    Normalize WBGT (°C) to 0–100.

    Breakpoints derived from ISO 7243:2017 occupational thresholds
    (acclimatized workers, moderate work rate):
        <22°C  : Negligible heat load                 → 0
        22°C   : Low end of concern                   → 10
        28°C   : MINIMAL→LOW risk boundary            → 25
        31°C   : LOW→MODERATE risk boundary           → 50
        32°C   : MODERATE→HIGH risk boundary          → 65
        34°C   : HIGH→EXTREME risk boundary           → 80
        40°C   : Upper physiological limit             → 100
    """
    bp = [
        (18.0,  0.0),
        (22.0, 10.0),
        (28.0, 25.0),
        (31.0, 50.0),
        (32.0, 65.0),
        (34.0, 80.0),
        (40.0, 100.0),
    ]
    return round(_piecewise_linear(wbgt_c, bp), 2)


def normalize_utci(utci_c: float) -> float:
    """
    Normalize UTCI (°C) to 0–100 for heat stress.

    Cold stress (UTCI < 9°C) maps to 0 — HTSI is a heat stress index.
    Breakpoints derived from COST Action 730 thermal stress categories:
        ≤9°C   : No / Cold thermal stress (heat component = 0) → 0
        9°C    : Moderate heat stress begins                    → 0
        26°C   : Strong heat stress begins                      → 25
        32°C   : Very strong heat stress begins                 → 55
        38°C   : Extreme heat stress begins                     → 80
        50°C   : Upper physiological limit                      → 100
    """
    bp = [
        (9.0,   0.0),
        (26.0, 25.0),
        (32.0, 55.0),
        (38.0, 80.0),
        (50.0, 100.0),
    ]
    if utci_c < 9.0:
        return 0.0  # cold or no heat stress
    return round(_piecewise_linear(utci_c, bp), 2)


def _htsi_category(htsi: float) -> str:
    """Map HTSI score to human-readable category."""
    if htsi < 20:
        return "LOW"
    elif htsi < 40:
        return "MODERATE"
    elif htsi < 60:
        return "HIGH"
    elif htsi < 80:
        return "VERY_HIGH"
    else:
        return "EXTREME"


# ── Nominal weights ────────────────────────────────────────────────────────

NOMINAL_WEIGHTS = {
    "utci": 0.40,
    "wbgt": 0.35,
    "hi":   0.25,
}


# ── HTSI Engine ────────────────────────────────────────────────────────────

class HTSIEngine:
    """
    Human Thermal Stress Index (HTSI) Engine.

    Combines Heat Index, WBGT, and UTCI into a single 0–100 score
    using weighted normalization.

    Parameters
    ----------
    hi_weight, wbgt_weight, utci_weight : float
        Nominal weights (must sum to 1.0). If an index cannot be computed,
        the remaining weights are re-normalized proportionally.
    """

    def __init__(
        self,
        hi_weight: float = 0.25,
        wbgt_weight: float = 0.35,
        utci_weight: float = 0.40,
        enforce_validation: bool = False,
    ):
        total = hi_weight + wbgt_weight + utci_weight
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Weights must sum to 1.0, got {total:.4f}")
        self.w_hi   = hi_weight
        self.w_wbgt = wbgt_weight
        self.w_utci = utci_weight
        self.enforce_validation = enforce_validation

        self._hi_engine   = HeatIndexEngine(enforce_validation=enforce_validation)
        self._wbgt_engine = WBGTEngine(enforce_validation=enforce_validation, prefer_outdoor=True)
        self._utci_engine = UTCIEngine(enforce_validation=enforce_validation)

    def calculate(self, record: HTSIInput) -> HTSIDerived:
        """Compute HTSI from a unified input record."""

        # Base requirement: temperature and relative humidity must be present
        if (record.temperature_c is None or 
            (isinstance(record.temperature_c, float) and math.isnan(record.temperature_c)) or
            record.relative_humidity_pct is None or 
            (isinstance(record.relative_humidity_pct, float) and math.isnan(record.relative_humidity_pct))):
            return HTSIDerived(
                area_id=record.area_id,
                timestamp=record.timestamp,
                htsi=None,
                htsi_category=None,
                calculation_status="INSUFFICIENT_DATA",
                indices_computed=[],
                indices_skipped=["HI", "WBGT", "UTCI"],
            )

        scores = {}
        raw_values = {}
        skipped = []
        computed = []

        # ── 1. Heat Index ──────────────────────────────────────────────
        hi_rec = HI_Input(
            area_id=record.area_id,
            timestamp=record.timestamp,
            temperature_c=record.temperature_c,
            relative_humidity_pct=record.relative_humidity_pct,
            latitude=record.latitude,
            longitude=record.longitude,
        )
        hi_res = self._hi_engine.calculate(hi_rec)
        if hi_res.calculation_status == "COMPUTED" and hi_res.heat_index_c is not None:
            raw_values["hi"] = hi_res.heat_index_c
            scores["hi"] = normalize_heat_index(hi_res.heat_index_c)
            computed.append("HI")
        else:
            skipped.append("HI")

        # ── 2. WBGT ────────────────────────────────────────────────────
        wbgt_rec = WBGT_Input(
            area_id=record.area_id,
            timestamp=record.timestamp,
            temperature_c=record.temperature_c,
            relative_humidity_pct=record.relative_humidity_pct,
            wind_speed_ms=record.wind_speed_ms,
            solar_radiation_wm2=record.solar_radiation_wm2,
            latitude=record.latitude,
            longitude=record.longitude,
            dew_point_c=record.dew_point_c,
        )
        wbgt_res = self._wbgt_engine.calculate(wbgt_rec)
        if wbgt_res.calculation_status == "COMPUTED" and wbgt_res.wbgt_c is not None:
            raw_values["wbgt"] = wbgt_res.wbgt_c
            scores["wbgt"] = normalize_wbgt(wbgt_res.wbgt_c)
            computed.append("WBGT")
        else:
            skipped.append("WBGT")

        # ── 3. UTCI ────────────────────────────────────────────────────
        if record.wind_speed_ms is not None:
            utci_rec = UTCI_Input(
                area_id=record.area_id,
                timestamp=record.timestamp,
                temperature_c=record.temperature_c,
                relative_humidity_pct=record.relative_humidity_pct,
                wind_speed_ms=record.wind_speed_ms,
                solar_radiation_wm2=record.solar_radiation_wm2,
                latitude=record.latitude,
                longitude=record.longitude,
            )
            utci_res = self._utci_engine.calculate(utci_rec)
            if utci_res.calculation_status == "COMPUTED" and utci_res.utci_c is not None:
                raw_values["utci"] = utci_res.utci_c
                scores["utci"] = normalize_utci(utci_res.utci_c)
                computed.append("UTCI")
            else:
                skipped.append("UTCI")
        else:
            skipped.append("UTCI (no wind_speed_ms)")

        # ── Insufficient data ──────────────────────────────────────────
        if not scores:
            return HTSIDerived(
                area_id=record.area_id,
                timestamp=record.timestamp,
                htsi=None,
                htsi_category=None,
                calculation_status="INSUFFICIENT_DATA",
                indices_computed=[],
                indices_skipped=skipped,
            )

        # ── Re-normalize weights for missing indices ───────────────────
        nominal = {"hi": self.w_hi, "wbgt": self.w_wbgt, "utci": self.w_utci}
        active_weights_raw = {k: v for k, v in nominal.items() if k in scores}
        total_active = sum(active_weights_raw.values())
        effective_weights = {k: v / total_active for k, v in active_weights_raw.items()}

        # ── Weighted HTSI ─────────────────────────────────────────────
        htsi = sum(scores[k] * effective_weights[k] for k in scores)
        htsi = round(min(max(htsi, 0.0), 100.0), 2)

        status = "COMPUTED" if not skipped else "PARTIAL"

        return HTSIDerived(
            area_id=record.area_id,
            timestamp=record.timestamp,
            htsi=htsi,
            htsi_category=_htsi_category(htsi),
            hi_score=scores.get("hi"),
            wbgt_score=scores.get("wbgt"),
            utci_score=scores.get("utci"),
            heat_index_c=raw_values.get("hi"),
            wbgt_c=raw_values.get("wbgt"),
            utci_c=raw_values.get("utci"),
            weights_used={
                "HI":   round(effective_weights.get("hi",   0) * 100, 1),
                "WBGT": round(effective_weights.get("wbgt", 0) * 100, 1),
                "UTCI": round(effective_weights.get("utci", 0) * 100, 1),
            },
            calculation_status=status,
            indices_computed=computed,
            indices_skipped=skipped,
            method_version="HTSI-v1",
        )

    def documentation(self) -> Dict[str, Any]:
        return {
            "component": "HTSI — Human Thermal Stress Index",
            "contract_version": "0.1",
            "formula": "Weighted average of normalized HI, WBGT, UTCI scores",
            "weights_nominal": {
                "HI":   f"{self.w_hi * 100:.0f}%",
                "WBGT": f"{self.w_wbgt * 100:.0f}%",
                "UTCI": f"{self.w_utci * 100:.0f}%",
            },
            "output_range": "0 (no stress) to 100 (extreme, life-threatening)",
            "categories": {
                "LOW":       "0–20  : Safe / minimal thermal concern",
                "MODERATE":  "20–40 : Caution — fatigue possible",
                "HIGH":      "40–60 : Extreme caution — heat illness risk",
                "VERY_HIGH": "60–80 : Danger — heat cramps/exhaustion likely",
                "EXTREME":   "80–100: Extreme danger — heat stroke imminent",
            },
            "fallback": "If index unavailable, weights re-normalized; §25 no fabrication",
        }


# ── Convenience function ───────────────────────────────────────────────────

def compute_htsi(
    temperature_c: float,
    relative_humidity_pct: float,
    wind_speed_ms: Optional[float] = None,
    solar_radiation_wm2: Optional[float] = None,
    area_id: str = "UNKNOWN",
    timestamp: str = "1970-01-01T00:00:00Z",
) -> HTSIDerived:
    """Quick HTSI calculation."""
    rec = HTSIInput(
        area_id=area_id,
        timestamp=timestamp,
        temperature_c=temperature_c,
        relative_humidity_pct=relative_humidity_pct,
        wind_speed_ms=wind_speed_ms,
        solar_radiation_wm2=solar_radiation_wm2,
    )
    return HTSIEngine().calculate(rec)


# ── Self-test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    engine = HTSIEngine()
    SEP = "=" * 72

    print(f"\n{SEP}")
    print("  HTSI — Human Thermal Stress Index  |  Self-Test")
    print(f"  Weights: HI={engine.w_hi*100:.0f}%  WBGT={engine.w_wbgt*100:.0f}%  UTCI={engine.w_utci*100:.0f}%")
    print(SEP)

    scenarios = [
        ("Comfortable (AC room)",       22.0,  55.0, None, None),
        ("Warm day, mild humidity",     28.0,  60.0,  2.0,  300.0),
        ("Hot day, moderate sun",       33.0,  65.0,  1.5,  700.0),
        ("Very hot, high humidity",     38.0,  70.0,  1.5,  800.0),
        ("Extreme heat + full sun",     42.0,  60.0,  1.0, 1000.0),
        ("Night in Cuttack (live)",     27.2,  94.0,  1.8,    0.0),
        ("Delhi daytime (live)",        29.7,  83.0,  2.0,  400.0),
    ]

    print(f"\n  {'Scenario':<30} {'Temp':>5} {'RH':>5}  "
          f"{'HI':>7} {'WBGT':>7} {'UTCI':>7}  "
          f"{'HI_s':>5} {'WB_s':>5} {'UC_s':>5}  "
          f"{'HTSI':>6}  {'Category'}")
    print("  " + "-" * 106)

    for label, temp, rh, wind, solar in scenarios:
        rec = HTSIInput(
            area_id="TEST", timestamp="2026-08-26T14:00:00Z",
            temperature_c=temp, relative_humidity_pct=rh,
            wind_speed_ms=wind, solar_radiation_wm2=solar,
        )
        r = engine.calculate(rec)
        hi_s   = f"{r.hi_score:.0f}"   if r.hi_score   is not None else " N/A"
        wb_s   = f"{r.wbgt_score:.0f}" if r.wbgt_score  is not None else " N/A"
        uc_s   = f"{r.utci_score:.0f}" if r.utci_score  is not None else " N/A"
        hi_c   = f"{r.heat_index_c:.1f}" if r.heat_index_c is not None else " N/A"
        wbgt_c = f"{r.wbgt_c:.1f}"  if r.wbgt_c  is not None else " N/A"
        utci_c = f"{r.utci_c:.1f}"  if r.utci_c  is not None else " N/A"
        htsi   = f"{r.htsi:.1f}"    if r.htsi    is not None else " N/A"

        print(f"  {label:<30} {temp:>4.1f}°C {rh:>4.0f}%  "
              f"{hi_c:>7} {wbgt_c:>7} {utci_c:>7}  "
              f"{hi_s:>5} {wb_s:>5} {uc_s:>5}  "
              f"{htsi:>6}  {r.htsi_category}")

    print(f"\n{SEP}")
    print("  HTSI Category Scale:")
    print("    0–20  : LOW        (Safe)")
    print("   20–40  : MODERATE   (Caution — fatigue possible)")
    print("   40–60  : HIGH       (Extreme Caution — heat illness risk)")
    print("   60–80  : VERY_HIGH  (Danger — heat cramps/exhaustion likely)")
    print("   80–100 : EXTREME    (Life-threatening — heat stroke imminent)")
    print(f"{SEP}\n")
