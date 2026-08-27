"""
Unit tests for the Multi-Ward Thermal Structuring Gate
Data Contract: v0.1  |  Checks: Multi-ward batch processing, fault tolerance, order preservation, and numerical parity.
"""

import json
import unittest

from backend.thermalengine import (
    calculate_thermal_indices,
    calculate_thermal_indices_batch,
    ThermalEngineService,
    ThermalInput,
    ThermalOutput,
    ThermalInputValidationError,
)


class TestMultiWardStructuringGate(unittest.TestCase):
    """Test multi-ward structuring gate features and edge cases."""

    def setUp(self):
        self.ward_1_data = {
            "area_id": "WARD_001",
            "timestamp": "2026-05-20T14:00:00+05:30",
            "temperature_c": 35.0,
            "relative_humidity_pct": 60.0,
            "wind_speed_ms": 2.0,
            "solar_radiation_wm2": 700.0,
        }
        self.ward_2_data = {
            "area_id": "WARD_002",
            "timestamp": "2026-05-20T14:00:00+05:30",
            "temperature_c": 42.0,
            "relative_humidity_pct": 40.0,
            "wind_speed_ms": 1.5,
            "solar_radiation_wm2": 950.0,
        }
        self.ward_3_data = {
            "area_id": "WARD_003",
            "timestamp": "2026-05-20T14:00:00+05:30",
            "temperature_c": 28.0,
            "relative_humidity_pct": 75.0,
            "wind_speed_ms": 3.0,
            "solar_radiation_wm2": 350.0,
        }

    def test_multiple_valid_wards_processing(self):
        """Test batch calculation for multiple valid wards preserving order and identity."""
        wards = [self.ward_1_data, self.ward_2_data, self.ward_3_data]
        outputs = calculate_thermal_indices_batch(wards)

        self.assertEqual(len(outputs), 3)

        # Verify identity and order
        self.assertEqual(outputs[0].area_id, "WARD_001")
        self.assertEqual(outputs[1].area_id, "WARD_002")
        self.assertEqual(outputs[2].area_id, "WARD_003")

        # Verify all computed
        for out in outputs:
            self.assertEqual(out.calculation_status, "COMPUTED")
            self.assertIsNotNone(out.htsi)
            self.assertIsNotNone(out.wbgt_c)
            self.assertIsNotNone(out.utci_c)
            self.assertIsNotNone(out.heat_index_c)

        # Ward 2 should have higher HTSI than Ward 1 and Ward 3
        self.assertGreater(outputs[1].htsi, outputs[0].htsi)
        self.assertGreater(outputs[1].htsi, outputs[2].htsi)

    def test_polymorphic_calculate_thermal_indices_with_list(self):
        """Test calculate_thermal_indices accepts a list and returns a list."""
        wards = [self.ward_1_data, self.ward_2_data]
        outputs = calculate_thermal_indices(wards)

        self.assertIsInstance(outputs, list)
        self.assertEqual(len(outputs), 2)
        self.assertEqual(outputs[0].area_id, "WARD_001")
        self.assertEqual(outputs[1].area_id, "WARD_002")

    def test_single_ward_in_collection(self):
        """Test batch calculation with a single record in collection."""
        outputs = calculate_thermal_indices_batch([self.ward_1_data])
        self.assertEqual(len(outputs), 1)
        self.assertEqual(outputs[0].area_id, "WARD_001")
        self.assertEqual(outputs[0].calculation_status, "COMPUTED")

    def test_empty_collection(self):
        """Test batch calculation with empty collection returns empty list."""
        outputs = calculate_thermal_indices_batch([])
        self.assertEqual(outputs, [])

    def test_partial_failure_tolerance(self):
        """Test that invalid ward does not crash valid wards and returns traceable failure."""
        invalid_ward = {
            "area_id": "WARD_002_BAD",
            "timestamp": "2026-05-20T14:00:00Z",
            "temperature_c": 75.0,  # Invalid: > 60.0°C plausible limit
            "relative_humidity_pct": 50.0,
        }
        wards = [self.ward_1_data, invalid_ward, self.ward_3_data]

        outputs = calculate_thermal_indices_batch(wards, allow_partial_failures=True)

        self.assertEqual(len(outputs), 3)

        # Ward 1: Valid & Computed
        self.assertEqual(outputs[0].area_id, "WARD_001")
        self.assertEqual(outputs[0].calculation_status, "COMPUTED")
        self.assertIsNotNone(outputs[0].htsi)

        # Ward 2: Invalid & Traceable Insufficient Data
        self.assertEqual(outputs[1].area_id, "WARD_002_BAD")
        self.assertEqual(outputs[1].calculation_status, "INSUFFICIENT_DATA")
        self.assertIsNone(outputs[1].htsi)
        self.assertIsNone(outputs[1].wbgt_c)
        self.assertIn("FAILED-VALIDATION", outputs[1].method_version)
        self.assertEqual(outputs[1].indices_computed, [])
        self.assertEqual(outputs[1].indices_skipped, ["HI", "WBGT", "UTCI"])

        # Ward 3: Valid & Computed
        self.assertEqual(outputs[2].area_id, "WARD_003")
        self.assertEqual(outputs[2].calculation_status, "COMPUTED")
        self.assertIsNotNone(outputs[2].htsi)

    def test_strict_mode_raises_on_invalid_ward(self):
        """Test strict mode raises ThermalInputValidationError on invalid ward."""
        invalid_ward = {
            "area_id": "WARD_002_BAD",
            "timestamp": "2026-05-20T14:00:00Z",
            "temperature_c": 75.0,
            "relative_humidity_pct": 50.0,
        }
        wards = [self.ward_1_data, invalid_ward, self.ward_3_data]

        with self.assertRaises(ThermalInputValidationError):
            calculate_thermal_indices_batch(wards, allow_partial_failures=False)

    def test_json_list_string_parsing_and_serialization(self):
        """Test passing a JSON string representing an array of ward records."""
        json_array = json.dumps([self.ward_1_data, self.ward_2_data])
        outputs = calculate_thermal_indices_batch(json_array)

        self.assertEqual(len(outputs), 2)
        self.assertEqual(outputs[0].area_id, "WARD_001")
        self.assertEqual(outputs[1].area_id, "WARD_002")

        # Test serializing multi-ward output to JSON array
        serialized = ThermalOutput.to_json_list(outputs, indent=2)
        self.assertIsInstance(serialized, str)
        parsed = json.loads(serialized)
        self.assertIsInstance(parsed, list)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["area_id"], "WARD_001")
        self.assertEqual(parsed[1]["area_id"], "WARD_002")

    def test_numerical_parity_with_single_record_calls(self):
        """Ensure multi-ward calculation gives identical numerical results to individual single calls."""
        wards = [self.ward_1_data, self.ward_2_data, self.ward_3_data]

        batch_outputs = calculate_thermal_indices_batch(wards)
        single_outputs = [calculate_thermal_indices(w) for w in wards]

        self.assertEqual(len(batch_outputs), len(single_outputs))

        for batch_res, single_res in zip(batch_outputs, single_outputs):
            self.assertEqual(batch_res.area_id, single_res.area_id)
            self.assertEqual(batch_res.htsi, single_res.htsi)
            self.assertEqual(batch_res.htsi_category, single_res.htsi_category)
            self.assertEqual(batch_res.wbgt_c, single_res.wbgt_c)
            self.assertEqual(batch_res.utci_c, single_res.utci_c)
            self.assertEqual(batch_res.heat_index_c, single_res.heat_index_c)
            self.assertEqual(batch_res.hi_score, single_res.hi_score)
            self.assertEqual(batch_res.wbgt_score, single_res.wbgt_score)
            self.assertEqual(batch_res.utci_score, single_res.utci_score)
            self.assertEqual(batch_res.weights_used, single_res.weights_used)


if __name__ == "__main__":
    unittest.main()
