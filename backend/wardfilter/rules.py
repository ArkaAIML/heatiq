"""
HeatIQ Ward Filter — Deterministic Intelligent Filtering Engine Rules

This module defines the PROTOTYPE POLICY thresholds and rules for severity classification.
These rules integrate Thermal Hazard, Mortality Risk, Population Vulnerability, and Adaptive Capacity.
No authoritative scientific thresholds were provided, so these are explicitly marked as prototype benchmarks.
"""

from backend.wardfilter.engine import Rule
from backend.wardfilter.schemas import WardContext

def _has_prediction(context: WardContext) -> bool:
    """Safely check if meaningful prediction exists."""
    return context.prediction is not None and context.prediction.thermal_hazard_score is not None

def _get_htsi(context: WardContext) -> float:
    return context.thermal.htsi

def _get_mortality_risk(context: WardContext) -> str:
    return context.mortality.risk_level

def _get_vuln_score(context: WardContext) -> float:
    return context.info_pool.vulnerability_score

def _get_resource_score(context: WardContext) -> float:
    return context.resource_pool.resource_capacity_score


# =====================================================================
# EXTREME RULES (Highest severity)
# =====================================================================
rule_extreme_thermal_mortality = Rule(
    id="EXTREME_THERMAL_MORTALITY",
    condition=lambda c: _get_htsi(c) >= 85.0 and _get_mortality_risk(c) == "EXTREME",
    severity="EXTREME",
    reason_code="EXTREME_THERMAL_AND_MORTALITY_RISK",
    recommended_action="Initiate emergency medical response and mandatory cooling center activation.",
    priority=100
)

rule_extreme_thermal_vulnerable = Rule(
    id="EXTREME_THERMAL_VULNERABLE",
    condition=lambda c: _get_htsi(c) >= 90.0 and _get_vuln_score(c) >= 80.0,
    severity="EXTREME",
    reason_code="CRITICAL_THERMAL_HIGH_VULNERABILITY",
    recommended_action="Deploy targeted emergency outreach to highly vulnerable populations immediately.",
    priority=90
)

rule_extreme_thermal_standalone = Rule(
    id="EXTREME_THERMAL_STANDALONE",
    condition=lambda c: _get_htsi(c) >= 95.0,
    severity="EXTREME",
    reason_code="EXTREME_THERMAL_STRESS",
    recommended_action="Declare widespread heat emergency.",
    priority=80
)


# =====================================================================
# CRITICAL RULES
# =====================================================================
rule_critical_thermal_mortality = Rule(
    id="CRITICAL_THERMAL_MORTALITY",
    condition=lambda c: _get_htsi(c) >= 75.0 and _get_mortality_risk(c) in ["HIGH", "EXTREME"],
    severity="CRITICAL",
    reason_code="HIGH_THERMAL_AND_ELEVATED_MORTALITY",
    recommended_action="Avoid unnecessary outdoor exposure and activate community warning systems.",
    priority=100
)

rule_critical_thermal_vulnerable = Rule(
    id="CRITICAL_THERMAL_VULNERABLE",
    condition=lambda c: _get_htsi(c) >= 80.0 and _get_vuln_score(c) >= 70.0,
    severity="CRITICAL",
    reason_code="HIGH_THERMAL_ELEVATED_VULNERABILITY",
    recommended_action="Targeted warnings for vulnerable demographics (elderly/children).",
    priority=90
)

rule_critical_thermal_poor_resources = Rule(
    id="CRITICAL_THERMAL_POOR_RESOURCES",
    condition=lambda c: _get_htsi(c) >= 80.0 and _get_resource_score(c) <= 30.0,
    severity="CRITICAL",
    reason_code="HIGH_THERMAL_LIMITED_RESOURCES",
    recommended_action="Coordinate emergency resource distribution to under-resourced areas.",
    priority=85
)

rule_critical_thermal_standalone = Rule(
    id="CRITICAL_THERMAL_STANDALONE",
    condition=lambda c: _get_htsi(c) >= 85.0,
    severity="CRITICAL",
    reason_code="SEVERE_THERMAL_STRESS",
    recommended_action="Avoid all strenuous outdoor activity.",
    priority=80
)

rule_critical_prediction = Rule(
    id="CRITICAL_PREDICTION_ESCALATION",
    condition=lambda c: _has_prediction(c) and c.prediction.thermal_hazard_score >= 0.9 and _get_htsi(c) >= 75.0,
    severity="CRITICAL",
    reason_code="ANTICIPATED_SEVERE_HEAT_EVENT",
    recommended_action="Pre-position emergency resources based on high-confidence severe forecast.",
    priority=70
)


# =====================================================================
# HIGH RULES
# =====================================================================
rule_high_thermal_standalone = Rule(
    id="HIGH_THERMAL_STANDALONE",
    condition=lambda c: _get_htsi(c) >= 70.0,
    severity="HIGH",
    reason_code="HIGH_THERMAL_STRESS",
    recommended_action="Reduce prolonged outdoor exposure.",
    priority=100
)

rule_high_mortality_standalone = Rule(
    id="HIGH_MORTALITY_STANDALONE",
    condition=lambda c: _get_mortality_risk(c) == "HIGH",
    severity="HIGH",
    reason_code="ELEVATED_BASELINE_MORTALITY_RISK",
    recommended_action="Monitor population health closely.",
    priority=90
)

rule_high_prediction = Rule(
    id="HIGH_PREDICTION_ESCALATION",
    condition=lambda c: _has_prediction(c) and c.prediction.thermal_hazard_score >= 0.75 and _get_htsi(c) >= 60.0,
    severity="HIGH",
    reason_code="ANTICIPATED_HIGH_HEAT_EVENT",
    recommended_action="Issue early heat advisories.",
    priority=80
)


# =====================================================================
# MODERATE RULES
# =====================================================================
rule_moderate_thermal_standalone = Rule(
    id="MODERATE_THERMAL_STANDALONE",
    condition=lambda c: _get_htsi(c) >= 50.0,
    severity="MODERATE",
    reason_code="MODERATE_THERMAL_STRESS",
    recommended_action="Stay hydrated and wear light clothing.",
    priority=100
)

rule_moderate_mortality_standalone = Rule(
    id="MODERATE_MORTALITY_STANDALONE",
    condition=lambda c: _get_mortality_risk(c) == "MODERATE",
    severity="MODERATE",
    reason_code="MODERATE_BASELINE_MORTALITY_RISK",
    recommended_action="Routine health monitoring.",
    priority=90
)


# =====================================================================
# LOW RULES
# =====================================================================
rule_low_thermal_standalone = Rule(
    id="LOW_THERMAL_STANDALONE",
    condition=lambda c: _get_htsi(c) >= 30.0,
    severity="LOW",
    reason_code="LOW_THERMAL_STRESS",
    recommended_action="Normal summer precautions.",
    priority=100
)

# =====================================================================
# DEFAULT RULESET EXPORT
# =====================================================================
DEFAULT_RULESET = [
    # EXTREME
    rule_extreme_thermal_mortality,
    rule_extreme_thermal_vulnerable,
    rule_extreme_thermal_standalone,
    
    # CRITICAL
    rule_critical_thermal_mortality,
    rule_critical_thermal_vulnerable,
    rule_critical_thermal_poor_resources,
    rule_critical_thermal_standalone,
    rule_critical_prediction,
    
    # HIGH
    rule_high_thermal_standalone,
    rule_high_mortality_standalone,
    rule_high_prediction,
    
    # MODERATE
    rule_moderate_thermal_standalone,
    rule_moderate_mortality_standalone,
    
    # LOW
    rule_low_thermal_standalone
]
