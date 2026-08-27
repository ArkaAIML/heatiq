"""
Unit tests for Heat Index Module
Contract checks: §4.1, §8, §9, §25, §27, §26
"""

import unittest
from backend.thermalengine.heat_index import (
    HeatIndexEngine,
    CanonicalThermalInput,
    HeatIndexValidationError,
    HeatIndexDerived,
    compute_heat_index,
)


class TestHeatIndexContract(unittest.TestCase):
    def test_canonical_record_has_area_id_and_timestamp(self):
        """§7 identification schema required."""
        rec = CanonicalThermalInput(
            area_id="WARD_001", timestamp="2026-05-20T10:00:00Z",
            temperature_c=30.0, relative_humidity_pct=50.0
        )
        self.assertEqual(rec.area_id, "WARD_001")
        self.assertIn("2026", rec.timestamp)

    def test_required_environmental_fields_present(self):
        """§8 required: temperature_c, relative_humidity_pct."""
        rec = CanonicalThermalInput(
            area_id="W1", timestamp="2026-05-20T10:00:00Z",
            temperature_c=32.0, relative_humidity_pct=55.0
        )
        self.assertIsNotNone(rec.temperature_c)
        self.assertIsNotNone(rec.relative_humidity_pct)

    def test_missing_relative_humidity_no_fabrication(self):
        """§25: missing values never fabricated."""
        engine = HeatIndexEngine()
        bad = CanonicalThermalInput(
            area_id="W1", timestamp="2026-05-20T10:00:00Z",
            temperature_c=30.0, relative_humidity_pct=None
        )
        result = engine.calculate(bad)
        self.assertEqual(result.calculation_status, "INSUFFICIENT_DATA")
        self.assertIsNone(result.heat_index_c)

    def test_output_is_derived_heat_index_c(self):
        """§9 thermal index schema."""
        engine = HeatIndexEngine()
        rec = CanonicalThermalInput(
            area_id="W1", timestamp="2026-05-20T10:00:00Z",
            temperature_c=35.0, relative_humidity_pct=60.0
        )
        out = engine.calculate(rec)
        self.assertTrue(hasattr(out, "heat_index_c"))
        self.assertIsInstance(out.heat_index_c, float)
        self.assertTrue(out.method_version.startswith("NWS"))

    def test_internal_units_celsius(self):
        """§26: internal temperature must be °C, not °F."""
        # 35 °C => ~95 °F => HI ~45 °C (~113 °F)
        engine = HeatIndexEngine()
        out = engine.calculate(CanonicalThermalInput(
            area_id="W1", timestamp="2026-05-20T10:00:00Z",
            temperature_c=35.0, relative_humidity_pct=60.0
        ))
        self.assertGreater(out.heat_index_c, 35.0)  # HI must exceed dry bulb in humid heat
        self.assertLess(out.heat_index_c, 55.0)

    def test_validation_rejects_impossible_rh(self):
        """§27: impossible environmental values rejected."""
        engine = HeatIndexEngine()
        rec = CanonicalThermalInput(
            area_id="W1", timestamp="2026-05-20T10:00:00Z",
            temperature_c=30.0, relative_humidity_pct=105.0
        )
        with self.assertRaises(HeatIndexValidationError):
            engine.validate_input(rec)

    def test_documentation_contains_formula_library(self):
        """§4.1 / §9: must document formula and assumptions."""
        meta = HeatIndexEngine().documentation()
        self.assertIn("formula_library", meta)
        self.assertIn("assumptions", meta)
        self.assertIn("fallback_behaviour", meta)

    def test_convenience_function(self):
        res = compute_heat_index(temperature_c=35.0, relative_humidity_pct=60.0)
        self.assertEqual(res.calculation_status, "COMPUTED")
        self.assertIsNotNone(res.heat_index_c)


if __name__ == "__main__":
    unittest.main()
