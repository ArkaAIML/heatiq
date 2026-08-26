from app.api.schemas import SpatialRisk

def calculate_population_exposure(spatial_risk: SpatialRisk) -> str:
    # MVP: proxy for exposure. Just returning a string note
    if spatial_risk.overall_risk in ["Severe", "High"]:
        return "Critical exposure levels expected for outdoor workers and vulnerable groups."
    return "Exposure levels are within normal limits."
