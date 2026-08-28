import httpx
import logging
import math
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class OpenMeteoProvider:
    """
    Real atmospheric data provider using the Open-Meteo API.
    Fetches current weather and historical daily weather for a city
    to derive temporal features (lags, rolling means).
    """
    
    BASE_URL = "https://api.open-meteo.com/v1/forecast"
    
    # Bhubaneswar fallback coordinates
    DEFAULT_LAT = 20.296
    DEFAULT_LON = 85.824

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

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

    def fetch_current_and_history(self) -> Dict[str, Any]:
        """
        Fetches current conditions and historical data (past 5 days) for calculating temporal features.
        """
        params = {
            "latitude": self.DEFAULT_LAT,
            "longitude": self.DEFAULT_LON,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,shortwave_radiation,surface_pressure,dew_point_2m,terrestrial_radiation",
            "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean,relative_humidity_2m_mean",
            "past_days": 5,
            "timezone": "UTC"
        }
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(self.BASE_URL, params=params)
                
            if response.status_code == 429:
                raise Exception("Rate limit exceeded for Open-Meteo API")
                
            response.raise_for_status()
            data = response.json()
            
            if "current" not in data or "daily" not in data:
                raise Exception("Malformed response: missing 'current' or 'daily' block")
                
            return data
            
        except httpx.RequestError as e:
            raise Exception(f"Network failure while reaching Open-Meteo: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to fetch data from Open-Meteo: {str(e)}")
