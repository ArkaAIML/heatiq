from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class EnvData(BaseModel):
    temperature_c: float
    relative_humidity: float = Field(..., ge=0, le=100)
    wind_speed_ms: Optional[float] = None
    solar_radiation: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    location_id: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class ProcessedEnvData(EnvData):
    wind_speed_ms: float  # Normalized

class ThermalIndices(BaseModel):
    heat_index: float
    wbgt_est: float

class HTSIResult(BaseModel):
    score: float
    category: str
    contributing_factors: List[str]

class RiskResult(BaseModel):
    mortality_risk_score: float
    risk_category: str
    model_version: str

class SpatialRisk(BaseModel):
    area_id: str
    overall_risk: str
    population_affected: Optional[int]

class Recommendation(BaseModel):
    action: str
    reason: str
    priority: str

class AlertPayload(BaseModel):
    level: str
    message: str
    action_required: str

class AnalysisResponse(BaseModel):
    timestamp: datetime
    location_id: Optional[str]
    environmental_conditions: ProcessedEnvData
    thermal_indices: ThermalIndices
    htsi: HTSIResult
    health_risk: RiskResult
    spatial_risk: SpatialRisk
    recommendations: List[Recommendation]
    alert: AlertPayload
