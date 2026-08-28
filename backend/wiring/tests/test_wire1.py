import pytest
from unittest.mock import patch, MagicMock
from backend.wiring.wire1 import process_location
from backend.thermalengine.schemas import ThermalOutput
from backend.mortality.schemas import MortalityOutput
from backend.wardfilter.schemas import WardFilterResult
from backend.mortality.schemas import InfoPoolRecord, ResourcePoolRecord

@patch("backend.wiring.wire1.WardContextStore")
@patch("backend.wiring.wire1.GlobalDataAcquisitionAdapter")
@patch("backend.wiring.wire1.get_canonical_info_pool")
@patch("backend.wiring.wire1.get_canonical_resource_pool")
@patch("backend.wiring.wire1.calculate_thermal_indices")
@patch("backend.wiring.wire1.PredictionAdapter")
@patch("backend.wiring.wire1.calculate_mortality_risk_batch")
@patch("backend.wiring.wire1.filter_wards")
def test_process_location_flow(
    mock_filter_wards,
    mock_calculate_mortality,
    mock_adapter_class_pred,
    mock_calculate_thermal,
    mock_get_resource,
    mock_get_info,
    mock_adapter_class_acq,
    mock_store_class
):
    # Setup mocks
    mock_store = mock_store_class.return_value
    mock_adapter = mock_adapter_class_acq.return_value
    mock_adapter.acquire_for_location.return_value = [{"area_id": "WARD_001"}]
    
    mock_info_df = MagicMock()
    mock_info_df.empty = False
    mock_info_df.to_dict.return_value = [{"area_id": "WARD_001", "population": 100}]
    mock_get_info.return_value = mock_info_df
    
    mock_resource_df = MagicMock()
    mock_resource_df.empty = False
    mock_resource_df.to_dict.return_value = [{"area_id": "WARD_001", "hospital_count": 2}]
    mock_get_resource.return_value = mock_resource_df

    t_out = ThermalOutput(area_id="WARD_001", timestamp="2026-05-20T14:00:00Z", heat_index_c=0.0, utci_c=0.0, wbgt_c=0.0, htsi=0.0, htsi_category="MODERATE", calculation_status="COMPUTED")
    mock_calculate_thermal.return_value = [t_out]
    
    from backend.prediction.schemas import PredictionOutput
    p_out = PredictionOutput(area_id="WARD_001", prediction_generated_at="2026-05-20T14:00:00Z", forecast_for="2026-05-20T14:00:00Z", forecast_horizon_days=1, thermal_hazard_score=0.9, predicted_max_utci_c=36.0, thermal_stress_level="HIGH", model_name="test", model_version="v1")
    mock_adapter_class_pred.predict_batch.return_value = [p_out]
    
    m_out = MortalityOutput(area_id="WARD_001", timestamp="2026-05-20T14:00:00Z", risk_level="HIGH")
    mock_calculate_mortality.return_value = [m_out]
    
    wf_out = WardFilterResult(area_id="WARD_001", timestamp="2026-05-20T14:00:00Z", calculation_status="COMPUTED", method_version="v1")
    mock_filter_wards.return_value = [wf_out]

    # Execute
    results = process_location("Bhubaneswar")

    # Verify
    assert len(results) == 1
    assert results[0].area_id == "WARD_001"
    
    # Assert orchestration sequence
    mock_adapter.acquire_for_location.assert_called_once_with("Bhubaneswar")
    mock_get_info.assert_called_once_with("Bhubaneswar")
    mock_get_resource.assert_called_once_with("Bhubaneswar")
    
    mock_calculate_thermal.assert_called_once()
    mock_adapter_class_pred.predict_batch.assert_called_once_with([t_out])
    mock_calculate_mortality.assert_called_once()
    mock_filter_wards.assert_called_once()
    
    # Assert area_id alignment in filter_wards
    kwargs = mock_filter_wards.call_args.kwargs
    assert kwargs["thermal_outputs"][0].area_id == "WARD_001"
    assert kwargs["mortality_outputs"][0].area_id == "WARD_001"
    assert kwargs["info_records"][0]["area_id"] == "WARD_001"
    assert kwargs["resource_records"][0]["area_id"] == "WARD_001"
    
    # Verify the context was stored
    mock_store.put.assert_called_once_with("WARD_001", wf_out)
