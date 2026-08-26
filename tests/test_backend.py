import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.calculations.heat_index import calculate_heat_index

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200

def test_analysis_safe():
    payload = {
        "temperature_c": 22.0,
        "relative_humidity": 45.0,
        "location_id": "ward-1"
    }
    response = client.post("/api/v1/analysis", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["htsi"]["category"] == "SAFE"

def test_analysis_danger():
    payload = {
        "temperature_c": 40.0,
        "relative_humidity": 65.0,
        "location_id": "ward-1"
    }
    response = client.post("/api/v1/analysis", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["htsi"]["category"] in ["DANGER", "CRITICAL"]

def test_heat_index():
    hi = calculate_heat_index(35.0, 50.0)
    assert 40.0 < hi < 42.0
