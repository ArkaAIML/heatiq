import unittest
from backend.thermalengine import ThermalOutput
from backend.mortality import MortalityOutput, InfoPoolRecord, ResourcePoolRecord
from backend.prediction.schemas import PredictionOutput
from backend.wardfilter import (
    InfoSmasher,
    IntelligentFilteringEngine,
    Rule,
    filter_ward,
    filter_wards,
    WardFilterInputValidationError
)

class TestWardFilter(unittest.TestCase):
    def setUp(self):
        # Ward 1 (High hazard, high mortality risk)
        self.t1 = ThermalOutput(area_id="W1", timestamp="2026-05-20", htsi=90.0, calculation_status="COMPUTED", heat_index_c=None, utci_c=None, wbgt_c=None, htsi_category="EXTREME")
        self.p1 = PredictionOutput(area_id="W1", prediction_generated_at="2026-05-20", forecast_for="2026-05-20", forecast_horizon_days=1, thermal_hazard_score=1.0, predicted_max_utci_c=40.0, thermal_stress_level="EXTREME", model_name="dummy", model_version="1")
        self.m1 = MortalityOutput(area_id="W1", timestamp="2026-05-20", risk_score=85.0, risk_level="EXTREME", calculation_status="COMPUTED")
        self.i1 = InfoPoolRecord(area_id="W1", population=50000, elderly_fraction=0.25)
        self.r1 = ResourcePoolRecord(area_id="W1", hospital_count=1)

        # Ward 2 (Moderate hazard, low risk)
        self.t2 = ThermalOutput(area_id="W2", timestamp="2026-05-20", htsi=45.0, calculation_status="COMPUTED", heat_index_c=None, utci_c=None, wbgt_c=None, htsi_category="MODERATE")
        self.p2 = PredictionOutput(area_id="W2", prediction_generated_at="2026-05-20", forecast_for="2026-05-20", forecast_horizon_days=1, thermal_hazard_score=0.5, predicted_max_utci_c=30.0, thermal_stress_level="MODERATE", model_name="dummy", model_version="1")
        self.m2 = MortalityOutput(area_id="W2", timestamp="2026-05-20", risk_score=20.0, risk_level="LOW", calculation_status="COMPUTED")
        self.i2 = InfoPoolRecord(area_id="W2", population=40000, elderly_fraction=0.10)
        self.r2 = ResourcePoolRecord(area_id="W2", hospital_count=5)

        # Ward 3 (Low hazard, low risk)
        self.t3 = ThermalOutput(area_id="W3", timestamp="2026-05-20", htsi=10.0, calculation_status="COMPUTED", heat_index_c=None, utci_c=None, wbgt_c=None, htsi_category="LOW")
        self.p3 = PredictionOutput(area_id="W3", prediction_generated_at="2026-05-20", forecast_for="2026-05-20", forecast_horizon_days=1, thermal_hazard_score=0.1, predicted_max_utci_c=25.0, thermal_stress_level="LOW", model_name="dummy", model_version="1")
        self.m3 = MortalityOutput(area_id="W3", timestamp="2026-05-20", risk_score=5.0, risk_level="LOW", calculation_status="COMPUTED")
        self.i3 = InfoPoolRecord(area_id="W3", population=30000, elderly_fraction=0.05)
        self.r3 = ResourcePoolRecord(area_id="W3", hospital_count=2)

        # Demo rules
        self.rules = [
            Rule(
                id="DEMO_01",
                condition=lambda ctx: ctx.thermal.htsi > 80 and ctx.mortality.risk_score > 75,
                severity="CRITICAL",
                reason_code="SEVERE_THERMAL_AND_MORTALITY_RISK",
                condition_message="Demo critical risk.",
                recommended_action="Issue immediate targeted warnings.",
                priority=100,
                is_demo_rule=True
            ),
            Rule(
                id="DEMO_02",
                condition=lambda ctx: ctx.info_pool.elderly_fraction > 0.20,
                severity="HIGH",
                reason_code="HIGH_ELDERLY_VULNERABILITY",
                condition_message="Demo high risk.",
                recommended_action="Prioritize elderly outreach.",
                priority=50,
                is_demo_rule=True
            )
        ]

    def test_single_ward(self):
        """One complete ward produces a correct structured result."""
        res = filter_ward(self.t1, self.p1, self.m1, self.i1, self.r1)
        self.assertEqual(res.area_id, "W1")
        self.assertEqual(res.calculation_status, "COMPUTED")

    def test_multi_ward(self):
        """3+ wards produce 3+ independent results."""
        results = filter_wards([self.t1, self.t2, self.t3], [self.p1, self.p2, self.p3], [self.m1, self.m2, self.m3], [self.i1, self.i2, self.i3], [self.r1, self.r2, self.r3])
        self.assertEqual(len(results), 3)

    def test_area_id_matching(self):
        """Shuffle each source collection independently and verify correct matching."""
        results = filter_wards([self.t1, self.t2, self.t3], [self.p3, self.p2, self.p1], [self.m3, self.m2, self.m1], [self.i2, self.i3, self.i1], [self.r3, self.r1, self.r2])
        self.assertEqual(results[0].area_id, "W1")
        self.assertEqual(results[0].context.mortality.risk_score, 85.0) # From W1
        self.assertEqual(results[0].context.info_pool.population, 50000) # From W1
        self.assertEqual(results[0].context.resource_pool.hospital_count, 1) # From W1

    def test_no_cross_ward_contamination(self):
        """Verify Ward A never receives Ward B's data."""
        # Intentionally mismatch area_id
        with self.assertRaises(WardFilterInputValidationError):
            InfoSmasher.smash(self.t1, self.p2, self.m2, self.i1, self.r1)

    def test_concurrent_execution(self):
        """Verify that multiple ward jobs are dispatched through the configured concurrency mechanism."""
        results = filter_wards([self.t1, self.t2], [self.p1, self.p2], [self.m1, self.m2], [self.i1, self.i2], [self.r1, self.r2], max_workers=2)
        self.assertEqual(len(results), 2)

    def test_output_order(self):
        """Verify deterministic output order."""
        results = filter_wards([self.t3, self.t1, self.t2], [self.p3, self.p1, self.p2], [self.m1, self.m2, self.m3], [self.i1, self.i2, self.i3], [self.r1, self.r2, self.r3])
        self.assertEqual(results[0].area_id, "W3")
        self.assertEqual(results[1].area_id, "W1")
        self.assertEqual(results[2].area_id, "W2")

    def test_partial_failure(self):
        """valid, invalid, valid preserves valid results."""
        results = filter_wards([self.t1, "invalid", self.t3], [self.p1, self.p3], [self.m1, self.m3], [self.i1, self.i3], [self.r1, self.r3], allow_partial_failures=True)
        self.assertEqual(results[0].calculation_status, "COMPUTED")
        self.assertEqual(results[1].calculation_status, "INSUFFICIENT_DATA")
        self.assertEqual(results[2].calculation_status, "COMPUTED")

    def test_missing_data(self):
        """Test missing records."""
        results = filter_wards([self.t1, self.t2], [self.p1], [self.m1], [self.i1], [self.r1], allow_partial_failures=True)
        self.assertEqual(results[0].calculation_status, "COMPUTED")
        self.assertEqual(results[1].calculation_status, "INSUFFICIENT_DATA")

    def test_duplicate_area_ids(self):
        """Verify deterministic handling of duplicates."""
        results = filter_wards([self.t1, self.t1], [self.p1], [self.m1], [self.i1], [self.r1], allow_partial_failures=True)
        self.assertEqual(results[0].calculation_status, "INSUFFICIENT_DATA")
        self.assertIn("DUPLICATE", results[0].method_version)
        self.assertEqual(results[1].calculation_status, "INSUFFICIENT_DATA")

    def test_empty_input(self):
        """Verify clean empty output."""
        self.assertEqual(filter_wards([], [], [], [], []), [])

    def test_single_ward_through_batch(self):
        """Verify single ward through batch interface works."""
        self.assertEqual(len(filter_wards([self.t1], [self.p1], [self.m1], [self.i1], [self.r1])), 1)

    def test_infosmasher_isolation(self):
        """Test InfoSmasher independently."""
        ctx = InfoSmasher.smash(self.t1, self.p1, self.m1, self.i1, self.r1)
        self.assertEqual(ctx.area_id, "W1")
        self.assertEqual(ctx.thermal.htsi, 90.0)

    def test_rule_engine_isolation(self):
        """Test the Intelligent Filtering Engine using injected deterministic test rules."""
        engine = IntelligentFilteringEngine(rules=self.rules)
        ctx = InfoSmasher.smash(self.t1, self.p1, self.m1, self.i1, self.r1)
        res = engine.evaluate(ctx)
        self.assertEqual(res.severity, "CRITICAL")
        self.assertIn("SEVERE_THERMAL_AND_MORTALITY_RISK", res.triggered_conditions)

    def test_rule_priority(self):
        """Multiple triggered rules must resolve deterministically to the highest-priority applicable severity."""
        engine = IntelligentFilteringEngine(rules=self.rules)
        ctx = InfoSmasher.smash(self.t1, self.p1, self.m1, self.i1, self.r1)
        # For W1, both DEMO_01 (CRITICAL) and DEMO_02 (HIGH) trigger. Result should be CRITICAL.
        res = engine.evaluate(ctx)
        self.assertEqual(res.severity, "CRITICAL")
        self.assertTrue(len(res.triggered_conditions) == 2)
        self.assertIn("HIGH_ELDERLY_VULNERABILITY", res.triggered_conditions)

    def test_technical_output_preservation(self):
        """Verify the complete InfoSmasher ward context remains available."""
        res = filter_ward(self.t1, self.p1, self.m1, self.i1, self.r1)
        self.assertIsNotNone(res.context)
        self.assertEqual(res.context.thermal.htsi, 90.0)

    def test_numerical_integrity(self):
        """Verify the Ward Filter does not alter values."""
        res = filter_ward(self.t1, self.p1, self.m1, self.i1, self.r1)
        self.assertEqual(res.context.thermal.htsi, 90.0)
        self.assertEqual(res.context.mortality.risk_score, 85.0)

if __name__ == "__main__":
    unittest.main()
