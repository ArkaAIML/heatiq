from app.api.schemas import HTSIResult, RiskResult, Recommendation

def generate_recommendations(htsi: HTSIResult, risk: RiskResult) -> list[Recommendation]:
    recs = []
    if risk.risk_category == "Severe":
        recs.append(Recommendation(
            action="Open Cooling Centers",
            reason="Severe mortality risk in population.",
            priority="HIGH"
        ))
    if htsi.category in ["DANGER", "CRITICAL"]:
        recs.append(Recommendation(
            action="Issue Public Warning",
            reason="HTSI is critical.",
            priority="HIGH"
        ))
    return recs
