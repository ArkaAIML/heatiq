from typing import Dict, Any, List
import logging
import httpx
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class OpenMeteoProvider:
    """
    Real atmospheric data provider using the Open-Meteo API.
    Fetches weather data based on geographic coordinates.
    Since explicit ward coordinates are unavailable, we use a city-level
    observation (Bhubaneswar: 20.296, 85.824) and distribute it across
    all requested area_ids to prevent redundant requests.
    """
    
    BASE_URL = "https://api.open-meteo.com/v1/forecast"
    
    # Bhubaneswar fallback coordinates
    DEFAULT_LAT = 20.296
    DEFAULT_LON = 85.824

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def fetch_current_conditions(self, area_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Fetches the current weather for the city and maps it to the given wards.
        """
        if not area_ids:
            return []
            
        params = {
            "latitude": self.DEFAULT_LAT,
            "longitude": self.DEFAULT_LON,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,shortwave_radiation",
            "timezone": "UTC"
        }
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(self.BASE_URL, params=params)
                
            if response.status_code == 429:
                raise Exception("Rate limit exceeded for Open-Meteo API")
                
            response.raise_for_status()
            data = response.json()
            
            if "current" not in data:
                raise Exception("Malformed response: 'current' block missing")
                
            current = data["current"]
            
            obs_time = current.get("time", datetime.now(timezone.utc).isoformat())
            # Ensure proper ISO timezone suffix if it's UTC
            if not obs_time.endswith("Z") and "+" not in obs_time:
                obs_time += "Z"
            
            temp = current.get("temperature_2m")
            rh = current.get("relative_humidity_2m")
            wind = current.get("wind_speed_10m")
            solar = current.get("shortwave_radiation")
            
            # Numeric validation
            if temp is not None and not isinstance(temp, (int, float)):
                raise Exception("Non-numeric temperature received")
            if rh is not None and not isinstance(rh, (int, float)):
                raise Exception("Non-numeric humidity received")
            
            results = []
            for area_id in area_ids:
                results.append({
                    "source_area_id": area_id,
                    "source_timestamp": obs_time,
                    "source_temperature": temp,
                    "source_humidity": rh,
                    "source_wind": wind,
                    "source_solar": solar
                })
                
            return results
            
        except httpx.RequestError as e:
            raise Exception(f"Network failure while reaching Open-Meteo: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to fetch data from Open-Meteo: {str(e)}")
