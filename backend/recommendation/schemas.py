from dataclasses import dataclass, asdict
from typing import Dict, Any, List

class RecommendationOutputValidationError(ValueError):
    """Raised when structured recommendation output violates the canonical data contract."""
    pass

@dataclass
class RecommendationOutput:
    """
    Canonical Recommendation Output conforming to Data Contract §24.
    """
    area_id: str
    forecast_for: str
    priority: str
    actions: List[str]
    reason_codes: List[str]
    status: str = "COMPUTED"
    message: str = "Recommendation generated successfully."
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert output to a JSON-serializable dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecommendationOutput":
        if not isinstance(data, dict):
            raise RecommendationOutputValidationError(f"Expected dict, got {type(data).__name__}")
        valid_keys = set(cls.__dataclass_fields__.keys())
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        try:
            return cls(**filtered)
        except TypeError as exc:
            raise RecommendationOutputValidationError(f"Failed to instantiate RecommendationOutput: {exc}")

@dataclass
class FailedRecommendationOutput:
    """
    Canonical Failed Recommendation Output.
    """
    area_id: str
    status: str
    message: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert output to a JSON-serializable dictionary."""
        return {
            "area_id": self.area_id,
            "forecast_for": None,
            "priority": "UNKNOWN",
            "actions": [],
            "reason_codes": [],
            "status": self.status,
            "message": self.message
        }
