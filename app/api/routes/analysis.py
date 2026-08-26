from fastapi import APIRouter
from app.api.schemas import EnvData, AnalysisResponse
from app.processing.preprocessing import normalize_data
from app.calculations.heat_index import calculate_heat_index
from app.calculations.wbgt import calculate_wbgt_est
from app.thermal.htsi import calculate_htsi
from app.risk.mortality import BaselineRiskModel
from app.spatial.grid import calculate_spatial_risk
from app.population.exposure import calculate_population_exposure
from app.recommendations.engine import generate_recommendations
from app.alerts.generator import generate_alert
from app.api.schemas import ThermalIndices

router = APIRouter()
risk_model = BaselineRiskModel()

@router.post("/analysis", response_model=AnalysisResponse)
def analyze_conditions(data: EnvData):
    processed_data = normalize_data(data)
    
    hi = calculate_heat_index(processed_data.temperature_c, processed_data.relative_humidity)
    wbgt = calculate_wbgt_est(processed_data.temperature_c, processed_data.relative_humidity, processed_data.solar_radiation or 0.0)
    
    indices = ThermalIndices(heat_index=hi, wbgt_est=wbgt)
    
    htsi = calculate_htsi(indices)
    
    health_risk = risk_model.predict_risk(htsi)
    
    spatial = calculate_spatial_risk(processed_data.location_id or "unknown", health_risk)
    
    exposure = calculate_population_exposure(spatial)
    
    recs = generate_recommendations(htsi, health_risk)
    
    alert = generate_alert(htsi)
    
    return AnalysisResponse(
        timestamp=processed_data.timestamp,
        location_id=processed_data.location_id,
        environmental_conditions=processed_data,
        thermal_indices=indices,
        htsi=htsi,
        health_risk=health_risk,
        spatial_risk=spatial,
        recommendations=recs,
        alert=alert
    )
