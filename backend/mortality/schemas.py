"""
HeatIQ Mortality Risk Index — Public Data Contract Schemas and Validation Layer
Data Contract: v0.1  |  Components: Exposure (§10), Vulnerability (§11), Resource (§12), Risk Output (§22)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, Literal, List


class MortalityInputValidationError(ValueError):
    """Raised when structured input violates the canonical data contract."""
    pass


@dataclass
class InfoPoolRecord:
    """
    Canonical Population/Demographic Input Record.
    Combines Exposure Schema (§10) and Vulnerability Schema (§11).
    """
    area_id: str
    
    # Exposure Schema (§10)
    population: Optional[int] = None
    population_density: Optional[float] = None
    outdoor_worker_fraction: Optional[float] = None
    
    # Vulnerability Schema (§11)
    elderly_fraction: Optional[float] = None
    child_fraction: Optional[float] = None
    vulnerability_score: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> InfoPoolRecord:
        if not isinstance(data, dict):
            raise MortalityInputValidationError(f"Expected dict, got {type(data).__name__}")
        valid_keys = set(cls.__dataclass_fields__.keys())
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        try:
            return cls(**filtered)
        except TypeError as exc:
            raise MortalityInputValidationError(f"Failed to instantiate InfoPoolRecord: {exc}")


@dataclass
class ResourcePoolRecord:
    """
    Canonical Adaptive Capacity / Resource Input Record.
    Based on Resource Schema (§12).
    """
    area_id: str
    
    hospital_count: Optional[int] = None
    hospital_capacity: Optional[float] = None
    cooling_centre_count: Optional[int] = None
    distance_to_healthcare_km: Optional[float] = None
    resource_capacity_score: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ResourcePoolRecord:
        if not isinstance(data, dict):
            raise MortalityInputValidationError(f"Expected dict, got {type(data).__name__}")
        valid_keys = set(cls.__dataclass_fields__.keys())
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        try:
            return cls(**filtered)
        except TypeError as exc:
            raise MortalityInputValidationError(f"Failed to instantiate ResourcePoolRecord: {exc}")


@dataclass
class MortalityOutput:
    """
    Canonical Mortality Risk Output conforming to Data Contract (§22).
    Exposes component scores, final risk category, and explainable reason codes.
    """
    # Identification
    area_id: str
    timestamp: str

    # Component Scores (0-100)
    hazard_score: Optional[float] = None
    exposure_score: Optional[float] = None
    vulnerability_score: Optional[float] = None
    adaptive_capacity_score: Optional[float] = None

    # Overall Risk
    risk_score: Optional[float] = None  # Dimensionless prioritization score 0-100
    risk_level: Optional[str] = None    # LOW / MODERATE / HIGH / EXTREME

    # Traceability & Explainability
    calculation_status: Literal["COMPUTED", "INSUFFICIENT_DATA"] = "COMPUTED"
    reason_codes: List[str] = field(default_factory=list)
    method_version: str = "RULE_BASED_MVP"

    def to_dict(self) -> Dict[str, Any]:
        """Convert output to a JSON-serializable dictionary."""
        return asdict(self)

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serialize output to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def to_json_list(cls, outputs: List[MortalityOutput], indent: Optional[int] = None) -> str:
        """Serialize a collection of MortalityOutput instances to a JSON string."""
        return json.dumps([o.to_dict() for o in outputs], indent=indent)
