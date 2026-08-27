import pytest
import json
from backend.wiring.ward_context_store.store import WardContextStore
from backend.wardfilter.schemas import WardFilterResult, WardContext
from backend.thermalengine.schemas import ThermalOutput
from backend.mortality.schemas import MortalityOutput, InfoPoolRecord, ResourcePoolRecord

from backend.prediction.schemas import PredictionOutput

def test_store_and_retrieve_and_freshness(tmp_path):
    store = WardContextStore(data_dir=tmp_path)
    
    thermal = ThermalOutput(area_id="WARD_TEST", timestamp="2026-05-20T14:00:00Z", heat_index_c=35.0, utci_c=34.0, wbgt_c=30.0, htsi=50.0, htsi_category="HIGH")
    prediction = PredictionOutput(area_id="WARD_TEST", prediction_generated_at="2026-05-20T14:00:00Z", forecast_for="2026-05-20T14:00:00Z", forecast_horizon_days=1, thermal_hazard_score=0.9, predicted_max_utci_c=36.0, thermal_stress_level="HIGH", model_name="test", model_version="v1")
    mortality = MortalityOutput(area_id="WARD_TEST", timestamp="2026-05-20T14:00:00Z", risk_level="MODERATE")
    info = InfoPoolRecord(area_id="WARD_TEST", population=1000)
    resource = ResourcePoolRecord(area_id="WARD_TEST", hospital_count=2)
    
    context = WardContext(
        area_id="WARD_TEST",
        timestamp="2026-05-20T14:00:00Z",
        thermal=thermal,
        prediction=prediction,
        mortality=mortality,
        info_pool=info,
        resource_pool=resource
    )
    
    result = WardFilterResult(
        area_id="WARD_TEST",
        timestamp="2026-05-20T14:00:00Z",
        severity="HIGH",
        context=context
    )
    
    store.put("WARD_TEST", result)
    
    # Retrieve in a completely new instance to prove persistence
    store2 = WardContextStore(data_dir=tmp_path)
    retrieved = store2.get("WARD_TEST")
    
    assert retrieved is not None
    assert retrieved.area_id == "WARD_TEST"
    assert retrieved.severity == "HIGH"
    
    retrieved_context = retrieved.context
    assert retrieved_context is not None
    assert retrieved_context.area_id == "WARD_TEST"
    assert retrieved_context.thermal.htsi_category == "HIGH"
    assert retrieved_context.mortality.risk_level == "MODERATE"
    assert retrieved_context.info_pool.population == 1000
    assert retrieved_context.resource_pool.hospital_count == 2
    
    assert retrieved_context.prediction is not None
    assert retrieved_context.prediction.area_id == "WARD_TEST"
    assert retrieved_context.prediction.thermal_hazard_score == 0.9

    # Test freshness API
    freshness = store2.get_freshness("WARD_TEST")
    assert freshness["area_id"] == "WARD_TEST"
    assert freshness["is_fresh_determinable"] is True
    assert freshness["observation_timestamp"] == "2026-05-20T14:00:00Z"
    assert "generated_timestamp" in freshness

def test_missing_area_id(tmp_path):
    from backend.wiring.ward_context_store.store import ContextNotFoundError
    store = WardContextStore(data_dir=tmp_path)
    with pytest.raises(ContextNotFoundError):
        store.get("NON_EXISTENT")
    
    freshness = store.get_freshness("NON_EXISTENT")
    assert freshness["status"] == "NOT_FOUND"

def test_backward_compatibility(tmp_path):
    store = WardContextStore(data_dir=tmp_path)
    
    # Manually write an old-style JSON file without the metadata wrapper
    old_data = {
        "area_id": "WARD_OLD",
        "timestamp": "2025-01-01T00:00:00Z",
        "severity": "LOW",
        "message": "Old record",
        "recommended_actions": [],
        "triggered_conditions": [],
        "context": None,
        "calculation_status": "COMPUTED",
        "method_version": "WARD_FILTER_MVP"
    }
    
    file_path = tmp_path / "WARD_OLD.json"
    with file_path.open("w", encoding="utf-8") as f:
        json.dump(old_data, f)
        
    # Test retrieval
    retrieved = store.get("WARD_OLD")
    assert retrieved is not None
    assert retrieved.area_id == "WARD_OLD"
    assert retrieved.severity == "LOW"
    
    # Test freshness API on old format
    freshness = store.get_freshness("WARD_OLD")
    assert freshness["area_id"] == "WARD_OLD"
    assert freshness["is_fresh_determinable"] is False
    assert freshness["observation_timestamp"] == "2025-01-01T00:00:00Z"
    assert freshness["generated_timestamp"] is None
    assert freshness["status"] == "MISSING_METADATA"
