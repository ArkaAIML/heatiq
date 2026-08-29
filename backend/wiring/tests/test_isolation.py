import pytest
from unittest.mock import patch, MagicMock

from backend.wiring.wire1 import process_location
from backend.wiring.wire2 import get_recommendation
from backend.wiring.wire2_store.context_store import Wire2ContextStore
from backend.wiring.wire2_store.store import RecommendationStore

@patch("backend.wiring.wire1.GlobalDataAcquisitionAdapter")
@patch("backend.wiring.wire1.get_canonical_info_pool")
@patch("backend.wiring.wire1.get_canonical_resource_pool")
@patch("backend.wiring.wire2.RecommendationAdapter")
def test_cross_ward_isolation_and_wire2_handoff(
    mock_rec_adapter,
    mock_resource_pool,
    mock_info_pool,
    mock_data_adapter
):
    # 1. Setup mock data
    mock_data_adapter.return_value.acquire_for_location.return_value = MagicMock(
        provider="mock",
        timestamp="2026-05-20T14:00:00Z"
    )
    
    import pandas as pd
    
    # 2 wards
    mock_info_pool.return_value = pd.DataFrame([
        {"area_id": "WARD_A", "population": 100},
        {"area_id": "WARD_B", "population": 200}
    ])
    
    mock_resource_pool.return_value = pd.DataFrame([
        {"area_id": "WARD_A", "hospital_count": 1},
        {"area_id": "WARD_B", "hospital_count": 2}
    ])
    
    mock_rec_adapter.return_value.generate_recommendation.return_value = MagicMock(
        to_dict=lambda: {"status": "SUCCESS"}
    )
    
    # Clear Wire 2 Context Store to ensure a clean slate
    import shutil
    w2_store = Wire2ContextStore()
    if w2_store.data_dir.exists():
        shutil.rmtree(w2_store.data_dir)
    w2_store.data_dir.mkdir(parents=True, exist_ok=True)
    
    w2_rec = RecommendationStore()
    if w2_rec.data_dir.exists():
        shutil.rmtree(w2_rec.data_dir)
    w2_rec.data_dir.mkdir(parents=True, exist_ok=True)
    
    # 2. Execute Wire 1
    process_location("TestCity", allow_partial_failures=False)
    
    # 3. Verify Wire 2 received the context for both wards
    ctx_a = w2_store.get_ward_context("WARD_A")
    assert ctx_a.area_id == "WARD_A"
    
    ctx_b = w2_store.get_ward_context("WARD_B")
    assert ctx_b.area_id == "WARD_B"
    
    # 4. Prove Wire 2 operates completely independently of Wire 1
    # We will delete/hide the WardContextStore (Wire 1 DB) to prove Wire 2 doesn't use it
    from backend.wiring.ward_context_store.store import WardContextStore
    w1_store = WardContextStore()
    if w1_store.data_dir.exists():
        shutil.rmtree(w1_store.data_dir)
        
    # Execute Wire 2 for WARD_A
    rec_a = get_recommendation("WARD_A", force_refresh=True)
    assert rec_a["status"] == "SUCCESS"
    
    # Execute Wire 2 for WARD_B
    rec_b = get_recommendation("WARD_B", force_refresh=True)
    assert rec_b["status"] == "SUCCESS"
    
    # Verify the Recommendation Adapter received the right context (Isolation check)
    calls = mock_rec_adapter.return_value.generate_recommendation.call_args_list
    assert len(calls) == 2
    
    # First call was WARD_A, Second call was WARD_B
    # calls[0][0][0] is the filtered input dict
    assert calls[0][0][0]["area_id"] == "WARD_A"
    assert calls[1][0][0]["area_id"] == "WARD_B"
