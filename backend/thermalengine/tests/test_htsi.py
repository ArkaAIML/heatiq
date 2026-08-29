"""
Unit tests for HTSI (Human Thermal Stress Index) module
Contract: §4.1, §8, §9, §25, §27, §26
"""

import unittest
import math

from backend.thermalengine.htsi import (
    HTSIEngine,
    HTSIInput,
    HTSIDerived,
    compute_htsi,
    normalize_heat_index,
    normalize_wbgt,
    normalize_utci,
    _htsi_category,
)


class TestHTSINormalization(unittest.TestCase):
    """Test individual index normalization functions (0-100)."""

    def test_hi_normalization_bounds(self):
        self.assertEqual(normalize_heat_index(20.0), 0.0)
        self.assertEqual(normalize_heat_index(27.0), 15.0)
        self.assertEqual(normalize_heat_index(33.0), 40.0)
        self.assertEqual(normalize_heat_index(40.0), 60.0)
        self.assertEqual(normalize_heat_index(52.0), 80.0)
        self.assertEqual(normalize_heat_index(65.0), 100.0)

    def test_wbgt_normalization_bounds(self):
        self.assertEqual(normalize_wbgt(15.0), 0.0)
        self.assertEqual(normalize_wbgt(28.0), 25.0)
        self.assertEqual(normalize_wbgt(31.0), 50.0)
        self.assertEqual(normalize_wbgt(34.0), 80.0)
        self.assertEqual(normalize_wbgt(42.0), 100.0)

    def test_utci_normalization_bounds(self):
        self.assertEqual(normalize_utci(5.0), 0.0)  # Cold / no heat stress
        self.assertEqual(normalize_utci(9.0), 0.0)
        self.assertEqual(normalize_utci(26.0), 25.0)
        self.assertEqual(normalize_utci(32.0), 55.0)
        self.assertEqual(normalize_utci(38.0), 80.0)
        self.assertEqual(normalize_utci(52.0), 100.0)


class TestHTSICalculation(unittest.TestCase):
    """Test composite HTSI calculation and monotonicity."""

    def test_htsi_range_zero_to_hundred(self):
        engine = HTSIEngine()
        rec = HTSIInput(
            area_id="TEST",
            timestamp="2026-05-20T14:00:00Z",
            temperature_c=35.0,
            relative_humidity_pct=60.0,
            wind_speed_ms=2.0,
            solar_radiation_wm2=700.0,
        )
        res = engine.calculate(rec)
        self.assertEqual(res.calculation_status, "COMPUTED")
        self.assertIsNotNone(res.htsi)
        self.assertTrue(0.0 <= res.htsi <= 100.0)

    def test_htsi_monotonic_with_temperature(self):
        engine = HTSIEngine()
        temps = [25.0, 30.0, 35.0, 40.0, 45.0]
        htsi_vals = []

        for t in temps:
            rec = HTSIInput(
                area_id="TEST",
                timestamp="2026-05-20T14:00:00Z",
                temperature_c=t,
                relative_humidity_pct=60.0,
                wind_speed_ms=2.0,
                solar_radiation_wm2=600.0,
            )
            res = engine.calculate(rec)
            htsi_vals.append(res.htsi)

        for i in range(len(htsi_vals) - 1):
            self.assertLess(htsi_vals[i], htsi_vals[i + 1])

    def test_htsi_monotonic_with_humidity(self):
        engine = HTSIEngine()
        humidities = [40.0, 60.0, 80.0]
        htsi_vals = []

        for rh in humidities:
            rec = HTSIInput(
                area_id="TEST",
                timestamp="2026-05-20T14:00:00Z",
                temperature_c=35.0,
                relative_humidity_pct=rh,
                wind_speed_ms=2.0,
                solar_radiation_wm2=600.0,
            )
            res = engine.calculate(rec)
            htsi_vals.append(res.htsi)

        for i in range(len(htsi_vals) - 1):
            self.assertLess(htsi_vals[i], htsi_vals[i + 1])

    def test_htsi_monotonic_with_solar(self):
        engine = HTSIEngine()
        solar_loads = [0.0, 400.0, 800.0]
        htsi_vals = []

        for sol in solar_loads:
            rec = HTSIInput(
                area_id="TEST",
                timestamp="2026-05-20T14:00:00Z",
                temperature_c=35.0,
                relative_humidity_pct=60.0,
                wind_speed_ms=2.0,
                solar_radiation_wm2=sol,
            )
            res = engine.calculate(rec)
            htsi_vals.append(res.htsi)

        for i in range(len(htsi_vals) - 1):
            self.assertLessEqual(htsi_vals[i], htsi_vals[i + 1])


class TestHTSIFallbacksAndWeighting(unittest.TestCase):
    """Test re-weighting when some indices are skipped."""

    def test_missing_wind_omits_utci_and_renormalizes(self):
        engine = HTSIEngine(hi_weight=0.25, wbgt_weight=0.35, utci_weight=0.40)
        rec = HTSIInput(
            area_id="TEST",
            timestamp="2026-05-20T14:00:00Z",
            temperature_c=35.0,
            relative_humidity_pct=60.0,
            wind_speed_ms=None,  # Missing -> UTCI skipped
        )
        res = engine.calculate(rec)
        self.assertEqual(res.calculation_status, "PARTIAL")
        self.assertIsNone(res.utci_score)
        self.assertIn("UTCI (no wind_speed_ms)", res.indices_skipped)
        total_eff_weight = res.weights_used["HI"] + res.weights_used["WBGT"]
        self.assertAlmostEqual(total_eff_weight, 100.0, delta=0.2)

    def test_missing_all_required_returns_insufficient_data(self):
        engine = HTSIEngine()
        rec = HTSIInput(
            area_id="TEST",
            timestamp="2026-05-20T14:00:00Z",
            temperature_c=None,  # Missing required
            relative_humidity_pct=60.0,
        )
        res = engine.calculate(rec)
        self.assertEqual(res.calculation_status, "INSUFFICIENT_DATA")
        self.assertIsNone(res.htsi)


class TestHTSICategories(unittest.TestCase):
    """Test category thresholds."""

    def test_category_mapping(self):
        self.assertEqual(_htsi_category(10.0), "LOW")
        self.assertEqual(_htsi_category(25.0), "MODERATE")
        self.assertEqual(_htsi_category(50.0), "HIGH")
        self.assertEqual(_htsi_category(70.0), "VERY_HIGH")
        self.assertEqual(_htsi_category(90.0), "EXTREME")


class TestConvenienceFunction(unittest.TestCase):
    """Test compute_htsi wrapper."""

    def test_compute_htsi_wrapper(self):
        res = compute_htsi(
            temperature_c=34.0,
            relative_humidity_pct=65.0,
            wind_speed_ms=2.0,
            solar_radiation_wm2=650.0,
        )
        self.assertEqual(res.calculation_status, "COMPUTED")
        self.assertIsNotNone(res.htsi)
        self.assertIn(res.htsi_category, ["LOW", "MODERATE", "HIGH", "VERY_HIGH", "EXTREME"])


if __name__ == "__main__":
    unittest.main()
