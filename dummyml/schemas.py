from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class DummyPredictionOutput:
    """
    Temporary dummy schema for Prediction Engine output.
    Does NOT contain real ML predictions.
    """
    area_id: str
    status: str = "DUMMY"
    message: str = "Prediction engine is currently staring at the weather and doing absolutely nothing."

    def to_dict(self) -> Dict[str, Any]:
        return {
            "area_id": self.area_id,
            "status": self.status,
            "message": self.message
        }

@dataclass
class DummyRecommendationOutput:
    """
    Temporary dummy schema for Recommendation Engine output.
    Does NOT contain real recommendations.
    """
    area_id: str
    status: str = "DUMMY"
    message: str = "Recommendation engine unavailable. Please consult the nearest sensible human."

    def to_dict(self) -> Dict[str, Any]:
        return {
            "area_id": self.area_id,
            "status": self.status,
            "message": self.message
        }

@dataclass
class DummyMLResult:
    """
    Composite result containing both dummy prediction and recommendation outputs.
    """
    prediction: DummyPredictionOutput
    recommendation: DummyRecommendationOutput

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prediction": self.prediction.to_dict(),
            "recommendation": self.recommendation.to_dict()
        }
