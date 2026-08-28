from dataclasses import dataclass
from typing import Optional

@dataclass
class CanonicalHourlyWeather:
    """
    Raw Canonical Hourly Weather data.
    These fields match the exact ML preprocessing requirements, before any 
    feature engineering (like temporal shifts or daily aggregation) occurs.
    """
    location: str
    timestamp: str  # ISO-8601 timezone-naive UTC
    latitude: float
    longitude: float
    
    temperature_c: float
    dewpoint_c: float
    relative_humidity_pct: float
    wind_speed_ms: float
    surface_pressure_pa: float
    solar_radiation_wm2: float
    
    # Thermal radiation is currently handled gracefully if absent in standard API
    thermal_radiation_wm2: Optional[float] = None
