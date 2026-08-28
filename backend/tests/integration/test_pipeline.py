import os
import unittest
import shutil
from pathlib import Path
from unittest.mock import patch
import json
import pandas as pd

from backend.wiring.wire1 import process_location
from backend.wiring.wire2 import get_recommendation
from datalake.core.cache_manager import DATA_DIR
from backend.wiring.ward_context_store.store import WardContextStore
from backend.data_acquisition.schemas import CanonicalAcquiredData

class TestIntegrationPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Force deterministic mock provider
        os.environ["HEATIQ_WEATHER_PROVIDER"] = "mock"

    def setUp(self):
        # Clean caches and context store before each test
        if DATA_DIR.exists():
            shutil.rmtree(DATA_DIR)
            
        store = WardContextStore()
        if store.data_dir.exists():
            shutil.rmtree(store.data_dir)
            
    def test_end_to_end_pipeline_isolation_and_lineage(self):
        """
        Tests Wire 1 -> Store -> Wire 2
        Proves data lineage, cross-ward isolation, and prevention of re-computation.
        """
        # 1. Run Wire 1 (Bhubaneswar)
        ward_results = process_location("Bhubaneswar")
        
        # Verify 3 distinct wards processed
        self.assertEqual(len(ward_results), 3)
        area_ids = {r.area_id for r in ward_results}
        self.assertSetEqual(area_ids, {"WARD_001", "WARD_002", "WARD_003"})
        
        # 2. Check Ward Context Store
        store = WardContextStore()
        
        ctx_001 = store.get("WARD_001")
        ctx_002 = store.get("WARD_002")
        ctx_003 = store.get("WARD_003")
        
        # Verify isolation: each context must retain distinct Info/Resource inputs
        self.assertEqual(ctx_001.context.info_pool.population, 50000)
        self.assertEqual(ctx_001.context.resource_pool.hospital_count, 2)
        
        self.assertEqual(ctx_002.context.info_pool.population, 30000)
        self.assertEqual(ctx_002.context.resource_pool.hospital_count, 0)
        
        self.assertTrue(pd.isna(ctx_003.context.info_pool.population) or ctx_003.context.info_pool.population is None)
        
        # Assert Data Lineage: Timestamp survives from acquisition through Thermal to Context
        # Mock provider sets timestamp
        self.assertTrue(ctx_001.context.timestamp)
        self.assertEqual(ctx_001.context.timestamp, ctx_002.context.timestamp) # Same atmospheric condition
        
        # Assert Data Lineage: Prediction output is populated
        self.assertIsNotNone(ctx_001.context.prediction)
        
        # Assert Data Lineage: Mortality output is populated (calculated)
        self.assertIsNotNone(ctx_001.context.mortality)
        self.assertEqual(ctx_001.context.mortality.calculation_status, "COMPUTED")
        
        # 3. Test Wire 2 (No re-computation)
        with patch('backend.wiring.wire1.calculate_thermal_indices') as mock_thermal:
            recommendation = get_recommendation("WARD_002")
            
            # Wire 2 should NOT invoke thermal/mortality/etc.
            mock_thermal.assert_not_called()
            
            # Validate Recommendation output
            self.assertEqual(recommendation["area_id"], "WARD_002")
            self.assertIn("actions", recommendation)
            self.assertIn("freshness", recommendation)
            self.assertIn("generated_timestamp", recommendation["freshness"])

    def test_global_failure_propagation(self):
        """
        Verify that failing Info Pool source (e.g. invalid location) does not crash,
        and results in empty list while preserving architecture.
        """
        # Run with an unknown location to trigger Data Lake failure
        ward_results = process_location("UNKNOWN_LOCATION")
        
        # In our architecture, if InfoPool resolves to empty, the adapter currently 
        # returns empty area_ids, resulting in an empty list. 
        self.assertEqual(len(ward_results), 0)

        # Let's mock the adapter to return a failing atmospheric input globally
        with patch('backend.data_acquisition.adapter.GlobalDataAcquisitionAdapter.acquire_for_location') as mock_acquire:
            mock_acquire.return_value = CanonicalAcquiredData(
                location="Bhubaneswar", timestamp="2024-01-01T00:00:00Z", provider="failed"
            )
            
            ward_results_partial = process_location("Bhubaneswar")
            
            # Since global acquisition fails, we return an empty list now
            self.assertEqual(len(ward_results_partial), 0)

if __name__ == '__main__':
    unittest.main()
