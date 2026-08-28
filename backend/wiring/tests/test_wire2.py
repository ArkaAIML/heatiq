import pytest
from unittest.mock import patch, MagicMock
from backend.wiring.wire2 import get_recommendation
from backend.wardfilter.schemas import WardContext, WardFilterResult
from backend.thermalengine.schemas import ThermalOutput
from backend.mortality import MortalityOutput, InfoPoolRecord, ResourcePoolRecord
from backend.recommendation.schemas import RecommendationOutput, FailedRecommendationOutput

@patch("backend.wiring.wire2.Wire2ContextStore")
@patch("backend.wiring.wire2.RecommendationAdapter")
def test_get_recommendation_success(mock_adapter_class, mock_store_class):
    # Setup
    t_out = ThermalOutput(area_id="WARD_017", timestamp="2026-05-20T14:00:00Z", heat_index_c=0.0, utci_c=0.0, wbgt_c=0.0, htsi=0.0, htsi_category="MODERATE", calculation_status="COMPUTED")
    m_out = MortalityOutput(area_id="WARD_017", timestamp="2026-05-20T14:00:00Z", risk_score=0.0, risk_level="LOW")
    info = InfoPoolRecord(area_id="WARD_017", population=100)
    res = ResourcePoolRecord(area_id="WARD_017", hospital_count=1)
    
    mock_context = WardContext(
        area_id="WARD_017",
        timestamp="2026-05-20T14:00:00Z",
        thermal=t_out,
        prediction=None,
        mortality=m_out,
        info_pool=info,
        resource_pool=res
    )
    
    mock_wf_result = WardFilterResult(
        area_id="WARD_017",
        timestamp="2026-05-20T14:00:00Z",
        severity="HIGH",
        context=mock_context
    )
    
    mock_store = mock_store_class.return_value
    mock_store.get_ward_filter_result.return_value = mock_wf_result
    
    mock_adapter = mock_adapter_class.return_value
    mock_adapter.generate_recommendation.return_value = RecommendationOutput(
        area_id="WARD_017",
        generated_at="2026-05-20T14:00:00Z",
        situation_summary="Test",
        severity="HIGH",
        status="DUMMY",
        message="Recommendation generated successfully."
    )
    
    # Execute
    result_data = get_recommendation("WARD_017", force_refresh=True)
    
    # Verify
    assert result_data["area_id"] == "WARD_017"
    assert result_data["message"] == "Recommendation generated successfully."
    assert "freshness" in result_data
    mock_adapter.generate_recommendation.assert_called_once_with(mock_context)


def test_get_recommendation_missing_area_id():
    res = get_recommendation("")
    assert res["status"] == "ERROR"
    assert "area_id is required" in res["message"]


@patch("backend.wiring.wire2.Wire2ContextStore")
def test_get_recommendation_missing_context(mock_store_class):
    from backend.wiring.wire2_store.context_store import Wire2ContextNotFoundError
    mock_store = mock_store_class.return_value
    mock_store.get_ward_filter_result.side_effect = Wire2ContextNotFoundError("Not found")
    
    res = get_recommendation("WARD_999", force_refresh=True)
    
    assert res["status"] == "NOT_FOUND"
    assert "No context found" in res["message"]
    assert res["area_id"] == "WARD_999"


@patch("backend.wiring.wire2.Wire2ContextStore")
@patch("backend.wiring.wire2.RecommendationAdapter")
def test_get_recommendation_engine_failure(mock_adapter_class, mock_store_class):
    t_out = ThermalOutput(area_id="WARD_017", timestamp="2026-05-20T14:00:00Z", heat_index_c=0.0, utci_c=0.0, wbgt_c=0.0, htsi=0.0, htsi_category="MODERATE", calculation_status="COMPUTED")
    m_out = MortalityOutput(area_id="WARD_017", timestamp="2026-05-20T14:00:00Z", risk_score=0.0, risk_level="LOW")
    info = InfoPoolRecord(area_id="WARD_017", population=100)
    res = ResourcePoolRecord(area_id="WARD_017", hospital_count=1)
    
    mock_context = WardContext(
        area_id="WARD_017",
        timestamp="2026-05-20T14:00:00Z",
        thermal=t_out,
        prediction=None,
        mortality=m_out,
        info_pool=info,
        resource_pool=res
    )
    
    mock_store = mock_store_class.return_value
    mock_store.get_ward_context.return_value = mock_context
    
    mock_adapter = mock_adapter_class.return_value
    mock_adapter.generate_recommendation.return_value = FailedRecommendationOutput(
        area_id="WARD_017",
        status="ERROR",
        message="Recommendation Engine failed: Model exploded"
    )
    
    result_data = get_recommendation("WARD_017", force_refresh=True)
    
    assert result_data["status"] == "ERROR"
    assert "Model exploded" in result_data["message"]
    assert result_data["area_id"] == "WARD_017"
