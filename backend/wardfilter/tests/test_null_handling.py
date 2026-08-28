import pytest
from backend.wardfilter.schemas import WardContext, MissingDataError
from backend.thermalengine.schemas import ThermalOutput
from backend.mortality.schemas import MortalityOutput, InfoPoolRecord, ResourcePoolRecord
from backend.prediction.schemas import PredictionOutput
from backend.wardfilter.engine import IntelligentFilteringEngine
from backend.wardfilter.rules import DEFAULT_RULESET

def _create_mock_context(
    htsi: float = 85.0,
    mortality_risk: str = "EXTREME",
    vuln_score: float = 85.0,
    resource_score: float = 20.0,
    prediction_score: float = 0.95
) -> WardContext:
    thermal = ThermalOutput("WARD_1", "2026", heat_index_c=0.0, utci_c=0.0, wbgt_c=0.0, htsi=htsi, htsi_category="HIGH", calculation_status="COMPUTED")
    mortality = MortalityOutput("WARD_1", "2026", risk_level=mortality_risk)
    info = InfoPoolRecord("WARD_1", vulnerability_score=vuln_score)
    resource = ResourcePoolRecord("WARD_1", resource_capacity_score=resource_score)
    prediction = PredictionOutput(
        area_id="WARD_1", 
        prediction_generated_at="2026", 
        forecast_for="2026", 
        forecast_horizon_days=1, 
        model_name="model", 
        model_version="v1", 
        thermal_hazard_score=prediction_score, 
        predicted_max_temperature_c=0.0, 
        predicted_max_utci_c=0.0, 
        thermal_stress_level="HIGH"
    ) if prediction_score is not None else None
    
    return WardContext("WARD_1", "2026", thermal, mortality, info, resource, prediction)

def test_all_fields_available():
    ctx = _create_mock_context()
    engine = IntelligentFilteringEngine(DEFAULT_RULESET)
    res = engine.evaluate(ctx)
    # With HTSI 85, Mortality EXTREME -> EXTREME_THERMAL_MORTALITY should trigger (Priority 100)
    assert res.severity == "EXTREME"
    assert "EXTREME_THERMAL_AND_MORTALITY_RISK" in res.triggered_conditions

def test_resource_missing_still_evaluates_thermal_mortality():
    ctx = _create_mock_context(resource_score=None) # resource is missing
    engine = IntelligentFilteringEngine(DEFAULT_RULESET)
    res = engine.evaluate(ctx)
    # Should still evaluate and get EXTREME from thermal+mortality
    assert res.severity == "EXTREME"
    assert "EXTREME_THERMAL_AND_MORTALITY_RISK" in res.triggered_conditions
    assert "HIGH_THERMAL_LIMITED_RESOURCES" not in res.triggered_conditions # Skipped cleanly

def test_mortality_missing_still_evaluates_vulnerable():
    ctx = _create_mock_context(htsi=90.0, mortality_risk=None) # missing mortality
    engine = IntelligentFilteringEngine(DEFAULT_RULESET)
    res = engine.evaluate(ctx)
    # With HTSI 90, Vuln 85, it triggers EXTREME_THERMAL_VULNERABLE (Priority 90)
    assert res.severity == "EXTREME"
    assert "CRITICAL_THERMAL_HIGH_VULNERABILITY" in res.triggered_conditions

def test_vulnerability_missing_still_evaluates_standalone():
    # Only thermal available, HTSI = 95 -> EXTREME_THERMAL_STANDALONE
    ctx = _create_mock_context(htsi=95.0, vuln_score=None, mortality_risk=None, resource_score=None)
    engine = IntelligentFilteringEngine(DEFAULT_RULESET)
    res = engine.evaluate(ctx)
    assert res.severity == "EXTREME"
    assert "EXTREME_THERMAL_STRESS" in res.triggered_conditions

def test_prediction_missing():
    # Only HTSI 85, prediction None. Should fallback to CRITICAL_THERMAL_STANDALONE
    ctx = _create_mock_context(htsi=85.0, prediction_score=None, mortality_risk=None, vuln_score=None, resource_score=None)
    engine = IntelligentFilteringEngine(DEFAULT_RULESET)
    res = engine.evaluate(ctx)
    assert res.severity == "CRITICAL"
    assert "SEVERE_THERMAL_STRESS" in res.triggered_conditions

def test_multiple_missing_fields_evaluates_remaining():
    # HTSI 70 -> HIGH_THERMAL_STANDALONE
    ctx = _create_mock_context(htsi=70.0, mortality_risk=None, vuln_score=None, resource_score=None, prediction_score=None)
    engine = IntelligentFilteringEngine(DEFAULT_RULESET)
    res = engine.evaluate(ctx)
    assert res.severity == "HIGH"
    assert "HIGH_THERMAL_STRESS" in res.triggered_conditions

def test_all_meaningful_inputs_unavailable():
    # HTSI = None -> Early exit INSUFFICIENT_DATA
    ctx = _create_mock_context(htsi=None)
    engine = IntelligentFilteringEngine(DEFAULT_RULESET)
    res = engine.evaluate(ctx)
    assert res.severity is None
    assert res.calculation_status == "INSUFFICIENT_DATA"

def test_condition_message_corresponds():
    ctx = _create_mock_context(htsi=95.0, vuln_score=None, mortality_risk=None, resource_score=None)
    engine = IntelligentFilteringEngine(DEFAULT_RULESET)
    res = engine.evaluate(ctx)
    assert res.condition_message == "Extreme heat risk. Universal dangerous conditions. Stay indoors."

def test_missing_resource_does_not_cause_generic_fallback():
    # HTSI = 85.0, Resource = None. Should trigger CRITICAL_THERMAL_STANDALONE, not LOW_MORTALITY_FALLBACK.
    ctx = _create_mock_context(htsi=85.0, mortality_risk="HIGH", resource_score=None)
    engine = IntelligentFilteringEngine(DEFAULT_RULESET)
    res = engine.evaluate(ctx)
    assert res.severity == "CRITICAL"
    assert "SEVERE_THERMAL_STRESS" in res.triggered_conditions
