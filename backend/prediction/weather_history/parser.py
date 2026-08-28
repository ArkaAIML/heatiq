import logging
from typing import List
from datetime import datetime, timedelta, timezone

from backend.prediction.weather_history.schemas import CanonicalHourlyWeather
from backend.prediction.weather_history.storage import WeatherHistoryStore
from backend.prediction.weather_history.api import NasaPowerHistoryAPI

logger = logging.getLogger(__name__)

class WeatherHistoryManager:
    """
    Manages historical weather data for the Prediction Module.
    Responsible for checking storage, finding gaps, fetching missing data,
    and returning complete contiguous hourly records.
    """
    
    RETENTION_DAYS = 60
    
    def __init__(self, store: WeatherHistoryStore, api: NasaPowerHistoryAPI):
        self.store = store
        self.api = api

    def get_history(
        self, 
        location: str, 
        latitude: float, 
        longitude: float, 
        start_time: str, 
        end_time: str
    ) -> List[CanonicalHourlyWeather]:
        """
        Retrieves contiguous hourly weather history.
        start_time and end_time must be strict ISO-8601 strings, e.g. '2026-08-01T00:00:00Z'.
        """
        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        
        # 1. Identify what timestamps we *should* have
        expected_timestamps = []
        curr = start_dt
        while curr <= end_dt:
            expected_timestamps.append(curr.strftime("%Y-%m-%dT%H:%M:%SZ"))
            curr += timedelta(hours=1)
            
        # 2. Check existing coverage
        existing = set(self.store.get_coverage(location, start_time, end_time))
        missing = [t for t in expected_timestamps if t not in existing]
        
        import os
        prototype_mode = os.environ.get("HEATIQ_PROTOTYPE_MODE", "false").lower() == "true"
        
        # 3. Fetch missing intervals
        if missing and not prototype_mode:
            self._fetch_missing(location, latitude, longitude, missing)
            
        # 4. Truncate old history (rolling retention)
        if not prototype_mode:
            retention_cutoff = (datetime.now(timezone.utc) - timedelta(days=self.RETENTION_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
            self.store.trim_old_records(location, retention_cutoff)
            
        # 5. Fetch final set from DB and verify completeness
        records = self.store.get_records(location, start_time, end_time)
        if len(records) != len(expected_timestamps) and not prototype_mode:
            logger.warning(f"Gap detected for {location}. Expected {len(expected_timestamps)} rows, got {len(records)}.")
            
        return records

    def _fetch_missing(self, location: str, latitude: float, longitude: float, missing_timestamps: List[str]):
        """
        Identifies contiguous missing blocks and queries the API for each block.
        """
        # Simple grouping into continuous blocks (or just min/max to simplify API calls)
        missing_dts = [datetime.fromisoformat(t.replace("Z", "+00:00")) for t in missing_timestamps]
        min_dt = min(missing_dts)
        max_dt = max(missing_dts)
        
        start_date_str = min_dt.strftime("%Y-%m-%d")
        end_date_str = max_dt.strftime("%Y-%m-%d")
        
        logger.info(f"Fetching missing weather history for {location} from {start_date_str} to {end_date_str}")
        
        new_records = self.api.fetch_history(
            location=location,
            latitude=latitude,
            longitude=longitude,
            start_date=start_date_str,
            end_date=end_date_str
        )
        
        # Validate and insert
        if new_records:
            self.store.insert_records(new_records)
