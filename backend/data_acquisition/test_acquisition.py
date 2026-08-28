import unittest
from unittest.mock import patch
import os
from backend.data_acquisition.adapter import GlobalDataAcquisitionAdapter
from backend.data_acquisition.schemas import CanonicalAcquiredData
from backend.thermalengine.schemas import ThermalInput, ThermalOutput

class MockAtmosphericProvider:
    def fetch_current_and_history(self):
        return {
            "current": {
                "temperature_2m": 35.0,
                "relative_humidity_2m": 60.0,
                "wind_speed_10m": 5.0,
                "shortwave_radiation": 800.0,
                "surface_pressure": 1013.25,
                "dew_point_2m": 25.0
            }
        }


os.environ["HEATIQ_WEATHER_PROVIDER"] = "mock"

class TestAtmosphericDataAcquisition(unittest.TestCase):
    
    def test_acquire_for_location(self):
        adapter = GlobalDataAcquisitionAdapter(provider=MockAtmosphericProvider())
        canonical = adapter.acquire_for_location("Bhubaneswar")
        
        self.assertIsInstance(canonical, CanonicalAcquiredData)
        self.assertEqual(canonical.location, "Bhubaneswar")
        self.assertEqual(canonical.temperature_c, 35.0)
        self.assertEqual(canonical.relative_humidity_pct, 60.0)
        self.assertEqual(canonical.wind_speed_ms, 5.0)
        self.assertEqual(canonical.solar_radiation_wm2, 800.0)
        self.assertEqual(canonical.surface_pressure_pa, 1013.25)
        self.assertEqual(canonical.dew_point_c, 25.0)

if __name__ == '__main__':
    unittest.main()
