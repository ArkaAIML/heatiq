"""
HeatIQ Ward Filter — Public Data Contract Schemas and Validation Layer
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List, Literal

from backend.thermalengine import ThermalOutput
from backend.mortality import MortalityOutput, InfoPoolRecord, ResourcePoolRecord
from backend.prediction.schemas import PredictionOutput

class WardFilterInputValidationError(ValueError):
    """Raised when structured input violates the canonical data contract."""
    pass

@dataclass
class WardContext:
    """
    Combined structured representation of a single ward.
    Produced by the InfoSmasher.
    """
    area_id: str
    timestamp: str
    thermal: ThermalOutput
    mortality: MortalityOutput
    info_pool: InfoPoolRecord
    resource_pool: ResourcePoolRecord
    prediction: Optional[PredictionOutput] = None

    def validate(self):
        if not self.area_id:
            raise WardFilterInputValidationError("Missing area_id in WardContext")
        if not self.timestamp:
            raise WardFilterInputValidationError("Missing timestamp in WardContext")
        if not isinstance(self.thermal, ThermalOutput):
            raise WardFilterInputValidationError("Invalid thermal record")
        if self.prediction is not None and not isinstance(self.prediction, PredictionOutput):
            raise WardFilterInputValidationError("Invalid prediction record")
        if not isinstance(self.mortality, MortalityOutput):
            raise WardFilterInputValidationError("Invalid mortality record")
        if not isinstance(self.info_pool, InfoPoolRecord):
            raise WardFilterInputValidationError("Invalid info pool record")
        if not isinstance(self.resource_pool, ResourcePoolRecord):
            raise WardFilterInputValidationError("Invalid resource pool record")

@dataclass
class WardFilterResult:
    """
    Structured output from the Intelligent Filtering Engine.
    Follows data_contract.md Recommendation Output Contract principles.
    """
    area_id: str
    timestamp: str
    
    severity: Optional[str] = None
    message: Optional[str] = None
    recommended_actions: List[str] = field(default_factory=list)
    triggered_conditions: List[str] = field(default_factory=list)
    
    # Preserves the full technical context for dashboard use
    context: Optional[WardContext] = None
    
    calculation_status: Literal["COMPUTED", "INSUFFICIENT_DATA"] = "COMPUTED"
    method_version: str = "WARD_FILTER_MVP"

    def to_dict(self) -> Dict[str, Any]:
        """Convert output to a JSON-serializable dictionary."""
        d = asdict(self)
        # Convert nested objects to dicts
        if self.context:
            d["context"] = {
                "area_id": self.context.area_id,
                "timestamp": self.context.timestamp,
                "thermal": self.context.thermal.to_dict(),
                "prediction": self.context.prediction.to_dict() if self.context.prediction else None,
                "mortality": self.context.mortality.to_dict(),
                "info_pool": asdict(self.context.info_pool),
                "resource_pool": asdict(self.context.resource_pool)
            }
        return d
