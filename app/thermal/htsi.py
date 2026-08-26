from app.api.schemas import HTSIResult, ThermalIndices
from app.config.settings import settings

def calculate_htsi(indices: ThermalIndices) -> HTSIResult:
    # MVP assumption: simple weighted average of Heat Index and WBGT
    score = (indices.heat_index * 0.4) + (indices.wbgt_est * 0.6)
    
    if score >= settings.HTSI_EXTREME:
        cat = "CRITICAL"
        factors = ["Extreme WBGT", "High Heat Index"]
    elif score >= settings.HTSI_HIGH:
        cat = "DANGER"
        factors = ["Elevated thermal load"]
    elif score >= settings.HTSI_MODERATE:
        cat = "CAUTION"
        factors = ["Moderate heat"]
    else:
        cat = "SAFE"
        factors = []
        
    return HTSIResult(
        score=round(score, 2),
        category=cat,
        contributing_factors=factors
    )
