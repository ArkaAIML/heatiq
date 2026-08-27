"""
Tests for Mortality Multi-Ward Gateway.
"""
import unittest
from backend.thermalengine import ThermalOutput
from backend.mortality import (
    InfoPoolRecord,
    ResourcePoolRecord,
    calculate_mortality_risk_batch,
    calculate_mortality_risk
)

class TestMortalityGateway(unittest.TestCase):
    def setUp(self):
        self.t1 = ThermalOutput(area_id="W1", timestamp="2026-05-20", htsi=80.0, calculation_status="COMPUTED", heat_index_c=None, utci_c=None, wbgt_c=None, htsi_category="HIGH")
        self.t2 = ThermalOutput(area_id="W2", timestamp="2026-05-20", htsi=40.0, calculation_status="COMPUTED", heat_index_c=None, utci_c=None, wbgt_c=None, htsi_category="MODERATE")
        self.t3 = ThermalOutput(area_id="W3", timestamp="2026-05-20", htsi=10.0, calculation_status="COMPUTED", heat_index_c=None, utci_c=None, wbgt_c=None, htsi_category="LOW")
        
        self.i1 = InfoPoolRecord(area_id="W1", population=50000, population_density=20000, outdoor_worker_fraction=0.5, elderly_fraction=0.20, child_fraction=0.20)
        self.i2 = InfoPoolRecord(area_id="W2", population=40000, population_density=10000, outdoor_worker_fraction=0.2, elderly_fraction=0.10, child_fraction=0.10)
        self.i3 = InfoPoolRecord(area_id="W3", population=30000, population_density=5000, outdoor_worker_fraction=0.1, elderly_fraction=0.05, child_fraction=0.05)
        
        self.r1 = ResourcePoolRecord(area_id="W1", hospital_count=1, cooling_centre_count=2)
        self.r2 = ResourcePoolRecord(area_id="W2", hospital_count=2, cooling_centre_count=4)
        self.r3 = ResourcePoolRecord(area_id="W3", hospital_count=3, cooling_centre_count=6)

    def test_basic_multi_ward(self):
        """3+ wards produce 3+ corresponding outputs."""
        results = calculate_mortality_risk_batch([self.t1, self.t2, self.t3], [self.i1, self.i2, self.i3], [self.r1, self.r2, self.r3])
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].area_id, "W1")
        self.assertEqual(results[1].area_id, "W2")
        self.assertEqual(results[2].area_id, "W3")
        for res in results:
            self.assertEqual(res.calculation_status, "COMPUTED")

    def test_area_id_matching(self):
        """Shuffle Info Pool and Resource Pool, verify matching."""
        results = calculate_mortality_risk_batch([self.t1, self.t2, self.t3], [self.i3, self.i2, self.i1], [self.r2, self.r3, self.r1])
        single_w1 = calculate_mortality_risk(self.t1, self.i1, self.r1)
        self.assertEqual(results[0].risk_score, single_w1.risk_score)
        
    def test_concurrent_execution(self):
        """Verify execution uses ThreadPoolExecutor (max_workers check)."""
        # We can pass max_workers explicitly and check if it runs without errors.
        results = calculate_mortality_risk_batch([self.t1, self.t2], [self.i1, self.i2], max_workers=2)
        self.assertEqual(len(results), 2)

    def test_order_preservation(self):
        """Verify output order remains deterministic."""
        results = calculate_mortality_risk_batch([self.t3, self.t1, self.t2], [self.i1, self.i2, self.i3], [self.r1, self.r2, self.r3])
        self.assertEqual(results[0].area_id, "W3")
        self.assertEqual(results[1].area_id, "W1")
        self.assertEqual(results[2].area_id, "W2")

    def test_partial_failure(self):
        """valid, invalid, valid preserves valid results."""
        invalid_t = "NotAThermalOutput"
        results = calculate_mortality_risk_batch([self.t1, invalid_t, self.t3], [self.i1, self.i3], allow_partial_failures=True)
        self.assertEqual(results[0].calculation_status, "COMPUTED")
        self.assertEqual(results[1].calculation_status, "INSUFFICIENT_DATA")
        self.assertEqual(results[2].calculation_status, "COMPUTED")
        
    def test_missing_info_pool_record(self):
        """Verify structured failure behavior if info pool missing but calc can partially succeed."""
        results = calculate_mortality_risk_batch([self.t1], [], [self.r1])
        # Base calculator still computes but some factors might be zero/default.
        self.assertEqual(results[0].calculation_status, "COMPUTED")
        self.assertEqual(results[0].vulnerability_score, 0.0)

    def test_missing_resource_pool_record(self):
        """Verify behavior if resource missing."""
        results = calculate_mortality_risk_batch([self.t1], [self.i1], [])
        self.assertEqual(results[0].calculation_status, "COMPUTED")
        self.assertEqual(results[0].adaptive_capacity_score, 0.0)

    def test_duplicate_area_ids(self):
        """Duplicate area_ids in primary thermal_outputs produce INSUFFICIENT_DATA for the duplicates."""
        results = calculate_mortality_risk_batch([self.t1, self.t1], [self.i1], [self.r1], allow_partial_failures=True)
        self.assertEqual(results[0].calculation_status, "INSUFFICIENT_DATA")
        self.assertIn("DUPLICATE", results[0].method_version)
        self.assertEqual(results[1].calculation_status, "INSUFFICIENT_DATA")

    def test_empty_input(self):
        """Empty input."""
        results = calculate_mortality_risk_batch([])
        self.assertEqual(len(results), 0)

    def test_single_ward_batch(self):
        """Single ward through batch interface."""
        results = calculate_mortality_risk_batch([self.t1], [self.i1], [self.r1])
        self.assertEqual(len(results), 1)

    def test_numerical_parity(self):
        """batch == single MortalityService result."""
        res_batch = calculate_mortality_risk_batch([self.t1], [self.i1], [self.r1])[0]
        res_single = calculate_mortality_risk(self.t1, self.i1, self.r1)
        self.assertEqual(res_batch.risk_score, res_single.risk_score)

if __name__ == "__main__":
    unittest.main()
