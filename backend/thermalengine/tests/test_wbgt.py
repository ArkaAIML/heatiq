"""
Unit tests for WBGT module
Contract: §4.1, §8, §9, §25, §27, §26
"""

import unittest
import math

from backend.thermalengine.wbgt import (
    WBGTEngine,
    CanonicalThermalInput,
    WBGTValidationError,
    WBGTDerived,
    compute_wbgt_outdoor,
    compute_wbgt_indoor,
)


class TestWBGTContract(unittest.TestCase):
    """Test contract compliance (§4.1, §8, §9, §25, §27)"""
    
    def test_canonical_record_identification(self):
        """§7 identification schema required."""
        rec = CanonicalThermalInput(
            area_id="WARD_001",
            timestamp="2026-05-20T10:00:00Z",
            temperature_c=30.0,
            relative_humidity_pct=50.0
        )
        self.assertEqual(rec.area_id, "WARD_001")
        self.assertIn("2026", rec.timestamp)
    
    def test_required_environmental_fields(self):
        """§8 required: temperature_c, relative_humidity_pct."""
        rec = CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T10:00:00Z",
            temperature_c=32.0,
            relative_humidity_pct=55.0
        )
        self.assertIsNotNone(rec.temperature_c)
        self.assertIsNotNone(rec.relative_humidity_pct)
    
    def test_outdoor_requires_wind_and_solar(self):
        """§8 outdoor WBGT requires wind_speed_ms and solar_radiation_wm2."""
        rec = CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T10:00:00Z",
            temperature_c=35.0,
            relative_humidity_pct=60.0,
            wind_speed_ms=2.5,
            solar_radiation_wm2=800.0
        )
        self.assertIsNotNone(rec.wind_speed_ms)
        self.assertIsNotNone(rec.solar_radiation_wm2)
    
    def test_missing_temperature_no_fabrication(self):
        """§25: missing values never fabricated."""
        engine = WBGTEngine()
        bad = CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T10:00:00Z",
            temperature_c=None,  # Missing
            relative_humidity_pct=60.0
        )
        result = engine.calculate(bad)
        self.assertEqual(result.calculation_status, "INSUFFICIENT_DATA")
        self.assertIsNone(result.wbgt_c)
    
    def test_output_is_derived_wbgt_c(self):
        """§9 thermal index schema."""
        engine = WBGTEngine()
        rec = CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T10:00:00Z",
            temperature_c=35.0,
            relative_humidity_pct=60.0,
            wind_speed_ms=2.0,
            solar_radiation_wm2=700.0
        )
        out = engine.calculate(rec)
        self.assertTrue(hasattr(out, "wbgt_c"))
        self.assertIsInstance(out.wbgt_c, float)
        self.assertTrue(out.method_version.startswith("Liljegren"))
    
    def test_internal_units_celsius(self):
        """§26: internal temperature must be °C."""
        engine = WBGTEngine()
        out = engine.calculate(CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T10:00:00Z",
            temperature_c=35.0,
            relative_humidity_pct=60.0,
            wind_speed_ms=2.0,
            solar_radiation_wm2=700.0
        ))
        self.assertTrue(25.0 < out.wbgt_c < 45.0)  # Plausible WBGT range in °C
    
    def test_validation_rejects_impossible_rh(self):
        """§27: impossible environmental values rejected."""
        engine = WBGTEngine()
        rec = CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T10:00:00Z",
            temperature_c=30.0,
            relative_humidity_pct=150.0  # Invalid
        )
        with self.assertRaises(WBGTValidationError):
            engine.validate_input(rec)
    
    def test_validation_rejects_impossible_wind(self):
        """§27: impossible wind speed rejected."""
        engine = WBGTEngine()
        rec = CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T10:00:00Z",
            temperature_c=30.0,
            relative_humidity_pct=50.0,
            wind_speed_ms=100.0  # Impossible
        )
        with self.assertRaises(WBGTValidationError):
            engine.validate_input(rec, require_outdoor=True)
    
    def test_validation_rejects_impossible_solar(self):
        """§27: impossible solar radiation rejected."""
        engine = WBGTEngine()
        rec = CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T10:00:00Z",
            temperature_c=30.0,
            relative_humidity_pct=50.0,
            wind_speed_ms=2.0,
            solar_radiation_wm2=2000.0  # Too high
        )
        with self.assertRaises(WBGTValidationError):
            engine.validate_input(rec, require_outdoor=True)
    
    def test_documentation_contains_formula(self):
        """§4.1 / §9: must document formula and assumptions."""
        meta = WBGTEngine().documentation()
        self.assertIn("formula_library", meta)
        self.assertIn("assumptions", meta)
        self.assertIn("fallback_behaviour", meta)
        self.assertIn("ISO 7243", meta["formula_library"])


class TestWBGTCalculationMethods(unittest.TestCase):
    """Test different calculation methods work correctly."""
    
    def test_outdoor_full_method(self):
        """OUTDOOR_FULL with all inputs available."""
        engine = WBGTEngine(prefer_outdoor=True)
        rec = CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T14:00:00Z",
            temperature_c=38.0,
            relative_humidity_pct=50.0,
            wind_speed_ms=2.0,
            solar_radiation_wm2=800.0
        )
        result = engine.calculate(rec)
        self.assertEqual(result.calculation_method, "OUTDOOR_FULL")
        self.assertEqual(result.calculation_status, "COMPUTED")
        self.assertGreater(result.wbgt_c, 30.0)
    
    def test_outdoor_simplified_method(self):
        """OUTDOOR_SIMPLIFIED when solar missing but wind available."""
        engine = WBGTEngine(prefer_outdoor=True)
        rec = CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T14:00:00Z",
            temperature_c=35.0,
            relative_humidity_pct=60.0,
            wind_speed_ms=2.5,
            solar_radiation_wm2=None  # Missing
        )
        result = engine.calculate(rec)
        self.assertEqual(result.calculation_method, "OUTDOOR_SIMPLIFIED")
        self.assertEqual(result.calculation_status, "COMPUTED")
        self.assertIsNotNone(result.wbgt_c)
    
    def test_indoor_method(self):
        """INDOOR when no wind/solar available."""
        engine = WBGTEngine(prefer_outdoor=True)
        rec = CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T14:00:00Z",
            temperature_c=32.0,
            relative_humidity_pct=70.0,
            wind_speed_ms=None,
            solar_radiation_wm2=None
        )
        result = engine.calculate(rec)
        self.assertEqual(result.calculation_method, "INDOOR")
        self.assertEqual(result.calculation_status, "COMPUTED")
        self.assertIsNotNone(result.wbgt_c)
    
    def test_wbgt_increases_with_temperature(self):
        """WBGT should increase with temperature."""
        engine = WBGTEngine()
        temps = [25.0, 30.0, 35.0, 40.0]
        wbgts = []
        
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
            wbgts.append(result.wbgt_c)
        
        for i in range(len(wbgts) - 1):
            self.assertLess(wbgts[i], wbgts[i + 1])
    
    def test_wbgt_increases_with_humidity(self):
        """WBGT should increase with humidity."""
        engine = WBGTEngine()
        humidities = [30.0, 50.0, 70.0, 90.0]
        wbgts = []
        
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
            wbgts.append(result.wbgt_c)
        
        for i in range(len(wbgts) - 1):
            self.assertLess(wbgts[i], wbgts[i + 1])
    
    def test_wbgt_increases_with_solar(self):
        """WBGT should increase with solar radiation."""
        engine = WBGTEngine()
        solars = [0.0, 400.0, 800.0, 1200.0]
        wbgts = []
        
        for solar in solars:
            rec = CanonicalThermalInput(
                area_id="TEST",
                timestamp="2026-05-20T14:00:00Z",
                temperature_c=35.0,
                relative_humidity_pct=60.0,
                wind_speed_ms=2.0,
                solar_radiation_wm2=solar
            )
            result = engine.calculate(rec)
            wbgts.append(result.wbgt_c)
        
        for i in range(len(wbgts) - 1):
            self.assertLess(wbgts[i], wbgts[i + 1])


class TestWBGTRiskCategories(unittest.TestCase):
    """Test ISO 7243 risk categorization."""
    
    def test_risk_categories_ordered(self):
        """Risk categories should be properly ordered."""
        engine = WBGTEngine()
        
        self.assertEqual(engine.get_risk_category(25.0), "MINIMAL_RISK")
        self.assertEqual(engine.get_risk_category(29.0), "LOW_RISK")
        self.assertEqual(engine.get_risk_category(31.5), "MODERATE_RISK")
        self.assertEqual(engine.get_risk_category(33.0), "HIGH_RISK")
        self.assertEqual(engine.get_risk_category(36.0), "EXTREME_RISK")


class TestConvenienceFunctions(unittest.TestCase):
    """Test module-level convenience functions."""
    
    def test_compute_wbgt_outdoor(self):
        """Test outdoor convenience function."""
        result = compute_wbgt_outdoor(
            temperature_c=35.0,
            relative_humidity_pct=60.0,
            wind_speed_ms=2.0,
            solar_radiation_wm2=700.0
        )
        self.assertEqual(result.calculation_method, "OUTDOOR_FULL")
        self.assertIsNotNone(result.wbgt_c)
    
    def test_compute_wbgt_indoor(self):
        """Test indoor convenience function."""
        result = compute_wbgt_indoor(
            temperature_c=32.0,
            relative_humidity_pct=70.0
        )
        self.assertEqual(result.calculation_method, "INDOOR")
        self.assertIsNotNone(result.wbgt_c)


class TestBatchProcessing(unittest.TestCase):
    """Test batch calculation."""
    
    def test_batch_calculation(self):
        """Calculate WBGT for multiple records."""
        engine = WBGTEngine()
        
        records = [
            CanonicalThermalInput(
                area_id=f"WARD_{i:03d}",
                timestamp="2026-05-20T14:00:00Z",
                temperature_c=30.0 + i * 2,
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
            self.assertIsNotNone(res.wbgt_c)


if __name__ == "__main__":
    unittest.main()
