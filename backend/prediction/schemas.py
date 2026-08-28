"""
HeatIQ Prediction Engine — Public Data Contract Schemas and Validation Layer
Data Contract: v0.1  |  Component: ML Prediction Engine (§20)
"""

import json
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

class PredictionOutputValidationError(ValueError):
    """Raised when structured prediction output violates the canonical data contract."""
    pass

@dataclass
class PredictionOutput:
    """
    Canonical ML Prediction Output conforming to Data Contract §20.
    """
    area_id: str
    prediction_generated_at: str
    forecast_for: str
    forecast_horizon_days: int
    model_name: str
    model_version: str
    thermal_hazard_score: Optional[float] = None
    predicted_max_temperature_c: Optional[float] = None
    predicted_max_utci_c: Optional[float] = None
    thermal_stress_level: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert output to a JSON-serializable dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PredictionOutput":
        if not isinstance(data, dict):
            raise PredictionOutputValidationError(f"Expected dict, got {type(data).__name__}")
        valid_keys = set(cls.__dataclass_fields__.keys())
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        try:
            return cls(**filtered)
        except TypeError as exc:
            raise PredictionOutputValidationError(f"Failed to instantiate PredictionOutput: {exc}")
