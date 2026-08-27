import pytest
from backend.thermalengine.schemas import ThermalOutput
from backend.prediction.adapter import PredictionAdapter
from backend.prediction.schemas import PredictionOutput

def test_prediction_adapter_canonical_output():
    t_out = ThermalOutput(area_id="WARD_001", timestamp="2026-05-20T14:00:00Z", heat_index_c=0.0, utci_c=0.0, wbgt_c=0.0, htsi=0.0, htsi_category="MODERATE", calculation_status="COMPUTED")
    
    results = PredictionAdapter.predict_batch([t_out])
    
    assert len(results) == 1
    pred = results[0]
    
    assert isinstance(pred, PredictionOutput)
    assert pred.area_id == "WARD_001"
    assert pred.forecast_for == "2026-05-20T14:00:00Z"
    assert pred.thermal_hazard_score == 0.0
    assert pred.model_name == "dummyml"

def test_prediction_adapter_multi_ward():
    t_out_1 = ThermalOutput(area_id="WARD_001", timestamp="2026-05-20T14:00:00Z", heat_index_c=0.0, utci_c=0.0, wbgt_c=0.0, htsi=0.0, htsi_category="MODERATE", calculation_status="COMPUTED")
    t_out_2 = ThermalOutput(area_id="WARD_002", timestamp="2026-05-20T14:00:00Z", heat_index_c=0.0, utci_c=0.0, wbgt_c=0.0, htsi=0.0, htsi_category="MODERATE", calculation_status="COMPUTED")
    
    results = PredictionAdapter.predict_batch([t_out_1, t_out_2])
    
    assert len(results) == 2
    assert results[0].area_id == "WARD_001"
    assert results[1].area_id == "WARD_002"
