import unittest
from unittest.mock import patch
import os
from backend.thermalengine.data_acquisition.adapter import AtmosphericDataAcquisitionAdapter
from backend.thermalengine.data_acquisition.mock_provider import MockAtmosphericProvider
from backend.thermalengine.schemas import ThermalInput, ThermalOutput
from backend.thermalengine.data_acquisition import thermal_engine_for_location

os.environ["HEATIQ_WEATHER_PROVIDER"] = "mock"

class TestAtmosphericDataAcquisition(unittest.TestCase):
    
    @patch('backend.thermalengine.data_acquisition.adapter.get_canonical_info_pool')
    def test_location_request_to_ward_resolution(self, mock_get_pool):
        import pandas as pd
        mock_get_pool.return_value = pd.DataFrame({"area_id": ["WARD_001", "WARD_002"]})
        
        adapter = AtmosphericDataAcquisitionAdapter()
        wards = adapter._resolve_wards("Bhubaneswar")
        
        self.assertEqual(wards, ["WARD_001", "WARD_002"])
        mock_get_pool.assert_called_once_with("Bhubaneswar")

    @patch('backend.thermalengine.data_acquisition.adapter.get_canonical_info_pool')
    def test_multiple_wards_producing_multiple_thermal_inputs(self, mock_get_pool):
        import pandas as pd
        mock_get_pool.return_value = pd.DataFrame({"area_id": ["WARD_001", "WARD_002"]})
        
        adapter = AtmosphericDataAcquisitionAdapter()
        inputs = adapter.acquire_for_location("Bhubaneswar")
        
        self.assertEqual(len(inputs), 2)
        self.assertIsInstance(inputs[0], ThermalInput)
        self.assertIsInstance(inputs[1], ThermalInput)
        
        # Test area_id preservation
        self.assertEqual(inputs[0].area_id, "WARD_001")
        self.assertEqual(inputs[1].area_id, "WARD_002")
        
        # Test field normalization (mock returns temp 38.5, humidity 45.0, wind 2.5, solar 800.0)
        self.assertEqual(inputs[0].temperature_c, 38.5)
        self.assertEqual(inputs[0].relative_humidity_pct, 45.0)
        self.assertEqual(inputs[0].wind_speed_ms, 2.5)
        self.assertEqual(inputs[0].solar_radiation_wm2, 800.0)

    @patch('backend.thermalengine.data_acquisition.adapter.AtmosphericDataAcquisitionAdapter._resolve_wards', return_value=["WARD_X"])
    def test_missing_optional_fields(self, mock_resolve):
        class IncompleteMockProvider(MockAtmosphericProvider):
            def fetch_current_conditions(self, area_ids):
                return [{"source_area_id": "WARD_X", "source_timestamp": "2026-05-20T14:00:00Z", "source_temperature": 35.0, "source_humidity": 50.0}]
        
        adapter = AtmosphericDataAcquisitionAdapter(provider=IncompleteMockProvider())
        inputs = adapter.acquire_for_location("Bhubaneswar")
        
        self.assertEqual(len(inputs), 1)
        self.assertEqual(inputs[0].temperature_c, 35.0)
        self.assertIsNone(inputs[0].wind_speed_ms)
        self.assertIsNone(inputs[0].solar_radiation_wm2)

    @patch('backend.thermalengine.data_acquisition.adapter.AtmosphericDataAcquisitionAdapter._resolve_wards', return_value=["WARD_X"])
    def test_missing_required_fields_produces_insufficient_data(self, mock_resolve):
        class BadMockProvider(MockAtmosphericProvider):
            def fetch_current_conditions(self, area_ids):
                # Missing humidity
                return [{"source_area_id": "WARD_X", "source_timestamp": "2026-05-20T14:00:00Z", "source_temperature": 35.0}]
        
        adapter = AtmosphericDataAcquisitionAdapter(provider=BadMockProvider())
        outputs = thermal_engine_for_location("Bhubaneswar", adapter=adapter)
        
        self.assertEqual(len(outputs), 1)
        self.assertEqual(outputs[0].calculation_status, "INSUFFICIENT_DATA")

    @patch('backend.thermalengine.data_acquisition.adapter.get_canonical_info_pool')
    def test_end_to_end_facade(self, mock_get_pool):
        import pandas as pd
        mock_get_pool.return_value = pd.DataFrame({"area_id": ["WARD_001", "WARD_002"]})
        
        outputs = thermal_engine_for_location("Bhubaneswar")
        self.assertEqual(len(outputs), 2)
        
        self.assertIsInstance(outputs[0], ThermalOutput)
        self.assertIsInstance(outputs[1], ThermalOutput)
        
        self.assertEqual(outputs[0].area_id, "WARD_001")
        self.assertEqual(outputs[1].area_id, "WARD_002")
        self.assertEqual(outputs[0].calculation_status, "COMPUTED")
        self.assertEqual(outputs[1].calculation_status, "COMPUTED")

if __name__ == '__main__':
    unittest.main()
