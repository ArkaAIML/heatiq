import pytest
from datetime import datetime, timezone
import json
import logging
from backend.prediction.adapter import PredictionAdapter
from backend.prediction.schemas import PredictionOutput
from backend.data_acquisition.schemas import CanonicalAcquiredData
from backend.prediction.weather_history.parser import WeatherHistoryManager
from backend.prediction.weather_history.storage import WeatherHistoryStore
from backend.prediction.weather_history.api import NasaPowerHistoryAPI
from backend.prediction.weather_history.schemas import CanonicalHourlyWeather

logger = logging.getLogger(__name__)

@pytest.mark.integration
def test_real_inference_e2e():
    """
    End-to-end test verifying:
    RAW WEATHER → PREPROCESSOR → REAL MODEL → OUTPUT
    """
    
    # 1. Provide a real supported location with current observation
    timestamp = "2024-05-20T14:00:00Z" # using a date in the past for history availability
    
    canonical = CanonicalAcquiredData(
        location="Bhubaneswar",
        timestamp=timestamp,
        latitude=20.296,
        longitude=85.824,
        temperature_c=35.0,
        dew_point_c=25.0,
        relative_humidity_pct=60.0,
        wind_speed_ms=5.0,
        surface_pressure_pa=101325.0,
        solar_radiation_wm2=800.0,
        thermal_radiation_wm2=380.0, # required by canonical input
        provider="mock"
    )
    
    ml_input = {
        "location": "Bhubaneswar",
        "regular": canonical
    }
    
    # We mock the history manager to return enough history (10 days * 24 hours + 1 = 241)
    from unittest.mock import patch
    from datetime import timedelta
    with patch('backend.prediction.adapter.WeatherHistoryManager.get_history') as mock_get_history:
        mock_history = []
        start_dt = datetime.fromisoformat("2024-05-10T14:00:00+00:00")
        for i in range(241): # exactly 10 days up to the current hour
            dt = start_dt + timedelta(hours=i)
            mock_history.append(
                CanonicalHourlyWeather(
                    location="Bhubaneswar",
                    timestamp=dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    latitude=20.296,
                    longitude=85.824,
                    temperature_c=35.0,
                    dewpoint_c=25.0,
                    relative_humidity_pct=60.0,
                    wind_speed_ms=5.0,
                    surface_pressure_pa=101325.0,
                    solar_radiation_wm2=800.0,
                    thermal_radiation_wm2=380.0
                )
            )
        mock_get_history.return_value = mock_history
        
        try:
            # Require 10 days for rolling features and boundary drops
            pred = PredictionAdapter.predict(ml_input, history_interval_days=10, use_dummy=False)
        except Exception as e:
            pytest.fail(f"Real ML inference failed: {e}")
        
    assert isinstance(pred, PredictionOutput)
    
    # Verify contract
    assert pred.area_id == "Bhubaneswar"
    assert pred.predicted_max_temperature_c is not None
    assert isinstance(pred.predicted_max_temperature_c, float)
    assert pred.model_name == "linear_regression"
    assert pred.forecast_horizon_days == 1
    
    logger.info(f"Successfully generated real prediction: {pred.predicted_max_temperature_c} C")
