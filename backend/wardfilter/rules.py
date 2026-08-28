"""
HeatIQ Ward Filter — Deterministic Intelligent Filtering Engine Rules

This module defines the PROTOTYPE POLICY thresholds and rules for severity classification.
These rules integrate Thermal Hazard, Mortality Risk, Population Vulnerability, and Adaptive Capacity.
No authoritative scientific thresholds were provided, so these are explicitly marked as prototype benchmarks.
"""

from backend.wardfilter.engine import Rule
from backend.wardfilter.schemas import WardContext, MissingDataError

def _has_prediction(context: WardContext) -> bool:
    """Safely check if meaningful prediction exists."""
    return context.prediction is not None and context.prediction.thermal_hazard_score is not None

def _get_htsi(context: WardContext) -> float:
    val = context.thermal.htsi
    if val is None:
        raise MissingDataError("HTSI is missing")
    return val

def _get_mortality_risk(context: WardContext) -> str:
    val = context.mortality.risk_level
    if val is None:
        raise MissingDataError("Mortality risk_level is missing")
    return val

def _get_vuln_score(context: WardContext) -> float:
    val = context.info_pool.vulnerability_score
    if val is None:
        raise MissingDataError("Vulnerability score is missing")
    return val

def _get_resource_score(context: WardContext) -> float:
    val = context.resource_pool.resource_capacity_score
    if val is None:
        raise MissingDataError("Resource capacity score is missing")
    return val


# =====================================================================
# EXTREME RULES (Highest severity)
# =====================================================================
rule_extreme_thermal_mortality = Rule(
    id="EXTREME_THERMAL_MORTALITY",
    condition=lambda c: _get_htsi(c) >= 85.0 and _get_mortality_risk(c) == "EXTREME",
    severity="EXTREME",
    reason_code="EXTREME_THERMAL_AND_MORTALITY_RISK",
    condition_message="Extreme heat risk compounded by extreme baseline mortality risk. Please stay indoors and avoid unnecessary outdoor exposure.",
    recommended_action="Initiate emergency medical response and mandatory cooling center activation.",
    priority=100
)

rule_extreme_thermal_vulnerable = Rule(
    id="EXTREME_THERMAL_VULNERABLE",
    condition=lambda c: _get_htsi(c) >= 90.0 and _get_vuln_score(c) >= 80.0,
    severity="EXTREME",
    reason_code="CRITICAL_THERMAL_HIGH_VULNERABILITY",
    condition_message="Extreme heat risk affecting highly vulnerable populations. Immediate intervention required.",
    recommended_action="Deploy targeted emergency outreach to highly vulnerable populations immediately.",
    priority=90
)

rule_extreme_thermal_standalone = Rule(
    id="EXTREME_THERMAL_STANDALONE",
    condition=lambda c: _get_htsi(c) >= 95.0,
    severity="EXTREME",
    reason_code="EXTREME_THERMAL_STRESS",
    condition_message="Extreme heat risk. Universal dangerous conditions. Stay indoors.",
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
    condition_message="Critical heat risk for areas with elevated historical mortality. Avoid unnecessary outdoor exposure.",
    recommended_action="Avoid unnecessary outdoor exposure and activate community warning systems.",
    priority=100
)

rule_critical_thermal_vulnerable = Rule(
    id="CRITICAL_THERMAL_VULNERABLE",
    condition=lambda c: _get_htsi(c) >= 80.0 and _get_vuln_score(c) >= 70.0,
    severity="CRITICAL",
    reason_code="HIGH_THERMAL_ELEVATED_VULNERABILITY",
    condition_message="Critical heat risk for vulnerable demographics. Target warnings and welfare checks.",
    recommended_action="Targeted warnings for vulnerable demographics (elderly/children).",
    priority=90
)

rule_critical_thermal_poor_resources = Rule(
    id="CRITICAL_THERMAL_POOR_RESOURCES",
    condition=lambda c: _get_htsi(c) >= 80.0 and _get_resource_score(c) <= 30.0,
    severity="CRITICAL",
    reason_code="HIGH_THERMAL_LIMITED_RESOURCES",
    condition_message="Critical heat risk compounded by severe lack of community resources.",
    recommended_action="Coordinate emergency resource distribution to under-resourced areas.",
    priority=85
)

rule_critical_thermal_standalone = Rule(
    id="CRITICAL_THERMAL_STANDALONE",
    condition=lambda c: _get_htsi(c) >= 85.0,
    severity="CRITICAL",
    reason_code="SEVERE_THERMAL_STRESS",
    condition_message="Critical heat risk. Avoid all strenuous outdoor activity.",
    recommended_action="Avoid all strenuous outdoor activity.",
    priority=80
)

rule_critical_prediction = Rule(
    id="CRITICAL_PREDICTION_ESCALATION",
    condition=lambda c: _has_prediction(c) and c.prediction.thermal_hazard_score >= 0.9 and _get_htsi(c) >= 75.0,
    severity="CRITICAL",
    reason_code="ANTICIPATED_SEVERE_HEAT_EVENT",
    condition_message="Anticipated critical heat event based on escalating forecast.",
    recommended_action="Pre-position emergency resources based on high-confidence severe forecast.",
    priority=70
)


# =====================================================================
# HIGH RULES
# =====================================================================
rule_high_thermal_vulnerable = Rule(
    id="HIGH_THERMAL_VULNERABLE",
    condition=lambda c: _get_htsi(c) >= 60.0 and _get_vuln_score(c) >= 60.0,
    severity="HIGH",
    reason_code="ELEVATED_THERMAL_VULNERABLE_POPULATION",
    condition_message="High heat risk for vulnerable populations. Prioritize community outreach.",
    recommended_action="Prioritize community outreach for vulnerable groups.",
    priority=110
)

rule_high_thermal_standalone = Rule(
    id="HIGH_THERMAL_STANDALONE",
    condition=lambda c: _get_htsi(c) >= 70.0,
    severity="HIGH",
    reason_code="HIGH_THERMAL_STRESS",
    condition_message="High heat risk. Reduce prolonged outdoor exposure.",
    recommended_action="Reduce prolonged outdoor exposure.",
    priority=100
)

# Demoted standalone mortality rule: Now requires at least some thermal stress to be "HIGH" overall.
rule_high_mortality_with_thermal = Rule(
    id="HIGH_MORTALITY_WITH_THERMAL",
    condition=lambda c: _get_mortality_risk(c) == "HIGH" and _get_htsi(c) >= 50.0,
    severity="HIGH",
    reason_code="ELEVATED_MORTALITY_AND_THERMAL",
    condition_message="High risk due to combination of historical mortality and current moderate heat.",
    recommended_action="Monitor population health closely.",
    priority=90
)

rule_high_prediction = Rule(
    id="HIGH_PREDICTION_ESCALATION",
    condition=lambda c: _has_prediction(c) and c.prediction.thermal_hazard_score >= 0.75 and _get_htsi(c) >= 60.0,
    severity="HIGH",
    reason_code="ANTICIPATED_HIGH_HEAT_EVENT",
    condition_message="Anticipated high heat event. Issue early advisories.",
    recommended_action="Issue early heat advisories.",
    priority=80
)


# =====================================================================
# MODERATE RULES
# =====================================================================
rule_moderate_thermal_poor_resources = Rule(
    id="MODERATE_THERMAL_POOR_RESOURCES",
    condition=lambda c: _get_htsi(c) >= 40.0 and _get_resource_score(c) <= 40.0,
    severity="MODERATE",
    reason_code="MODERATE_THERMAL_LIMITED_RESOURCES",
    condition_message="Moderate heat risk, but limited resources require careful monitoring.",
    recommended_action="Ensure cooling resources are accessible.",
    priority=110
)

rule_moderate_thermal_standalone = Rule(
    id="MODERATE_THERMAL_STANDALONE",
    condition=lambda c: _get_htsi(c) >= 50.0,
    severity="MODERATE",
    reason_code="MODERATE_THERMAL_STRESS",
    condition_message="Moderate heat risk. Stay hydrated and continue routine monitoring.",
    recommended_action="Stay hydrated and wear light clothing.",
    priority=100
)

# Replaced generic standalone mortality rule with a combination rule
rule_moderate_mortality_with_thermal = Rule(
    id="MODERATE_MORTALITY_WITH_THERMAL",
    condition=lambda c: _get_mortality_risk(c) == "MODERATE" and _get_htsi(c) >= 30.0,
    severity="MODERATE",
    reason_code="MODERATE_BASELINE_AND_THERMAL",
    condition_message="Moderate risk based on baseline mortality combined with current low-level heat.",
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
    condition_message="Low heat risk. Proceed with normal summer precautions.",
    recommended_action="Normal summer precautions.",
    priority=100
)

# Generic fallback for moderate mortality without thermal stress
rule_low_mortality_fallback = Rule(
    id="LOW_MORTALITY_FALLBACK",
    condition=lambda c: _get_mortality_risk(c) in ["MODERATE", "HIGH"],
    severity="LOW",
    reason_code="BASELINE_MORTALITY_NO_THERMAL",
    condition_message="Low thermal risk, but routine vigilance advised due to baseline demographic factors.",
    recommended_action="No acute action required; maintain routine vigilance.",
    priority=50
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
    rule_high_thermal_vulnerable,
    rule_high_thermal_standalone,
    rule_high_mortality_with_thermal,
    rule_high_prediction,
    
    # MODERATE
    rule_moderate_thermal_poor_resources,
    rule_moderate_thermal_standalone,
    rule_moderate_mortality_with_thermal,
    
    # LOW
    rule_low_thermal_standalone,
    rule_low_mortality_fallback
]
