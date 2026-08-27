"""
Unit tests for UTCI module
Contract: §4.1, §8, §9, §25, §27, §26
"""

import unittest
import math

from backend.thermalengine.utci import (
    UTCIEngine,
    CanonicalThermalInput,
    UTCIValidationError,
    UTCIDerived,
    compute_utci,
)


class TestUTCIContract(unittest.TestCase):
    """Test contract compliance (§4.1, §8, §9, §25, §27)"""
    
    def test_canonical_record_identification(self):
        """§7 identification schema required."""
        rec = CanonicalThermalInput(
            area_id="WARD_001",
            timestamp="2026-05-20T10:00:00Z",
            temperature_c=30.0,
            relative_humidity_pct=50.0,
            wind_speed_ms=2.0
        )
        self.assertEqual(rec.area_id, "WARD_001")
        self.assertIn("2026", rec.timestamp)
    
    def test_required_environmental_fields(self):
        """§8 required: temperature_c, relative_humidity_pct, wind_speed_ms."""
        rec = CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T10:00:00Z",
            temperature_c=32.0,
            relative_humidity_pct=55.0,
            wind_speed_ms=2.5
        )
        self.assertIsNotNone(rec.temperature_c)
        self.assertIsNotNone(rec.relative_humidity_pct)
        self.assertIsNotNone(rec.wind_speed_ms)
    
    def test_missing_wind_speed_no_fabrication(self):
        """§25: missing values never fabricated."""
        engine = UTCIEngine()
        bad = CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T10:00:00Z",
            temperature_c=30.0,
            relative_humidity_pct=60.0,
            wind_speed_ms=None  # Missing
        )
        result = engine.calculate(bad)
        self.assertEqual(result.calculation_status, "INSUFFICIENT_DATA")
        self.assertIsNone(result.utci_c)
    
    def test_output_is_derived_utci_c(self):
        """§9 thermal index schema."""
        engine = UTCIEngine()
        rec = CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T10:00:00Z",
            temperature_c=35.0,
            relative_humidity_pct=60.0,
            wind_speed_ms=2.0,
            solar_radiation_wm2=700.0
        )
        out = engine.calculate(rec)
        self.assertTrue(hasattr(out, "utci_c"))
        self.assertIsInstance(out.utci_c, float)
        self.assertTrue(out.method_version.startswith("COST"))
    
    def test_internal_units_celsius(self):
        """§26: internal temperature must be °C."""
        engine = UTCIEngine()
        out = engine.calculate(CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T10:00:00Z",
            temperature_c=35.0,
            relative_humidity_pct=60.0,
            wind_speed_ms=2.0
        ))
        self.assertTrue(30.0 < out.utci_c < 50.0)
    
    def test_validation_rejects_impossible_rh(self):
        """§27: impossible environmental values rejected."""
        engine = UTCIEngine()
        rec = CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T10:00:00Z",
            temperature_c=30.0,
            relative_humidity_pct=150.0,  # Invalid
            wind_speed_ms=2.0
        )
        with self.assertRaises(UTCIValidationError):
            engine.validate_input(rec)
    
    def test_validation_rejects_temperature_out_of_range(self):
        """§27: temperature outside UTCI valid range rejected."""
        engine = UTCIEngine()
        rec = CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T10:00:00Z",
            temperature_c=60.0,  # Above valid range
            relative_humidity_pct=50.0,
            wind_speed_ms=2.0
        )
        with self.assertRaises(UTCIValidationError):
            engine.validate_input(rec)
    
    def test_documentation_contains_formula(self):
        """§4.1 / §9: must document formula and assumptions."""
        meta = UTCIEngine().documentation()
        self.assertIn("formula_library", meta)
        self.assertIn("assumptions", meta)
        self.assertIn("fallback_behaviour", meta)
        self.assertIn("COST Action 730", meta["formula_library"])


class TestUTCICalculation(unittest.TestCase):
    """Test UTCI calculation accuracy and behavior."""
    
    def test_hot_conditions_with_solar(self):
        """UTCI for hot sunny conditions."""
        engine = UTCIEngine()
        rec = CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T14:00:00Z",
            temperature_c=38.0,
            relative_humidity_pct=50.0,
            wind_speed_ms=2.0,
            solar_radiation_wm2=850.0
        )
        result = engine.calculate(rec)
        self.assertEqual(result.calculation_status, "COMPUTED")
        self.assertGreater(result.utci_c, 38.0)
        self.assertIn("HEAT", result.thermal_stress_category)
    
    def test_cold_conditions(self):
        """UTCI for cold conditions."""
        engine = UTCIEngine()
        rec = CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-01-15T08:00:00Z",
            temperature_c=-10.0,
            relative_humidity_pct=70.0,
            wind_speed_ms=5.0,
            solar_radiation_wm2=100.0
        )
        result = engine.calculate(rec)
        self.assertEqual(result.calculation_status, "COMPUTED")
        self.assertLess(result.utci_c, -10.0)
        self.assertIn("COLD", result.thermal_stress_category)
    
    def test_mild_conditions(self):
        """UTCI for comfortable conditions."""
        engine = UTCIEngine()
        rec = CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-04-10T12:00:00Z",
            temperature_c=20.0,
            relative_humidity_pct=50.0,
            wind_speed_ms=1.5,
            solar_radiation_wm2=500.0
        )
        result = engine.calculate(rec)
        self.assertEqual(result.calculation_status, "COMPUTED")
        self.assertTrue(15.0 < result.utci_c < 30.0)
    
    def test_without_solar_radiation(self):
        """UTCI when solar radiation unavailable."""
        engine = UTCIEngine()
        rec = CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T14:00:00Z",
            temperature_c=35.0,
            relative_humidity_pct=60.0,
            wind_speed_ms=2.0,
            solar_radiation_wm2=None
        )
        result = engine.calculate(rec)
        self.assertEqual(result.calculation_status, "COMPUTED")
        self.assertEqual(result.tmrt_method, "ASSUMED_EQUAL_TA")
        self.assertIsNotNone(result.utci_c)
    
    def test_utci_increases_with_temperature(self):
        """UTCI should increase monotonically with temperature."""
        engine = UTCIEngine()
        temps = [20.0, 25.0, 30.0, 35.0, 40.0]
        utcis = []
        
        for temp in temps:
            rec = CanonicalThermalInput(
                area_id="TEST",
                timestamp="2026-05-20T14:00:00Z",
                temperature_c=temp,
                relative_humidity_pct=60.0,
                wind_speed_ms=2.0,
                solar_radiation_wm2=700.0
            )
            result = engine.calculate(rec)
            utcis.append(result.utci_c)
        
        for i in range(len(utcis) - 1):
            self.assertLess(utcis[i], utcis[i + 1])
    
    def test_utci_increases_with_humidity(self):
        """UTCI should increase with humidity in hot conditions."""
        engine = UTCIEngine()
        humidities = [30.0, 50.0, 70.0, 90.0]
        utcis = []
        
        for rh in humidities:
            rec = CanonicalThermalInput(
                area_id="TEST",
                timestamp="2026-05-20T14:00:00Z",
                temperature_c=35.0,
                relative_humidity_pct=rh,
                wind_speed_ms=2.0,
                solar_radiation_wm2=700.0
            )
            result = engine.calculate(rec)
            utcis.append(result.utci_c)
        
        for i in range(len(utcis) - 1):
            self.assertLess(utcis[i], utcis[i + 1])
    
    def test_wind_reduces_heat_stress(self):
        """Higher wind should reduce UTCI in hot conditions."""
        engine = UTCIEngine()
        winds = [0.5, 1.0, 2.0, 4.0]
        utcis = []
        
        for wind in winds:
            rec = CanonicalThermalInput(
                area_id="TEST",
                timestamp="2026-05-20T14:00:00Z",
                temperature_c=38.0,
                relative_humidity_pct=50.0,
                wind_speed_ms=wind,
                solar_radiation_wm2=800.0
            )
            result = engine.calculate(rec)
            utcis.append(result.utci_c)
        
        self.assertGreater(utcis[0], utcis[-1])
    
    def test_minimum_wind_speed_enforced(self):
        """UTCI enforces minimum 0.5 m/s wind speed."""
        engine = UTCIEngine()
        rec = CanonicalThermalInput(
            area_id="TEST",
            timestamp="2026-05-20T14:00:00Z",
            temperature_c=25.0,
            relative_humidity_pct=60.0,
            wind_speed_ms=0.1,  # Below minimum
            solar_radiation_wm2=500.0
        )
        result = engine.calculate(rec)
        self.assertEqual(result.calculation_status, "COMPUTED")


class TestUTCIStressCategories(unittest.TestCase):
    """Test thermal stress categorization."""
    
    def test_stress_categories_cover_full_range(self):
        """All UTCI values should map to a category."""
        engine = UTCIEngine()
        test_values = [-45.0, -30.0, -15.0, 5.0, 15.0, 28.0, 35.0, 42.0]
        for utci in test_values:
            category = engine.get_stress_category(utci)
            self.assertNotEqual(category, "UNKNOWN")
    
    def test_extreme_heat_category(self):
        """Values above 38°C should be EXTREME_HEAT."""
        engine = UTCIEngine()
        self.assertEqual(engine.get_stress_category(40.0), "EXTREME_HEAT")
        self.assertEqual(engine.get_stress_category(45.0), "EXTREME_HEAT")
    
    def test_extreme_cold_category(self):
        """Values below -40°C should be EXTREME_COLD."""
        engine = UTCIEngine()
        self.assertEqual(engine.get_stress_category(-45.0), "EXTREME_COLD")
        self.assertEqual(engine.get_stress_category(-50.0), "EXTREME_COLD")
    
    def test_no_stress_category(self):
        """Values 0-9°C should be NO_THERMAL_STRESS."""
        engine = UTCIEngine()
        self.assertEqual(engine.get_stress_category(5.0), "NO_THERMAL_STRESS")
        self.assertEqual(engine.get_stress_category(8.0), "NO_THERMAL_STRESS")


class TestConvenienceFunctions(unittest.TestCase):
    """Test module-level convenience functions."""
    
    def test_compute_utci_with_solar(self):
        """Test convenience function with solar radiation."""
        result = compute_utci(
            temperature_c=35.0,
            relative_humidity_pct=60.0,
            wind_speed_ms=2.0,
            solar_radiation_wm2=700.0
        )
        self.assertEqual(result.calculation_status, "COMPUTED")
        self.assertIsNotNone(result.utci_c)
        self.assertEqual(result.tmrt_method, "SOLAR_ESTIMATED")
    
    def test_compute_utci_without_solar(self):
        """Test convenience function without solar radiation."""
        result = compute_utci(
            temperature_c=30.0,
            relative_humidity_pct=50.0,
            wind_speed_ms=1.5,
            solar_radiation_wm2=None
        )
        self.assertEqual(result.calculation_status, "COMPUTED")
        self.assertEqual(result.tmrt_method, "ASSUMED_EQUAL_TA")


class TestBatchProcessing(unittest.TestCase):
    """Test batch calculation."""
    
    def test_batch_calculation(self):
        """Calculate UTCI for multiple records."""
        engine = UTCIEngine()
        records = [
            CanonicalThermalInput(
                area_id=f"WARD_{i:03d}",
                timestamp="2026-05-20T14:00:00Z",
                temperature_c=25.0 + i * 3,
                relative_humidity_pct=50.0 + i * 5,
                wind_speed_ms=2.0,
                solar_radiation_wm2=700.0
            )
            for i in range(5)
        ]
        results = engine.calculate_batch(records)
        self.assertEqual(len(results), 5)
        for res in results:
            self.assertEqual(res.calculation_status, "COMPUTED")
            self.assertIsNotNone(res.utci_c)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""
    
    def test_very_low_humidity(self):
        """UTCI at 5% RH (minimum valid)."""
        engine = UTCIEngine()
        rec = CanonicalThermalInput(
            area_id="TEST",
            timestamp="2026-05-20T14:00:00Z",
            temperature_c=40.0,
            relative_humidity_pct=5.0,
            wind_speed_ms=2.0
        )
        result = engine.calculate(rec)
        self.assertEqual(result.calculation_status, "COMPUTED")
    
    def test_very_high_temperature(self):
        """UTCI at 50°C (maximum valid)."""
        engine = UTCIEngine()
        rec = CanonicalThermalInput(
            area_id="TEST",
            timestamp="2026-05-20T14:00:00Z",
            temperature_c=50.0,
            relative_humidity_pct=30.0,
            wind_speed_ms=2.0
        )
        result = engine.calculate(rec)
        self.assertEqual(result.calculation_status, "COMPUTED")
        self.assertGreater(result.utci_c, 50.0)
    
    def test_very_low_temperature(self):
        """UTCI at -50°C (minimum valid)."""
        engine = UTCIEngine()
        rec = CanonicalThermalInput(
            area_id="TEST",
            timestamp="2026-01-15T08:00:00Z",
            temperature_c=-50.0,
            relative_humidity_pct=70.0,
            wind_speed_ms=5.0
        )
        result = engine.calculate(rec)
        self.assertEqual(result.calculation_status, "COMPUTED")
        self.assertEqual(result.thermal_stress_category, "EXTREME_COLD")


if __name__ == "__main__":
    unittest.main()
