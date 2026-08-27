"""
HeatIQ Ward Filter — Intelligent Filtering Engine
"""
from typing import List, Callable, Optional, Dict
from dataclasses import dataclass
from .schemas import WardContext, WardFilterResult

# Severity priority (higher number = higher severity)
SEVERITY_PRIORITY = {
    "NONE": 0,
    "LOW": 1,
    "MODERATE": 2,
    "HIGH": 3,
    "SEVERE": 4,
    "CRITICAL": 5,
    "EXTREME": 6
}

@dataclass
class Rule:
    """
    Represents a deterministic intervention criteria rule.
    """
    id: str
    condition: Callable[[WardContext], bool]
    severity: str
    reason_code: str
    recommended_action: str
    priority: int = 0
    is_demo_rule: bool = False

    def __post_init__(self):
        if self.severity not in SEVERITY_PRIORITY:
            raise ValueError(f"Unknown severity level: {self.severity}")

class IntelligentFilteringEngine:
    """
    Evaluates the complete Ward Context against deterministic rules.
    Selects the highest applicable severity according to a deterministic priority system.
    """
    
    def __init__(self, rules: Optional[List[Rule]] = None):
        """
        Initializes the engine with a set of deterministic rules.
        """
        self.rules = rules or []

    def evaluate(self, context: WardContext) -> WardFilterResult:
        """
        Evaluates the context against all registered rules.
        Triggers all matching rules and selects the highest priority severity.
        """
        # REQUIRED DATA CHECK
        if not context.thermal or context.thermal.htsi is None:
            return WardFilterResult(
                area_id=context.area_id,
                timestamp=context.timestamp,
                severity=None,
                message="Missing required thermal data (HTSI).",
                recommended_actions=[],
                triggered_conditions=["MISSING_REQUIRED_DATA"],
                context=context,
                calculation_status="INSUFFICIENT_DATA"
            )

        triggered_rules = []
        for rule in self.rules:
            try:
                if rule.condition(context):
                    triggered_rules.append(rule)
            except Exception as e:
                # If a rule errors, we skip it but log internally in a real system.
                # For this MVP, we let it propagate or safely ignore based on architecture.
                pass

        if not triggered_rules:
            return WardFilterResult(
                area_id=context.area_id,
                timestamp=context.timestamp,
                severity="NONE",
                message="No significant risk conditions met.",
                recommended_actions=[],
                triggered_conditions=[],
                context=context
            )

        # Sort triggered rules deterministically:
        # 1. Highest severity
        # 2. Highest rule-specific priority (if severities match)
        # 3. Alphabetical by Rule ID (to ensure stable order)
        triggered_rules.sort(
            key=lambda r: (
                SEVERITY_PRIORITY.get(r.severity, 0),
                r.priority,
                r.id
            ),
            reverse=True
        )

        highest_severity_rule = triggered_rules[0]
        
        triggered_conditions = [r.reason_code for r in triggered_rules]
        recommended_actions = list(dict.fromkeys(r.recommended_action for r in triggered_rules)) # preserve order, remove duplicates
        
        is_demo = any(r.is_demo_rule for r in triggered_rules)
        demo_msg = "[MVP / DEMONSTRATION RULE - NOT SCIENTIFICALLY CALIBRATED] " if is_demo else ""

        message = f"{demo_msg}Highest risk condition: {highest_severity_rule.reason_code}."

        return WardFilterResult(
            area_id=context.area_id,
            timestamp=context.timestamp,
            severity=highest_severity_rule.severity,
            message=message,
            recommended_actions=recommended_actions,
            triggered_conditions=triggered_conditions,
            context=context,
            calculation_status="COMPUTED"
        )
