import httpx
import logging
from typing import List, Optional
from datetime import datetime, timezone
import math

from backend.prediction.weather_history.schemas import CanonicalHourlyWeather

logger = logging.getLogger(__name__)

class NasaPowerHistoryAPI:
    """
    Handles fetching historical hourly data from NASA POWER.
    Maps provider variables directly into CanonicalHourlyWeather.
    """
    
    BASE_URL = "https://power.larc.nasa.gov/api/temporal/hourly/point"
    
    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    def fetch_history(self, location: str, latitude: float, longitude: float, start_date: str, end_date: str) -> List[CanonicalHourlyWeather]:
        """
        Fetches hourly weather data for the specified date range.
        start_date and end_date should be formatted as YYYY-MM-DD in UTC.
        """
        # NASA POWER uses YYYYMMDD
        start_str = start_date.replace("-", "")
        end_str = end_date.replace("-", "")
        
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start": start_str,
            "end": end_str,
            "parameters": "T2M,T2MDEW,RH2M,WS10M,PS,ALLSKY_SFC_SW_DWN,ALLSKY_SFC_LW_DWN",
            "community": "RE",
            "format": "JSON"
        }
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(self.BASE_URL, params=params)
                
            response.raise_for_status()
            data = response.json()
            
            if "properties" not in data or "parameter" not in data["properties"]:
                raise Exception("Malformed response: missing 'properties.parameter' block")
                
            return self._parse_response(location, latitude, longitude, data)
            
        except httpx.RequestError as e:
            raise Exception(f"Network failure while reaching NASA POWER: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to fetch data from NASA POWER: {str(e)}")

    def _safe_float(self, value: any) -> Optional[float]:
        if value is None:
            return None
        try:
            val = float(value)
            if math.isnan(val) or math.isinf(val) or val == -999.0:
                # -999.0 is the NASA POWER default fill value for missing data
                return None
            return val
        except (ValueError, TypeError):
            return None

    def _parse_response(self, location: str, latitude: float, longitude: float, data: dict) -> List[CanonicalHourlyWeather]:
        parameters = data["properties"]["parameter"]
        
        # All parameters share the same YYYYMMDDHH keys
        # We assume the keys are properly aligned across all parameters
        t2m = parameters.get("T2M", {})
        d2m = parameters.get("T2MDEW", {})
        rh = parameters.get("RH2M", {})
        wind = parameters.get("WS10M", {})
        sp = parameters.get("PS", {})
        swr = parameters.get("ALLSKY_SFC_SW_DWN", {})
        lwr = parameters.get("ALLSKY_SFC_LW_DWN", {})
        
        records = []
        for time_key in sorted(t2m.keys()):
            # Parse NASA POWER time YYYYMMDDHH
            dt = datetime.strptime(time_key, "%Y%m%d%H").replace(tzinfo=timezone.utc)
            # Format as strict ISO-8601 string for storage
            iso_time = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            
            t_c = self._safe_float(t2m.get(time_key))
            d_c = self._safe_float(d2m.get(time_key))
            r_pct = self._safe_float(rh.get(time_key))
            w_ms = self._safe_float(wind.get(time_key))
            s_kpa = self._safe_float(sp.get(time_key))
            
            sr_wm2 = self._safe_float(swr.get(time_key))
            lr_wm2 = self._safe_float(lwr.get(time_key))
            
            # Missing core variables from provider? We skip and let the parser detect the gap.
            if any(v is None for v in [t_c, d_c, r_pct, w_ms, s_kpa, sr_wm2, lr_wm2]):
                continue
                
            records.append(CanonicalHourlyWeather(
                location=location,
                timestamp=iso_time,
                latitude=latitude,
                longitude=longitude,
                temperature_c=t_c,
                dewpoint_c=d_c,
                relative_humidity_pct=r_pct,
                wind_speed_ms=w_ms,
                surface_pressure_pa=s_kpa * 1000.0, # kPa to Pa
                solar_radiation_wm2=sr_wm2,
                thermal_radiation_wm2=lr_wm2
            ))
            
        return records
