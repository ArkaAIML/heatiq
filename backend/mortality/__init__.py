"""
HeatIQ Mortality Risk Index Module

Produces a transparent, explainable risk classification (LOW, MODERATE, HIGH, EXTREME)
based on thermal conditions, population characteristics, and available emergency resources.

Designed to accept a future ML mortality model by substituting the internal calculator
while preserving the public interface.
"""

from .schemas import (
    InfoPoolRecord,
    ResourcePoolRecord,
    MortalityOutput,
    MortalityInputValidationError
)
from .calculator import (
    BaseMortalityRiskCalculator,
    RuleBasedMortalityRiskCalculator
)
from .service import (
    MortalityService,
    calculate_mortality_risk,
    calculate_mortality_risk_batch
)

__all__ = [
    # ── Public APIs ──
    "calculate_mortality_risk",
    "calculate_mortality_risk_batch",
    "MortalityService",
    
    # ── Schemas ──
    "InfoPoolRecord",
    "ResourcePoolRecord",
    "MortalityOutput",
    "MortalityInputValidationError",
    
    # ── Internal Calculators (For Extension) ──
    "BaseMortalityRiskCalculator",
    "RuleBasedMortalityRiskCalculator"
]
