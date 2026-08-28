"""
Unit tests for the Mortality Risk Index Module.
Verifies MVP heuristic determinism, missing data handling, batch mapping, and new multiplicative risk logic.
"""

import unittest
import json

from backend.thermalengine import ThermalOutput
from backend.mortality import (
    InfoPoolRecord,
    ResourcePoolRecord,
    calculate_mortality_risk,
    calculate_mortality_risk_batch,
    MortalityOutput,
    BaseMortalityRiskCalculator,
    MortalityService
)


class TestMortalityRiskModule(unittest.TestCase):

    def setUp(self):
        # Base Thermal Outputs
        self.t_extreme = ThermalOutput(area_id="W1", timestamp="2026-05-20", heat_index_c=None, utci_c=None, wbgt_c=None, htsi=100.0, htsi_category="EXTREME", calculation_status="COMPUTED")
        self.t_severe = ThermalOutput(area_id="W1", timestamp="2026-05-20", heat_index_c=None, utci_c=None, wbgt_c=None, htsi=85.0, htsi_category="EXTREME", calculation_status="COMPUTED")
        self.t_high = ThermalOutput(area_id="W1", timestamp="2026-05-20", heat_index_c=None, utci_c=None, wbgt_c=None, htsi=50.0, htsi_category="HIGH", calculation_status="COMPUTED")
        self.t_low = ThermalOutput(area_id="W2", timestamp="2026-05-20", heat_index_c=None, utci_c=None, wbgt_c=None, htsi=0.0, htsi_category="LOW", calculation_status="COMPUTED")
        self.t_missing = ThermalOutput(area_id="W3", timestamp="2026-05-20", heat_index_c=None, utci_c=None, wbgt_c=None, htsi=None, htsi_category=None, calculation_status="INSUFFICIENT_DATA")
        
        # InfoPool Records (Exposure and Vulnerability)
        self.i_vuln_exp = InfoPoolRecord(area_id="W1", population=50000, population_density=20000, outdoor_worker_fraction=0.5, elderly_fraction=0.20, child_fraction=0.20)
        self.i_safe = InfoPoolRecord(area_id="W2", population=50000, population_density=2000, outdoor_worker_fraction=0.1, elderly_fraction=0.05, child_fraction=0.10)
        
        # ResourcePool Records
        self.r_poor = ResourcePoolRecord(area_id="W1", hospital_count=0, cooling_centre_count=1)
        self.r_strong = ResourcePoolRecord(area_id="W2", hospital_count=5, cooling_centre_count=10)

    # --- Scenario-based Tests ---

    def test_zero_thermal_hazard_yields_zero_risk(self):
        """Zero thermal hazard (HTSI=0) -> risk_score = 0."""
        out = calculate_mortality_risk(self.t_low, self.i_vuln_exp, self.r_poor)
        self.assertEqual(out.risk_score, 0.0)
        self.assertEqual(out.risk_level, "LOW")

    def test_scenario_a_severe_heat_high_vuln_high_exp_poor_res(self):
        """Scenario A: Severe heat + high vulnerability + high exposure + poor resources -> very high/extreme relative risk."""
        out = calculate_mortality_risk(self.t_extreme, self.i_vuln_exp, self.r_poor)
        self.assertEqual(out.risk_level, "EXTREME")
        self.assertGreaterEqual(out.risk_score, 75.0)

    def test_scenario_b_same_heat_low_vuln_low_exp_strong_res(self):
        """Scenario B: Same severe heat + low vulnerability + low exposure + strong resources -> meaningfully lower risk than Scenario A."""
        out_a = calculate_mortality_risk(self.t_extreme, self.i_vuln_exp, self.r_poor)
        out_b = calculate_mortality_risk(self.t_extreme, self.i_safe, self.r_strong)
        
        self.assertLess(out_b.risk_score, out_a.risk_score)
        self.assertTrue((out_a.risk_score - out_b.risk_score) > 5.0)

    def test_scenario_c_increasing_htsi(self):
        """Scenario C: Same demographics/resources, increasing HTSI -> risk_score increases monotonically."""
        out_low = calculate_mortality_risk(self.t_low, self.i_vuln_exp, self.r_poor)
        out_high = calculate_mortality_risk(self.t_high, self.i_vuln_exp, self.r_poor)
        out_extreme = calculate_mortality_risk(self.t_extreme, self.i_vuln_exp, self.r_poor)
        
        self.assertLess(out_low.risk_score, out_high.risk_score)
        self.assertLess(out_high.risk_score, out_extreme.risk_score)

    def test_scenario_d_increasing_resource_coverage(self):
        """Scenario D: Same heat/demographics, increasing resource coverage -> risk_score decreases monotonically."""
        r1 = ResourcePoolRecord(area_id="W1", hospital_count=0, cooling_centre_count=0)
        r2 = ResourcePoolRecord(area_id="W1", hospital_count=2, cooling_centre_count=4)
        r3 = ResourcePoolRecord(area_id="W1", hospital_count=10, cooling_centre_count=20)
        
        out_1 = calculate_mortality_risk(self.t_high, self.i_vuln_exp, r1)
        out_2 = calculate_mortality_risk(self.t_high, self.i_vuln_exp, r2)
        out_3 = calculate_mortality_risk(self.t_high, self.i_vuln_exp, r3)
        
        self.assertGreaterEqual(out_1.risk_score, out_2.risk_score)
        self.assertGreaterEqual(out_2.risk_score, out_3.risk_score)
        self.assertLess(out_3.risk_score, out_1.risk_score)

    def test_scenario_e_increasing_elderly_fraction(self):
        """Scenario E: Same heat/resources, increasing elderly fraction -> risk_score does not decrease."""
        i1 = InfoPoolRecord(area_id="W1", population=10000, elderly_fraction=0.05)
        i2 = InfoPoolRecord(area_id="W1", population=10000, elderly_fraction=0.15)
        i3 = InfoPoolRecord(area_id="W1", population=10000, elderly_fraction=0.25)
        
        out_1 = calculate_mortality_risk(self.t_severe, i1, self.r_poor)
        out_2 = calculate_mortality_risk(self.t_severe, i2, self.r_poor)
        out_3 = calculate_mortality_risk(self.t_severe, i3, self.r_poor)
        
        self.assertGreaterEqual(out_2.risk_score, out_1.risk_score)
        self.assertGreaterEqual(out_3.risk_score, out_2.risk_score)

    def test_scenario_f_increasing_outdoor_worker(self):
        """Scenario F: Same heat/resources, increasing outdoor-worker fraction -> risk_score does not decrease."""
        i1 = InfoPoolRecord(area_id="W1", population=10000, outdoor_worker_fraction=0.1)
        i2 = InfoPoolRecord(area_id="W1", population=10000, outdoor_worker_fraction=0.3)
        i3 = InfoPoolRecord(area_id="W1", population=10000, outdoor_worker_fraction=0.6)
        
        out_1 = calculate_mortality_risk(self.t_severe, i1, self.r_poor)
        out_2 = calculate_mortality_risk(self.t_severe, i2, self.r_poor)
        out_3 = calculate_mortality_risk(self.t_severe, i3, self.r_poor)
        
        self.assertGreaterEqual(out_2.risk_score, out_1.risk_score)
        self.assertGreaterEqual(out_3.risk_score, out_2.risk_score)

    def test_scenario_g_doubling_hospitals(self):
        """Scenario G: Same ward population, doubling hospitals -> adaptive_capacity_score increases, risk_score decreases or remains equal."""
        r1 = ResourcePoolRecord(area_id="W1", hospital_count=2, cooling_centre_count=2)
        r2 = ResourcePoolRecord(area_id="W1", hospital_count=4, cooling_centre_count=2)
        
        out_1 = calculate_mortality_risk(self.t_severe, self.i_vuln_exp, r1)
        out_2 = calculate_mortality_risk(self.t_severe, self.i_vuln_exp, r2)
        
        self.assertGreater(out_2.adaptive_capacity_score, out_1.adaptive_capacity_score)
        self.assertLessEqual(out_2.risk_score, out_1.risk_score)

    def test_scenario_h_doubling_population_same_hospitals(self):
        """Scenario H: Same hospital count, doubling population -> hospital coverage decreases, adaptive_capacity_score does not increase."""
        i1 = InfoPoolRecord(area_id="W1", population=10000, elderly_fraction=0.1, outdoor_worker_fraction=0.2)
        i2 = InfoPoolRecord(area_id="W1", population=20000, elderly_fraction=0.1, outdoor_worker_fraction=0.2)
        
        r1 = ResourcePoolRecord(area_id="W1", hospital_count=2, cooling_centre_count=2)
        
        out_1 = calculate_mortality_risk(self.t_severe, i1, r1)
        out_2 = calculate_mortality_risk(self.t_severe, i2, r1)
        
        self.assertLess(out_2.adaptive_capacity_score, out_1.adaptive_capacity_score)

    # --- Edge Cases & Data Handling Tests ---

    def test_missing_data_insufficient_thermal(self):
        """Verify INSUFFICIENT_DATA is returned if thermal hazard is missing."""
        out = calculate_mortality_risk(self.t_missing, self.i_vuln_exp, self.r_poor)
        self.assertEqual(out.calculation_status, "INSUFFICIENT_DATA")
        self.assertIsNone(out.risk_level)
        self.assertIsNone(out.risk_score)
        self.assertIn("MISSING_THERMAL_DATA", out.method_version)

    def test_missing_population_disables_resource_coverage(self):
        """If population is missing, adaptive capacity cannot be calculated and yields 0."""
        # i_no_pop doesn't have population
        i_no_pop = InfoPoolRecord(area_id="W1", elderly_fraction=0.20, outdoor_worker_fraction=0.30)
        out = calculate_mortality_risk(self.t_severe, i_no_pop, self.r_strong)
        
        self.assertEqual(out.adaptive_capacity_score, 0.0)
        self.assertIn("UNKNOWN_ADAPTIVE_CAPACITY", out.reason_codes)

    def test_batch_ward_matching(self):
        """Verify the service correctly matches area_ids even if lists are misaligned."""
        t_list = [self.t_low, self.t_extreme] # W2, W1
        i_list = [self.i_vuln_exp, self.i_safe] # W1, W2 (different order)
        r_list = [self.r_poor, self.r_strong] # W1, W2
        
        results = calculate_mortality_risk_batch(t_list, i_list, r_list)
        
        self.assertEqual(len(results), 2)
        
        # Result 0 should be for W2 because t_list[0] is W2
        self.assertEqual(results[0].area_id, "W2")
        self.assertEqual(results[0].risk_level, "LOW")
        
        # Result 1 should be for W1
        self.assertEqual(results[1].area_id, "W1")
        self.assertEqual(results[1].risk_level, "EXTREME")

    def test_ml_calculator_interface(self):
        """Verify that the BaseMortalityRiskCalculator can be implemented by a custom class."""
        class MockMLCalculator(BaseMortalityRiskCalculator):
            def calculate(self, thermal, info=None, resource=None):
                return MortalityOutput(
                    area_id=thermal.area_id,
                    timestamp=thermal.timestamp,
                    risk_score=99.9,
                    risk_level="EXTREME",
                    method_version="ML_v2"
                )
                
        service = MortalityService(calculator=MockMLCalculator())
        out = service.calculate_mortality_risk(self.t_extreme)
        self.assertEqual(out.risk_level, "EXTREME")
        self.assertEqual(out.method_version, "ML_v2")
        self.assertEqual(out.risk_score, 99.9)


if __name__ == "__main__":
    unittest.main()
