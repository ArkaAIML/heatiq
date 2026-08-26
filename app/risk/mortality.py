from app.api.schemas import HTSIResult, RiskResult

class RiskModelInterface:
    def predict_risk(self, htsi: HTSIResult) -> RiskResult:
        raise NotImplementedError

class BaselineRiskModel(RiskModelInterface):
    def predict_risk(self, htsi: HTSIResult) -> RiskResult:
        # Baseline deterministic proxy for mortality risk score
        risk_score = min(100.0, max(0.0, (htsi.score - 20) * 3))
        
        cat = "Low"
        if risk_score > 70:
            cat = "Severe"
        elif risk_score > 40:
            cat = "Moderate"
            
        return RiskResult(
            mortality_risk_score=round(risk_score, 1),
            risk_category=cat,
            model_version="baseline-v1"
        )
