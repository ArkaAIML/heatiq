from app.api.schemas import RiskResult, SpatialRisk

def calculate_spatial_risk(location_id: str, risk: RiskResult) -> SpatialRisk:
    # MVP: proxy spatial risk based on area characteristics (hardcoded for now)
    pop = 10000 if location_id else None
    
    return SpatialRisk(
        area_id=location_id or "unknown",
        overall_risk=risk.risk_category,
        population_affected=pop
    )
