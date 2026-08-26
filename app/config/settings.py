from pydantic import BaseModel, Field

class Settings(BaseModel):
    # Risk thresholds
    HTSI_MODERATE: float = 27.0
    HTSI_HIGH: float = 32.0
    HTSI_EXTREME: float = 40.0
    
    # Defaults
    DEFAULT_WIND_SPEED: float = 0.0

settings = Settings()
