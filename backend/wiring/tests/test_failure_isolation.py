import pytest
import json
from pathlib import Path
from backend.wiring.wire1 import process_location
from backend.wiring.wire2 import get_recommendation
from backend.wiring.ward_context_store.store import WardContextStore
from datalake.core.cache_manager import DATA_DIR
import pandas as pd

# We use the existing mock provider in AtmosphericDataAcquisitionAdapter
# and intercept to force errors.

class FailingProvider:
    def fetch_current_conditions(self, area_ids):
        raise Exception("Simulated network timeout")

class PartialFailingProvider:
    def fetch_current_conditions(self, area_ids):
        res = []
        for a in area_ids:
            if a == "WARD_002":
                # Missing required field
                res.append({"source_area_id": a, "source_timestamp": "2024-01-01T00:00:00Z"})
            else:
                res.append({"source_area_id": a, "source_timestamp": "2024-01-01T00:00:00Z", "source_temperature": 35.0, "source_humidity": 50.0})
        return res

def test_atmospheric_provider_total_failure(monkeypatch):
    from backend.data_acquisition.adapter import GlobalDataAcquisitionAdapter
    monkeypatch.setattr(AtmosphericDataAcquisitionAdapter, "__init__", lambda self: setattr(self, "provider", FailingProvider()))
    
    # Run wire1
    results = process_location("Bhubaneswar")
    assert len(results) > 0
    # All wards should be INSUFFICIENT_DATA due to thermal missing
    for r in results:
        assert r.calculation_status == "INSUFFICIENT_DATA"
        assert "MISSING_REQUIRED_DATA" in r.triggered_conditions

def test_partial_failure_isolation(monkeypatch):
    from backend.data_acquisition.adapter import GlobalDataAcquisitionAdapter
    monkeypatch.setattr(AtmosphericDataAcquisitionAdapter, "__init__", lambda self: setattr(self, "provider", PartialFailingProvider()))
    
    results = process_location("Bhubaneswar")
    assert len(results) > 0
    
    res_map = {r.area_id: r for r in results}
    
    # WARD_002 should fail
    assert res_map["WARD_002"].calculation_status == "INSUFFICIENT_DATA"
    
    # Other wards should succeed
    for a, r in res_map.items():
        if a != "WARD_002":
            assert r.calculation_status == "COMPUTED"
            assert r.severity is not None

def test_prediction_total_failure(monkeypatch):
    from backend.prediction.adapter import PredictionAdapter
    def fail_predict(*args, **kwargs):
        raise Exception("ML Engine crashed")
    monkeypatch.setattr(PredictionAdapter, "predict_batch", fail_predict)
    
    results = process_location("Bhubaneswar")
    assert len(results) > 0
    for r in results:
        # Prediction is optional, so thermal and mortality should still classify it
        assert r.calculation_status == "COMPUTED"
        # Since dummy prediction normally raises severity, without it, severity might be lower but not NONE
        assert r.severity is not None

def test_datalake_source_failure(monkeypatch):
    from backend.wiring.wire1 import process_location
    import backend.wiring.wire1
    
    def fake_get_canonical_info_pool(location):
        raise Exception("Database dropped")
        
    monkeypatch.setattr(backend.wiring.wire1, "get_canonical_info_pool", fake_get_canonical_info_pool)
    
    results = process_location("Bhubaneswar")
    assert len(results) > 0
    for r in results:
        assert r.calculation_status == "INSUFFICIENT_DATA"
        assert "SOURCE_UNAVAILABLE: InfoPoolRecord" in r.method_version

def test_datalake_empty_dataset(monkeypatch):
    from backend.wiring.wire1 import process_location
    import backend.wiring.wire1
    import pandas as pd
    
    def fake_get_canonical_info_pool(location):
        return pd.DataFrame()
        
    monkeypatch.setattr(backend.wiring.wire1, "get_canonical_info_pool", fake_get_canonical_info_pool)
    
    results = process_location("Bhubaneswar")
    assert len(results) > 0
    for r in results:
        assert r.calculation_status == "INSUFFICIENT_DATA"
        assert "MISSING_DATA: InfoPoolRecord" in r.method_version

def test_store_read_missing():
    res = get_recommendation("NONEXISTENT_WARD_999")
    assert res["status"] == "NOT_FOUND"

def test_store_read_corrupt(tmp_path, monkeypatch):
    # Override store path
    monkeypatch.setattr(WardContextStore, "__init__", lambda self, data_dir=tmp_path: setattr(self, "data_dir", tmp_path) or tmp_path.mkdir(parents=True, exist_ok=True))
    store = WardContextStore()
    
    p = store._get_file_path("CORRUPT_WARD")
    p.write_text("invalid json {")
    
    res = get_recommendation("CORRUPT_WARD")
    assert res["status"] == "CORRUPT_RECORD"
