import pytest
from backend.wardfilter.schemas import WardContext
from backend.thermalengine.schemas import ThermalOutput
from backend.mortality.schemas import MortalityOutput, InfoPoolRecord, ResourcePoolRecord
from backend.prediction.schemas import PredictionOutput
from backend.wardfilter.engine import IntelligentFilteringEngine
from backend.wardfilter.rules import DEFAULT_RULESET

@pytest.fixture
def base_context():
    thermal = ThermalOutput(area_id="WARD_001", timestamp="2026-05-20T14:00:00Z", heat_index_c=30.0, utci_c=30.0, wbgt_c=30.0, htsi=20.0, htsi_category="LOW")
    mortality = MortalityOutput(area_id="WARD_001", timestamp="2026-05-20T14:00:00Z", risk_level="NORMAL")
    info = InfoPoolRecord(area_id="WARD_001", vulnerability_score=20.0)
    resource = ResourcePoolRecord(area_id="WARD_001", resource_capacity_score=80.0)
    prediction = PredictionOutput(area_id="WARD_001", prediction_generated_at="2026-05-20T14:00:00Z", forecast_for="2026-05-20T14:00:00Z", forecast_horizon_days=1, thermal_hazard_score=0.1, predicted_max_utci_c=30.0, thermal_stress_level="NORMAL", model_name="test", model_version="v1")
    return WardContext(
        area_id="WARD_001",
        timestamp="2026-05-20T14:00:00Z",
        thermal=thermal,
        prediction=prediction,
        mortality=mortality,
        info_pool=info,
        resource_pool=resource
    )

def test_normal_conditions(base_context):
    engine = IntelligentFilteringEngine(rules=DEFAULT_RULESET)
    res = engine.evaluate(base_context)
    assert res.severity == "NONE"

def test_low_thermal_stress(base_context):
    base_context.thermal.htsi = 40.0
    engine = IntelligentFilteringEngine(rules=DEFAULT_RULESET)
    res = engine.evaluate(base_context)
    assert res.severity == "LOW"

def test_moderate_thermal_stress(base_context):
    base_context.thermal.htsi = 60.0
    engine = IntelligentFilteringEngine(rules=DEFAULT_RULESET)
    res = engine.evaluate(base_context)
    assert res.severity == "MODERATE"

def test_high_thermal_stress(base_context):
    base_context.thermal.htsi = 72.0
    engine = IntelligentFilteringEngine(rules=DEFAULT_RULESET)
    res = engine.evaluate(base_context)
    assert res.severity == "HIGH"
    assert "HIGH_THERMAL_STRESS" in res.triggered_conditions

def test_critical_thermal_standalone(base_context):
    base_context.thermal.htsi = 86.0
    engine = IntelligentFilteringEngine(rules=DEFAULT_RULESET)
    res = engine.evaluate(base_context)
    assert res.severity == "CRITICAL"

def test_extreme_thermal_standalone(base_context):
    base_context.thermal.htsi = 96.0
    engine = IntelligentFilteringEngine(rules=DEFAULT_RULESET)
    res = engine.evaluate(base_context)
    assert res.severity == "EXTREME"

def test_elevated_mortality_escalation(base_context):
    # HTSI = 40 (LOW), but Mortality = HIGH.
    # PREVIOUSLY this was a HIGH severity due to standalone mortality.
    # NOW we explicitly verify it only falls back to LOW because there is no thermal stress.
    base_context.thermal.htsi = 40.0
    base_context.mortality.risk_level = "HIGH"
    engine = IntelligentFilteringEngine(rules=DEFAULT_RULESET)
    res = engine.evaluate(base_context)
    assert res.severity == "LOW"
    assert "BASELINE_MORTALITY_NO_THERMAL" in res.triggered_conditions
    assert res.condition_message == "Low heat risk. Proceed with normal summer precautions."

def test_high_thermal_high_mortality(base_context):
    # HTSI = 76 (CRITICAL threshold for mortality), Mortality = HIGH -> CRITICAL
    base_context.thermal.htsi = 76.0
    base_context.mortality.risk_level = "HIGH"
    engine = IntelligentFilteringEngine(rules=DEFAULT_RULESET)
    res = engine.evaluate(base_context)
    assert res.severity == "CRITICAL"
    assert "HIGH_THERMAL_AND_ELEVATED_MORTALITY" in res.triggered_conditions

def test_high_thermal_high_vulnerability(base_context):
    # HTSI = 81, Vuln = 85 -> CRITICAL, whereas normally HTSI 81 is only HIGH
    base_context.thermal.htsi = 81.0
    base_context.info_pool.vulnerability_score = 85.0
    engine = IntelligentFilteringEngine(rules=DEFAULT_RULESET)
    res = engine.evaluate(base_context)
    assert res.severity == "CRITICAL"
    assert "HIGH_THERMAL_ELEVATED_VULNERABILITY" in res.triggered_conditions

def test_high_thermal_poor_resources(base_context):
    base_context.thermal.htsi = 81.0
    base_context.resource_pool.resource_capacity_score = 20.0
    engine = IntelligentFilteringEngine(rules=DEFAULT_RULESET)
    res = engine.evaluate(base_context)
    assert res.severity == "CRITICAL"
    assert "HIGH_THERMAL_LIMITED_RESOURCES" in res.triggered_conditions

def test_missing_data_behavior(base_context):
    # If HTSI is missing (None), it should return INSUFFICIENT_DATA status instead of defaulting to 0
    base_context.thermal.htsi = None
    engine = IntelligentFilteringEngine(rules=DEFAULT_RULESET)
    res = engine.evaluate(base_context)
    
    assert res.calculation_status == "INSUFFICIENT_DATA"
    assert res.severity is None
    assert "MISSING_REQUIRED_DATA" in res.triggered_conditions

def test_missing_optional_prediction(base_context):
    # A ward with valid thermal data but missing prediction can still be classified
    base_context.thermal.htsi = 72.0
    base_context.prediction = None
    engine = IntelligentFilteringEngine(rules=DEFAULT_RULESET)
    res = engine.evaluate(base_context)
    
    # Missing prediction should not crash engine, it just evaluates available factors (HIGH)
    assert res.severity == "HIGH"
    assert "HIGH_THERMAL_STRESS" in res.triggered_conditions

def test_prediction_escalation(base_context):
    base_context.thermal.htsi = 65.0
    base_context.prediction.thermal_hazard_score = 0.8
    engine = IntelligentFilteringEngine(rules=DEFAULT_RULESET)
    res = engine.evaluate(base_context)
    assert res.severity == "HIGH"
    assert "ANTICIPATED_HIGH_HEAT_EVENT" in res.triggered_conditions

def test_multi_ward_independence():
    # Test identical thermal, different contexts -> different severity
    from backend.wardfilter.service import filter_wards
    
    t1 = ThermalOutput(area_id="WARD_1", timestamp="T1", heat_index_c=30, utci_c=30, wbgt_c=30, htsi=82.0, htsi_category="HIGH")
    t2 = ThermalOutput(area_id="WARD_2", timestamp="T1", heat_index_c=30, utci_c=30, wbgt_c=30, htsi=82.0, htsi_category="HIGH")
    t3 = ThermalOutput(area_id="WARD_3", timestamp="T1", heat_index_c=30, utci_c=30, wbgt_c=30, htsi=82.0, htsi_category="HIGH")
    
    # WARD_1: Normal vuln/res -> HTSI 82 -> HIGH
    i1 = InfoPoolRecord(area_id="WARD_1", vulnerability_score=20.0)
    r1 = ResourcePoolRecord(area_id="WARD_1", resource_capacity_score=80.0)
    
    # WARD_2: High vuln -> HTSI 82 + Vuln 85 -> CRITICAL
    i2 = InfoPoolRecord(area_id="WARD_2", vulnerability_score=85.0)
    r2 = ResourcePoolRecord(area_id="WARD_2", resource_capacity_score=80.0)
    
    # WARD_3: Poor resources -> HTSI 82 + Res 20 -> CRITICAL
    i3 = InfoPoolRecord(area_id="WARD_3", vulnerability_score=20.0)
    r3 = ResourcePoolRecord(area_id="WARD_3", resource_capacity_score=20.0)
    
    # Common prediction and mortality
    pred = [PredictionOutput(area_id=f"WARD_{i}", prediction_generated_at="T1", forecast_for="T1", forecast_horizon_days=1, thermal_hazard_score=0.1, predicted_max_utci_c=30, thermal_stress_level="NORMAL", model_name="test", model_version="v1") for i in [1, 2, 3]]
    mort = [MortalityOutput(area_id=f"WARD_{i}", timestamp="T1", risk_level="NORMAL") for i in [1, 2, 3]]
    
    results = filter_wards([t1, t2, t3], pred, mort, [i1, i2, i3], [r1, r2, r3])
    
    assert len(results) == 3
    res_map = {r.area_id: r for r in results}
    
    assert res_map["WARD_1"].severity == "HIGH"
    assert res_map["WARD_2"].severity == "CRITICAL"
    assert res_map["WARD_3"].severity == "CRITICAL"
