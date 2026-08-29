"""
Unit tests for the Thermal Engine Structuring Layer
Data Contract: v0.1  |  Checks: §5, §7, §8, §9, §25, §26, §27, §28
"""

import json
import unittest
import math

from backend.thermalengine import (
    calculate_thermal_indices,
    ThermalEngineService,
    ThermalInput,
    ThermalOutput,
    ThermalInputValidationError,
    HTSIEngine,
    HTSIInput,
)


class TestThermalInputSchemaAndValidation(unittest.TestCase):
    """Test ThermalInput instantiation and contract validation (§7, §8, §26, §27)."""

    def test_valid_input_instantiation(self):
        record = ThermalInput(
            area_id="WARD_017",
            timestamp="2026-05-20T14:00:00+05:30",
            temperature_c=38.0,
            relative_humidity_pct=55.0,
            wind_speed_ms=2.5,
            solar_radiation_wm2=850.0,
            latitude=20.35,
            longitude=85.82,
        )
        record.validate()
        self.assertEqual(record.area_id, "WARD_017")
        self.assertEqual(record.temperature_c, 38.0)

    def test_from_dict_and_to_dict(self):
        data = {
            "area_id": "WARD_017",
            "timestamp": "2026-05-20T14:00:00Z",
            "temperature_c": 35.0,
            "relative_humidity_pct": 60.0,
            "wind_speed_ms": 2.0,
            "solar_radiation_wm2": 700.0,
        }
        record = ThermalInput.from_dict(data)
        self.assertEqual(record.area_id, "WARD_017")
        out_dict = record.to_dict()
        self.assertEqual(out_dict["temperature_c"], 35.0)

    def test_from_json_and_to_json(self):
        data = {
            "area_id": "WARD_017",
            "timestamp": "2026-05-20T14:00:00Z",
            "temperature_c": 35.0,
            "relative_humidity_pct": 60.0,
        }
        json_str = json.dumps(data)
        record = ThermalInput.from_json(json_str)
        self.assertEqual(record.area_id, "WARD_017")
        serialized = record.to_json()
        self.assertIn("WARD_017", serialized)

    def test_validation_rejects_empty_area_id(self):
        record = ThermalInput(
            area_id="   ",
            timestamp="2026-05-20T14:00:00Z",
            temperature_c=35.0,
            relative_humidity_pct=60.0,
        )
        with self.assertRaises(ThermalInputValidationError) as ctx:
            record.validate()
        self.assertIn("area_id", str(ctx.exception))

    def test_validation_rejects_invalid_timestamp(self):
        record = ThermalInput(
            area_id="WARD_017",
            timestamp="not-a-timestamp",
            temperature_c=35.0,
            relative_humidity_pct=60.0,
        )
        with self.assertRaises(ThermalInputValidationError) as ctx:
            record.validate()
        self.assertIn("timestamp", str(ctx.exception))

    def test_validation_rejects_missing_required_temperature(self):
        with self.assertRaises(ThermalInputValidationError):
            ThermalInput.from_dict({
                "area_id": "WARD_017",
                "timestamp": "2026-05-20T14:00:00Z",
                "relative_humidity_pct": 60.0,
            })

    def test_validation_rejects_out_of_range_temperature(self):
        record = ThermalInput(
            area_id="WARD_017",
            timestamp="2026-05-20T14:00:00Z",
            temperature_c=65.0,  # Max is 60.0
            relative_humidity_pct=60.0,
        )
        with self.assertRaises(ThermalInputValidationError) as ctx:
            record.validate()
        self.assertIn("temperature_c", str(ctx.exception))

    def test_validation_rejects_out_of_range_humidity(self):
        record = ThermalInput(
            area_id="WARD_017",
            timestamp="2026-05-20T14:00:00Z",
            temperature_c=35.0,
            relative_humidity_pct=105.0,  # Max is 100.0
        )
        with self.assertRaises(ThermalInputValidationError) as ctx:
            record.validate()
        self.assertIn("relative_humidity_pct", str(ctx.exception))

    def test_validation_rejects_out_of_range_wind(self):
        record = ThermalInput(
            area_id="WARD_017",
            timestamp="2026-05-20T14:00:00Z",
            temperature_c=35.0,
            relative_humidity_pct=60.0,
            wind_speed_ms=60.0,  # Max is 50.0
        )
        with self.assertRaises(ThermalInputValidationError) as ctx:
            record.validate()
        self.assertIn("wind_speed_ms", str(ctx.exception))

    def test_validation_rejects_out_of_range_solar(self):
        record = ThermalInput(
            area_id="WARD_017",
            timestamp="2026-05-20T14:00:00Z",
            temperature_c=35.0,
            relative_humidity_pct=60.0,
            solar_radiation_wm2=2000.0,  # Max is 1500.0
        )
        with self.assertRaises(ThermalInputValidationError) as ctx:
            record.validate()
        self.assertIn("solar_radiation_wm2", str(ctx.exception))

    def test_validation_rejects_nan_and_inf(self):
        record = ThermalInput(
            area_id="WARD_017",
            timestamp="2026-05-20T14:00:00Z",
            temperature_c=float("inf"),
            relative_humidity_pct=60.0,
        )
        with self.assertRaises(ThermalInputValidationError):
            record.validate()


class TestThermalEngineService(unittest.TestCase):
    """Test ThermalEngineService and primary callable interface calculate_thermal_indices."""

    def test_calculate_with_dataclass(self):
        inp = ThermalInput(
            area_id="WARD_017",
            timestamp="2026-05-20T14:00:00+05:30",
            temperature_c=38.0,
            relative_humidity_pct=50.0,
            wind_speed_ms=2.0,
            solar_radiation_wm2=850.0,
        )
        out = calculate_thermal_indices(inp)
        self.assertIsInstance(out, ThermalOutput)
        self.assertEqual(out.area_id, "WARD_017")
        self.assertEqual(out.timestamp, "2026-05-20T14:00:00+05:30")
        self.assertEqual(out.calculation_status, "COMPUTED")
        self.assertIsNotNone(out.htsi)
        self.assertIsNotNone(out.wbgt_c)
        self.assertIsNotNone(out.utci_c)
        self.assertIsNotNone(out.heat_index_c)
        self.assertIn("HI", out.indices_computed)
        self.assertIn("WBGT", out.indices_computed)
        self.assertIn("UTCI", out.indices_computed)

    def test_calculate_with_dict(self):
        data = {
            "area_id": "WARD_018",
            "timestamp": "2026-05-20T14:00:00Z",
            "temperature_c": 35.0,
            "relative_humidity_pct": 60.0,
            "wind_speed_ms": 2.0,
            "solar_radiation_wm2": 700.0,
        }
        out = calculate_thermal_indices(data)
        self.assertEqual(out.area_id, "WARD_018")
        self.assertEqual(out.calculation_status, "COMPUTED")
        self.assertGreater(out.htsi, 0.0)

    def test_calculate_with_json_string(self):
        json_str = json.dumps({
            "area_id": "WARD_019",
            "timestamp": "2026-05-20T14:00:00Z",
            "temperature_c": 32.0,
            "relative_humidity_pct": 70.0,
        })
        out = calculate_thermal_indices(json_str)
        self.assertEqual(out.area_id, "WARD_019")
        # UTCI is skipped because wind_speed_ms is omitted
        self.assertEqual(out.calculation_status, "PARTIAL")
        self.assertIsNone(out.utci_c)
        self.assertIsNotNone(out.wbgt_c)
        self.assertIsNotNone(out.heat_index_c)
        self.assertIsNotNone(out.htsi)

    def test_calculate_with_kwargs(self):
        out = calculate_thermal_indices(
            area_id="WARD_020",
            timestamp="2026-05-20T14:00:00Z",
            temperature_c=35.0,
            relative_humidity_pct=60.0,
            wind_speed_ms=2.0,
            solar_radiation_wm2=700.0,
        )
        self.assertEqual(out.area_id, "WARD_020")
        self.assertEqual(out.calculation_status, "COMPUTED")

    def test_output_to_dict_and_to_json(self):
        out = calculate_thermal_indices(
            area_id="WARD_017",
            timestamp="2026-05-20T14:00:00Z",
            temperature_c=38.0,
            relative_humidity_pct=50.0,
            wind_speed_ms=2.0,
            solar_radiation_wm2=800.0,
        )
        out_dict = out.to_dict()
        self.assertIsInstance(out_dict, dict)
        self.assertIn("htsi", out_dict)
        self.assertIn("wbgt_c", out_dict)
        self.assertIn("utci_c", out_dict)
        self.assertIn("heat_index_c", out_dict)

        out_json = out.to_json()
        self.assertIsInstance(out_json, str)
        parsed = json.loads(out_json)
        self.assertEqual(parsed["area_id"], "WARD_017")

    def test_calculate_batch(self):
        service = ThermalEngineService()
        records = [
            {
                "area_id": f"WARD_{i:03d}",
                "timestamp": "2026-05-20T14:00:00Z",
                "temperature_c": 30.0 + i * 2,
                "relative_humidity_pct": 50.0 + i * 5,
                "wind_speed_ms": 2.0,
                "solar_radiation_wm2": 700.0,
            }
            for i in range(3)
        ]
        results = service.calculate_batch(records)
        self.assertEqual(len(results), 3)
        for i, res in enumerate(results):
            self.assertEqual(res.area_id, f"WARD_{i:03d}")
            self.assertEqual(res.calculation_status, "COMPUTED")

    def test_regression_numerical_consistency(self):
        """Ensure structuring layer gives exact same calculation output as direct HTSIEngine."""
        raw_engine = HTSIEngine()
        internal_rec = HTSIInput(
            area_id="TEST_REG",
            timestamp="2026-05-20T14:00:00Z",
            temperature_c=36.5,
            relative_humidity_pct=58.0,
            wind_speed_ms=2.3,
            solar_radiation_wm2=720.0,
        )
        expected = raw_engine.calculate(internal_rec)

        structured_out = calculate_thermal_indices(
            area_id="TEST_REG",
            timestamp="2026-05-20T14:00:00Z",
            temperature_c=36.5,
            relative_humidity_pct=58.0,
            wind_speed_ms=2.3,
            solar_radiation_wm2=720.0,
        )

        self.assertEqual(structured_out.htsi, expected.htsi)
        self.assertEqual(structured_out.htsi_category, expected.htsi_category)
        self.assertEqual(structured_out.wbgt_c, expected.wbgt_c)
        self.assertEqual(structured_out.utci_c, expected.utci_c)
        self.assertEqual(structured_out.heat_index_c, expected.heat_index_c)
        self.assertEqual(structured_out.hi_score, expected.hi_score)
        self.assertEqual(structured_out.wbgt_score, expected.wbgt_score)
        self.assertEqual(structured_out.utci_score, expected.utci_score)


if __name__ == "__main__":
    unittest.main()
