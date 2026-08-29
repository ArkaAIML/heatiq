import logging
import math
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import os

from backend.data_acquisition.schemas import CanonicalAcquiredData
from backend.data_acquisition.open_meteo_provider import OpenMeteoProvider
from datalake.core.cache_manager import get_canonical_info_pool
# Note: In the future, a mock provider can be implemented and toggled via env vars.

logger = logging.getLogger(__name__)

class GlobalDataAcquisitionAdapter:
    """
    Global Data Acquisition Layer.
    Fetches raw atmospheric data from providers and produces a single CanonicalAcquiredData payload.
    """
    def __init__(self, provider=None):
        if provider is not None:
            self.provider = provider
        else:
            self.provider = OpenMeteoProvider()

    def _safe_float(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            val = float(value)
            if math.isnan(val) or math.isinf(val):
                return None
            return val
        except (ValueError, TypeError):
            return None

    def acquire_for_location(self, location: str) -> CanonicalAcquiredData:
        try:
            # 1. PROTOTYPE MODE CHECK
            # In prototype mode, we anchor the system to the newest seeded historical record
            # to avoid faking timestamps while still satisfying the 10-day history requirement
            # without triggering massive API fetches.
            if os.environ.get("HEATIQ_PROTOTYPE_MODE", "false").lower() == "true":
                from backend.prediction.weather_history.storage import WeatherHistoryStore
                store = WeatherHistoryStore()
                records = store.get_records(location, "2000-01-01T00:00:00Z", "2099-01-01T00:00:00Z")
                if records:
                    latest = records[-1]
                    logger.info(f"PROTOTYPE MODE: Anchoring system time to seeded history at {latest.timestamp}")
                    return CanonicalAcquiredData(
                        location=location,
                        timestamp=latest.timestamp,
                        provider="seeded_prototype",
                        timezone="UTC",
                        temperature_c=latest.temperature_c,
                        relative_humidity_pct=latest.relative_humidity_pct,
                        wind_speed_ms=latest.wind_speed_ms,
                        solar_radiation_wm2=latest.solar_radiation_wm2,
                        thermal_radiation_wm2=latest.thermal_radiation_wm2,
                        surface_pressure_pa=latest.surface_pressure_pa,
                        dew_point_c=latest.dewpoint_c,
                        latitude=latest.latitude,
                        longitude=latest.longitude,
                    )
                else:
                    logger.warning("PROTOTYPE MODE is enabled but no seeded history found. Falling back to live API.")
            
            # 2. LIVE ACQUISITION
            raw_data = self.provider.fetch_current_and_history()
            current = raw_data.get("current", {})
            
            obs_time = current.get("time", datetime.now(timezone.utc).isoformat())
            if not obs_time.endswith("Z") and "+" not in obs_time:
                obs_time += "Z"
                
            temp = self._safe_float(current.get("temperature_2m"))
            rh = self._safe_float(current.get("relative_humidity_2m"))
            wind = self._safe_float(current.get("wind_speed_10m"))
            solar = self._safe_float(current.get("shortwave_radiation"))
            pressure = self._safe_float(current.get("surface_pressure"))
            dew_point = self._safe_float(current.get("dew_point_2m"))
            
            # Open-Meteo now supports terrestrial_radiation for longwave!
            thermal = self._safe_float(current.get("terrestrial_radiation"))
            
            # Validation rules: reject NaNs/missing core variables
            if any(v is None for v in [temp, rh, wind, solar, pressure, dew_point, thermal]):
                raise ValueError("Missing or invalid core weather variables from provider")
            
            data = CanonicalAcquiredData(
                location=location,
                timestamp=obs_time,
                provider="open-meteo",
                timezone="UTC",
                temperature_c=temp,
                relative_humidity_pct=rh,
                wind_speed_ms=wind,
                solar_radiation_wm2=solar,
                thermal_radiation_wm2=thermal,
                surface_pressure_pa=pressure,
                dew_point_c=dew_point,
                latitude=self.provider.DEFAULT_LAT,
                longitude=self.provider.DEFAULT_LON,
            )
            return data
            
        except Exception as e:
            logger.error(f"stage=GlobalDataAcquisition location={location} reason=PROVIDER_FAILURE details='{str(e)}'")
            now = datetime.now(timezone.utc).isoformat()
            return CanonicalAcquiredData(
                location=location,
                timestamp=now,
                provider="failed"
            )
