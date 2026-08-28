from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class CanonicalAcquiredData:
    """
    The COMPLETE Canonical Data Superset acquired by the Global Data Acquisition layer.
    Contains directly acquired raw weather values.
    No engine-specific filtering happens here.
    """
    
    # Metadata
    location: str
    timestamp: str  # ISO-8601 string representing current observation time
    provider: str
    timezone: str = "UTC"

    # Core Required Atmospheric Data (Directly Acquired)
    temperature_c: Optional[float] = None # Current Temperature
    relative_humidity_pct: Optional[float] = None # Current Humidity
    wind_speed_ms: Optional[float] = None # Current Wind Speed
    solar_radiation_wm2: Optional[float] = None # Current Solar Radiation
    thermal_radiation_wm2: Optional[float] = None # Current Thermal Radiation
    surface_pressure_pa: Optional[float] = None # Current Surface Pressure
    dew_point_c: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        from dataclasses import asdict
        return asdict(self)
