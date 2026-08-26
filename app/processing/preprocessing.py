from app.api.schemas import EnvData, ProcessedEnvData
from app.config.settings import settings

def normalize_data(data: EnvData) -> ProcessedEnvData:
    """
    Validates and normalizes environmental data.
    """
    wind = data.wind_speed_ms if data.wind_speed_ms is not None else settings.DEFAULT_WIND_SPEED
    
    return ProcessedEnvData(
        temperature_c=data.temperature_c,
        relative_humidity=data.relative_humidity,
        wind_speed_ms=wind,
        solar_radiation=data.solar_radiation,
        timestamp=data.timestamp,
        location_id=data.location_id,
        latitude=data.latitude,
        longitude=data.longitude
    )
