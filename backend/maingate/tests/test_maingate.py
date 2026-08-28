import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from backend.maingate.app import app
from backend.maingate.database import generate_key, init_db, revoke_key

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_db():
    init_db()

def test_api_key_generation_and_validation():
    # 1. Generate key
    resp = client.post("/api/keys", json={"label": "Test Key"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "active"
    
    raw_key = data["api_key"]
    
    # 2. Use invalid key
    bad_resp = client.post("/api/process", headers={"X-API-Key": "hk_invalid"}, json={"location": "Test"})
    assert bad_resp.status_code == 403
    
    # 3. Revoke key
    client.request("DELETE", "/api/keys", json={"key_id": data["key_id"]})
    
    # 4. Key should now be rejected
    revoked_resp = client.post("/api/process", headers={"X-API-Key": raw_key}, json={"location": "Test"})
    assert revoked_resp.status_code == 403

def test_missing_api_key_rejected():
    resp = client.post("/api/process", json={"location": "Test"})
    assert resp.status_code == 401

@patch("backend.maingate.routes.process_location")
def test_place_name_routing(mock_process):
    _, raw_key = generate_key("Test")
    
    # Mock Wire 1 returning an empty list
    mock_process.return_value = []
    
    resp = client.post("/api/process", headers={"X-API-Key": raw_key}, json={"location": "Bhubaneswar"})
    
    assert resp.status_code == 200
    assert resp.json()["route"] == "PLACE_NAME"
    mock_process.assert_called_once_with("Bhubaneswar", allow_partial_failures=True)

@patch("backend.maingate.routes.get_recommendation")
def test_area_id_routing_success(mock_rec):
    _, raw_key = generate_key("Test")
    
    # Mock Wire 2 returning a success dict
    mock_rec.return_value = {"status": "SUCCESS"}
    
    resp = client.post("/api/process", headers={"X-API-Key": raw_key}, json={"area_id": "WARD_001"})
    
    assert resp.status_code == 200
    assert resp.json()["route"] == "AREA_ID"
    mock_rec.assert_called_once_with("WARD_001")

@patch("backend.maingate.routes.get_recommendation")
def test_area_id_routing_wire1_prerequisite_failure(mock_rec):
    _, raw_key = generate_key("Test")
    
    # Mock Wire 2 indicating Wire 1 hasn't run yet
    mock_rec.return_value = {"status": "NOT_FOUND"}
    
    resp = client.post("/api/process", headers={"X-API-Key": raw_key}, json={"area_id": "WARD_999"})
    
    assert resp.status_code == 422
    assert "ward_context_not_available" in resp.json()["detail"]
    mock_rec.assert_called_once_with("WARD_999")
