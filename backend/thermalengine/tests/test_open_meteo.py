import unittest
from unittest.mock import patch, MagicMock
import httpx
from backend.thermalengine.data_acquisition.open_meteo_provider import OpenMeteoProvider

class TestOpenMeteoProvider(unittest.TestCase):
    def setUp(self):
        self.provider = OpenMeteoProvider()
        
    @patch('httpx.Client.get')
    def test_fetch_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "current": {
                "time": "2026-05-20T14:00Z",
                "temperature_2m": 35.0,
                "relative_humidity_2m": 45.0,
                "wind_speed_10m": 3.0,
                "shortwave_radiation": 800.0
            }
        }
        mock_get.return_value = mock_resp
        
        results = self.provider.fetch_current_conditions(["WARD_001", "WARD_002"])
        
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["source_area_id"], "WARD_001")
        self.assertEqual(results[0]["source_temperature"], 35.0)
        self.assertEqual(results[1]["source_area_id"], "WARD_002")

    @patch('httpx.Client.get')
    def test_rate_limit(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_get.return_value = mock_resp
        
        with self.assertRaises(Exception) as context:
            self.provider.fetch_current_conditions(["WARD_001"])
        self.assertIn("Rate limit", str(context.exception))

    @patch('httpx.Client.get')
    def test_malformed_response(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"error": "true"}
        mock_get.return_value = mock_resp
        
        with self.assertRaises(Exception) as context:
            self.provider.fetch_current_conditions(["WARD_001"])
        self.assertIn("Malformed response", str(context.exception))

    @patch('httpx.Client.get')
    def test_network_failure(self, mock_get):
        mock_get.side_effect = httpx.RequestError("Connection timeout", request=MagicMock())
        
        with self.assertRaises(Exception) as context:
            self.provider.fetch_current_conditions(["WARD_001"])
        self.assertIn("Network failure", str(context.exception))
