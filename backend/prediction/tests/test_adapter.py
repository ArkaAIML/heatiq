import pytest
from unittest.mock import patch, MagicMock
from backend.prediction.adapter import PredictionAdapter
from backend.prediction.schemas import PredictionOutput
from backend.data_acquisition.schemas import CanonicalAcquiredData
from datetime import datetime, timezone

def test_prediction_adapter_predict():
    # 1. Provide regular atmospheric data
    canonical = CanonicalAcquiredData(
        location="Bhubaneswar",
        timestamp="2026-05-20T14:00:00Z",
        latitude=20.296,
        longitude=85.824,
        temperature_c=35.0,
        dew_point_c=25.0,
        relative_humidity_pct=60.0,
        wind_speed_ms=5.0,
        surface_pressure_pa=101325.0,
        solar_radiation_wm2=800.0,
        thermal_radiation_wm2=300.0,
        provider="mock"
    )
    
    ml_input = {
        "location": "Bhubaneswar",
        "regular": canonical
    }
    
    # 2. Execute adapter
    # We mock the history manager to return empty so it doesn't try to use real DB
    with patch('backend.prediction.adapter.WeatherHistoryManager.get_history') as mock_get_history:
        mock_get_history.return_value = []
        
        pred = PredictionAdapter.predict(ml_input, history_interval_days=14, use_dummy=True)
        
        # Check that get_history was called with 14 days prior
        mock_get_history.assert_called_once()
        args, kwargs = mock_get_history.call_args
        assert args[0] == "Bhubaneswar"
        assert args[1] == 20.296
        assert args[2] == 85.824
        assert args[3] == "2026-05-06T14:00:00Z" # 14 days before 2026-05-20
        assert args[4] == "2026-05-20T14:00:00Z"

    # 3. Verify output
    assert isinstance(pred, PredictionOutput)
    assert pred.area_id == "Bhubaneswar"
    assert pred.forecast_for == "2026-05-20T14:00:00Z"
    assert pred.thermal_hazard_score is None
    assert pred.model_name == "dummyml"

def test_prediction_adapter_none_input():
    pred = PredictionAdapter.predict(None)
    assert pred is None
