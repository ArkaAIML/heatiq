from dataclasses import dataclass, asdict, field
from typing import Dict, Any, List

class RecommendationOutputValidationError(ValueError):
    """Raised when structured recommendation output violates the canonical data contract."""
    pass

@dataclass
class ImmediateAction:
    name: str
    allocations: List[str] = field(default_factory=list)
    reason: str = ""

@dataclass
class ResourceAllocation:
    cooling_centres: str = ""
    healthcare_capacity: str = ""
    outreach_personnel: str = ""
    other: str = ""

@dataclass
class RecommendationOutput:
    """
    Canonical Recommendation Output conforming to Data Contract §24.
    """
    area_id: str
    generated_at: str
    situation_summary: str
    severity: str
    immediate_actions: List[ImmediateAction] = field(default_factory=list)
    resource_allocation: ResourceAllocation = field(default_factory=ResourceAllocation)
    population_priorities: List[str] = field(default_factory=list)
    monitoring_instructions: List[str] = field(default_factory=list)
    rationale: str = ""
    escalation_conditions: str = ""
    status: str = "COMPUTED"
    message: str = "Recommendation generated successfully."
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert output to a JSON-serializable dictionary."""
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecommendationOutput":
        if not isinstance(data, dict):
            raise RecommendationOutputValidationError(f"Expected dict, got {type(data).__name__}")
            
        # Parse nested dataclasses safely
        immediate_actions = []
        for action_data in data.get('immediate_actions', []):
            if isinstance(action_data, dict):
                immediate_actions.append(ImmediateAction(
                    name=action_data.get('name', ''),
                    allocations=action_data.get('allocations', []),
                    reason=action_data.get('reason', '')
                ))
        data['immediate_actions'] = immediate_actions
        
        res_data = data.get('resource_allocation', {})
        if isinstance(res_data, dict):
            data['resource_allocation'] = ResourceAllocation(
                cooling_centres=res_data.get('cooling_centres', ''),
                healthcare_capacity=res_data.get('healthcare_capacity', ''),
                outreach_personnel=res_data.get('outreach_personnel', ''),
                other=res_data.get('other', '')
            )
            
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
            "generated_at": None,
            "situation_summary": "Recommendation unavailable",
            "severity": "UNKNOWN",
            "immediate_actions": [],
            "resource_allocation": asdict(ResourceAllocation()),
            "population_priorities": [],
            "monitoring_instructions": [],
            "rationale": "",
            "escalation_conditions": "",
            "status": self.status,
            "message": self.message
        }
