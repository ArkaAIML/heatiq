"""
Tests for HeatIQ Thermal Engine — Heat Index
Branch: feature/thermal-indices
Contract checks: §4.1, §8, §9, §25, §27, §26
"""

import os
import sys
import pytest

_htsi_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _htsi_root not in sys.path:
    sys.path.insert(0, _htsi_root)

from thermal.heat_index import (
    HeatIndexEngine,
    CanonicalThermalInput,
    HeatIndexValidationError,
    HeatIndexDerived,
)


class TestHeatIndexContract:
    def test_canonical_record_has_area_id_and_timestamp(self):
        """§7 identification schema required."""
        rec = CanonicalThermalInput(
            area_id="WARD_001", timestamp="2026-05-20T10:00:00Z",
            temperature_c=30.0, relative_humidity_pct=50.0
        )
        assert rec.area_id == "WARD_001"
        assert "2026" in rec.timestamp

    def test_required_environmental_fields_present(self):
        """§8 required: temperature_c, relative_humidity_pct."""
        rec = CanonicalThermalInput(
            area_id="W1", timestamp="2026-05-20T10:00:00Z",
            temperature_c=32.0, relative_humidity_pct=55.0
        )
        assert rec.temperature_c is not None
        assert rec.relative_humidity_pct is not None

    def test_missing_relative_humidity_no_fabrication(self):
        """§25: missing values never fabricated."""
        engine = HeatIndexEngine()
        bad = CanonicalThermalInput(
            area_id="W1", timestamp="2026-05-20T10:00:00Z",
            temperature_c=30.0, relative_humidity_pct=None
        )
        result = engine.calculate(bad)
        assert result.calculation_status == "INSUFFICIENT_DATA"
        assert result.heat_index_c is None

    def test_output_is_derived_heat_index_c(self):
        """§9 thermal index schema."""
        engine = HeatIndexEngine()
        rec = CanonicalThermalInput(
            area_id="W1", timestamp="2026-05-20T10:00:00Z",
            temperature_c=35.0, relative_humidity_pct=60.0
        )
        out = engine.calculate(rec)
        assert hasattr(out, "heat_index_c")
        assert isinstance(out.heat_index_c, float) or out.heat_index_c is None
        assert out.method_version.startswith("NWS")

    def test_internal_units_celsius(self):
        """§26: internal temperature must be °C, not °F."""
        # 35 °C => ~95 °F => HI ~45 °C (~113 °F)
        engine = HeatIndexEngine()
        out = engine.calculate(CanonicalThermalInput(
            area_id="W1", timestamp="2026-05-20T10:00:00Z",
            temperature_c=35.0, relative_humidity_pct=60.0
        ))
        assert out.heat_index_c > 35.0  # HI must exceed dry bulb in humid heat
        assert out.heat_index_c < 55.0

    def test_validation_rejects_impossible_rh(self):
        """§27: impossible environmental values rejected."""
        engine = HeatIndexEngine()
        rec = CanonicalThermalInput(
            area_id="W1", timestamp="2026-05-20T10:00:00Z",
            temperature_c=30.0, relative_humidity_pct=105.0
        )
        with pytest.raises(HeatIndexValidationError):
            engine.validate_input(rec)

    def test_documentation_contains_formula_library(self):
        """§4.1 / §9: must document formula and assumptions."""
        meta = HeatIndexEngine().documentation()
        assert "formula_library" in meta
        assert "assumptions" in meta
        assert "fallback_behaviour" in meta