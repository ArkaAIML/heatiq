import unittest
from unittest.mock import patch, MagicMock
from cli.client import HeatIQClient

class TestCLIClient(unittest.TestCase):
    def setUp(self):
        self.client = HeatIQClient()

    @patch("cli.client.requests.Session.get")
    def test_check_health_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp
        
        self.assertTrue(self.client.check_health())

    @patch("cli.client.requests.Session.get")
    def test_check_health_failure(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp
        
        self.assertFalse(self.client.check_health())

    @patch("cli.client.requests.Session.post")
    def test_process_location_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": [{"area_id": "WARD_001"}], "request_id": "123"}
        mock_post.return_value = mock_resp
        
        success, data, err = self.client.process_location("Bhubaneswar")
        self.assertTrue(success)
        self.assertEqual(data["request_id"], "123")
        self.assertEqual(err, "Success")

    @patch("cli.client.requests.Session.post")
    def test_process_area_id_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": {"severity": "HIGH"}, "request_id": "123"}
        mock_post.return_value = mock_resp
        
        success, data, err = self.client.process_area_id("WARD_001")
        self.assertTrue(success)
        self.assertEqual(data["results"]["severity"], "HIGH")

    @patch("cli.client.requests.Session.post")
    def test_wire1_prerequisite_rejection(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 422
        mock_resp.json.return_value = {"detail": "ward_context_not_available"}
        mock_post.return_value = mock_resp
        
        success, data, err = self.client.process_area_id("WARD_999")
        self.assertFalse(success)
        self.assertEqual(err, "ward_context_not_available")

    @patch("cli.client.requests.Session.post")
    def test_invalid_api_key(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_post.return_value = mock_resp
        
        success, data, err = self.client.process_area_id("WARD_001")
        self.assertFalse(success)
        self.assertEqual(err, "Invalid or revoked API key")

if __name__ == "__main__":
    unittest.main()
