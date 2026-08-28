import sys
from pathlib import Path
import logging
import pandas as pd
import xarray as xr

# Attach HeatIQ/ml and HeatIQ/ml/pipeline to path
sys.path.append(str(Path(__file__).parent.parent.parent / "ml"))
sys.path.append(str(Path(__file__).parent.parent.parent / "ml" / "pipeline"))

try:
    from ml.preprocessing.features import build_daily_feature_frame
    from ml.inference.artifact import load_model_artifact, D1_MAX_AIR_TEMPERATURE_CONTRACT
    _REAL_ML_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Failed to load REAL ML dependencies: {e}")
    _REAL_ML_AVAILABLE = False

from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from backend.prediction.schemas import PredictionOutput
from backend.prediction.weather_history.schemas import CanonicalHourlyWeather

# Using dummyml for fallback testing.
from dummyml.service import dummy_prediction_and_recommendation
from backend.thermalengine.schemas import ThermalOutput
from backend.prediction.weather_history.parser import WeatherHistoryManager
from backend.prediction.weather_history.storage import WeatherHistoryStore
from backend.prediction.weather_history.api import NasaPowerHistoryAPI

logger = logging.getLogger(__name__)

class PredictionAdapter:
    """
    Adapter boundary insulating HeatIQ from the ML Prediction implementation.
    Acts as the Prediction Gate.
    Translates canonical ML features into the ML Engine, and maps the proprietary
    output into the canonical PredictionOutput schema.
    """
    
    @staticmethod
    def predict(ml_input: Optional[Dict[str, Any]], history_interval_days: int = 10, use_dummy: bool = False) -> Optional[PredictionOutput]:
        """
        Executes the prediction engine for a structured ML input (from the Prediction Filter).
        Allows requesting an arbitrary history interval (default 10 days for rolling features).
        """
        if ml_input is None:
            return None
            
        location = ml_input["location"]
        canonical = ml_input["regular"]
        timestamp = canonical.timestamp
        lat = canonical.latitude
        lon = canonical.longitude
        
        # 1. Fetch required history
        store = WeatherHistoryStore()
        api = NasaPowerHistoryAPI()
        manager = WeatherHistoryManager(store, api)
        
        # Determine the start boundary based on history_interval_days
        end_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        start_dt = end_dt - timedelta(days=history_interval_days)
        start_time = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        try:
            history = manager.get_history(location, lat, lon, start_time, timestamp)
        except Exception as e:
            logger.error(f"Prediction failed to fetch history for {location}: {e}")
            history = []
            
        # 2. Stitch the canonical current observation to the history if it's missing
        current_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        floored_dt = current_dt.replace(minute=0, second=0, microsecond=0)
        floored_timestamp = floored_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        if not history:
            current_obs = CanonicalHourlyWeather(
                location=location,
                timestamp=floored_timestamp,
                latitude=lat,
                longitude=lon,
                temperature_c=canonical.temperature_c,
                dewpoint_c=canonical.dew_point_c,
                relative_humidity_pct=canonical.relative_humidity_pct,
                wind_speed_ms=canonical.wind_speed_ms,
                surface_pressure_pa=canonical.surface_pressure_pa,
                solar_radiation_wm2=canonical.solar_radiation_wm2,
                thermal_radiation_wm2=canonical.thermal_radiation_wm2
            )
            history.append(current_obs)
        else:
            last_dt = datetime.fromisoformat(history[-1].timestamp.replace("Z", "+00:00"))
            if last_dt < floored_dt:
                # ONLY append if there is exactly a 1-hour gap to prevent breaking ML continuous time-series assumption
                if (floored_dt - last_dt) == timedelta(hours=1):
                    current_obs = CanonicalHourlyWeather(
                        location=location,
                        timestamp=floored_timestamp,
                        latitude=lat,
                        longitude=lon,
                        temperature_c=canonical.temperature_c,
                        dewpoint_c=canonical.dew_point_c,
                        relative_humidity_pct=canonical.relative_humidity_pct,
                        wind_speed_ms=canonical.wind_speed_ms,
                        surface_pressure_pa=canonical.surface_pressure_pa,
                        solar_radiation_wm2=canonical.solar_radiation_wm2,
                        thermal_radiation_wm2=canonical.thermal_radiation_wm2
                    )
                    history.append(current_obs)
                else:
                    logger.warning(f"Gap detected between history ({last_dt}) and current observation ({floored_dt}). Skipping current observation append to maintain continuity.")
            
        now_iso = datetime.now(timezone.utc).isoformat()
        
        if use_dummy or not _REAL_ML_AVAILABLE:
            # Invoke Dummy ML fallback
            dummy_thermal = ThermalOutput(
                area_id=location, timestamp=timestamp,
                heat_index_c=0, utci_c=0, wbgt_c=0, htsi=0, htsi_category="DUMMY"
            )
            d_res = dummy_prediction_and_recommendation(dummy_thermal)
            
            return PredictionOutput(
                area_id=location,
                prediction_generated_at=now_iso,
                forecast_for=timestamp,
                forecast_horizon_days=1,
                predicted_max_temperature_c=None, # Dummy does not provide this
                model_name="dummyml",
                model_version="v0.1"
            )
            
        # 3. Construct Real ML input
        try:
            if not history:
                raise ValueError("Insufficient history for ML processing")
                
            from dataclasses import asdict
            df_history = pd.DataFrame([asdict(h) for h in history])
            
            # The ml preprocessing expects timezone-naive UTC valid_time index
            # We use format="mixed" because OpenMeteo current observations (no seconds) 
            # and NASA Power history (with seconds) have different ISO 8601 formatting.
            df_history["valid_time"] = pd.to_datetime(df_history["timestamp"], format="mixed").dt.tz_convert(None)
            df_history = df_history.set_index("valid_time")
            
            # Create xarray dataset as expected by build_daily_feature_frame
            ds = xr.Dataset.from_dataframe(df_history)
            
            # Preprocessing generates EXACTLY the 24 ML features safely
            df_features = build_daily_feature_frame(ds, timezone="UTC")
            
            # Use the most recent complete local day's feature row for the next-day prediction.
            # This handles incomplete current-day data being dropped by the preprocessor.
            df_feature_row = df_features.iloc[[-1]]
            feature_date = df_feature_row["date"].iloc[0]
            df_feature_row = df_feature_row.drop(columns=["date"])
            
            # 4. Load real artifact and Predict
            artifact_path = Path(__file__).parent.parent.parent / "ml" / "artifacts" / "linear_regression-v1" / "linear_regression-v1.pkl"
            artifact = load_model_artifact(artifact_path, expected_contract=D1_MAX_AIR_TEMPERATURE_CONTRACT)
            
            prediction_result = artifact.predict_one(df_feature_row, feature_date=feature_date)
            
            # 5. Output Prediction Schema
            pred = PredictionOutput(
                area_id=location,
                prediction_generated_at=now_iso,
                forecast_for=timestamp,
                forecast_horizon_days=1,
                predicted_max_temperature_c=float(prediction_result.prediction),
                model_name=artifact.metadata.model_name or "Linear Regression",
                model_version=artifact.model_version
            )
            return pred
            
        except Exception as e:
            logger.error(f"Real ML inference failed for {location}: {e}")
            raise
