import pytest
from unittest.mock import patch, MagicMock
from backend.wiring.wire2 import get_recommendation
from backend.wardfilter.schemas import WardContext
from backend.thermalengine.schemas import ThermalOutput
from backend.mortality import MortalityOutput, InfoPoolRecord, ResourcePoolRecord
from backend.recommendation.schemas import RecommendationOutput, FailedRecommendationOutput

@patch("backend.wiring.wire2.WardContextStore")
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
    
    mock_ward_result = MagicMock()
    mock_ward_result.context = mock_context
    
    mock_store = mock_store_class.return_value
    mock_store.get.return_value = mock_ward_result
    mock_store.get_freshness.return_value = {
        "area_id": "WARD_017",
        "is_fresh_determinable": True,
        "observation_timestamp": "2026-05-20T14:00:00Z",
        "generated_timestamp": "2026-05-20T14:00:01Z"
    }
    
    mock_adapter = mock_adapter_class.return_value
    mock_adapter.generate_recommendation.return_value = RecommendationOutput(
        area_id="WARD_017",
        forecast_for="2026-05-20T14:00:00Z",
        priority="UNKNOWN",
        actions=[],
        reason_codes=[],
        status="DUMMY",
        message="Recommendation generated successfully."
    )
    
    # Execute
    result_data = get_recommendation("WARD_017")
    
    # Verify
    assert result_data["area_id"] == "WARD_017"
    assert result_data["message"] == "Recommendation generated successfully."
    assert "freshness" in result_data
    assert result_data["freshness"]["is_fresh_determinable"] is True
    mock_adapter.generate_recommendation.assert_called_once_with(mock_context)


def test_get_recommendation_missing_area_id():
    res = get_recommendation("")
    assert res["status"] == "ERROR"
    assert "area_id is required" in res["message"]


@patch("backend.wiring.wire2.WardContextStore")
def test_get_recommendation_missing_context(mock_store_class):
    mock_store = mock_store_class.return_value
    mock_store.get.return_value = None
    
    res = get_recommendation("WARD_999")
    
    assert res["status"] == "ERROR"
    assert "No context found" in res["message"]
    assert res["area_id"] == "WARD_999"


@patch("backend.wiring.wire2.WardContextStore")
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
    
    mock_ward_result = MagicMock()
    mock_ward_result.context = mock_context
    
    mock_store = mock_store_class.return_value
    mock_store.get.return_value = mock_ward_result
    mock_store.get_freshness.return_value = {}
    
    mock_adapter = mock_adapter_class.return_value
    mock_adapter.generate_recommendation.return_value = FailedRecommendationOutput(
        area_id="WARD_017",
        status="ERROR",
        message="Recommendation Engine failed: Model exploded"
    )
    
    result_data = get_recommendation("WARD_017")
    
    assert result_data["status"] == "ERROR"
    assert "Model exploded" in result_data["message"]
    assert result_data["area_id"] == "WARD_017"
