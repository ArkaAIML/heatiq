"""
Data Lake tests.
Verifies config loading, parsing, merging, geographic filtering, caching, and data integrity.
"""

import unittest
import pandas as pd
from pathlib import Path
import shutil

from datalake.core.config_loader import load_sources_config
from datalake.infopoolparser.parser import parse_info_pool
from datalake.resourcepoolparser.parser import parse_resource_pool
from datalake.core.cache_manager import get_canonical_info_pool, get_canonical_resource_pool, DATA_DIR

class TestDataLake(unittest.TestCase):

    def setUp(self):
        # Clean up cache before each test
        if DATA_DIR.exists():
            shutil.rmtree(DATA_DIR)

    def test_config_loading(self):
        """Verify sources.toml is loaded correctly."""
        config = load_sources_config()
        self.assertIn("infopool", config)
        self.assertIn("resourcepool", config)
        
        info_sources = config["infopool"]["sources"]
        self.assertEqual(len(info_sources), 2)
        self.assertIn("MOCK_CENSUS", info_sources)

    def test_infopool_parsing_and_merging(self):
        """
        Verify:
        - Parses mock sources
        - Geographic filtering (Bhubaneswar only)
        - Priority-based merging
        - Canonical schema
        """
        df = parse_info_pool("Bhubaneswar")
        
        # WARD_001 should come from MOCK_CENSUS
        # WARD_002 should come from MOCK_CENSUS and filled by MOCK_SURVEY
        # WARD_003 should come entirely from MOCK_SURVEY
        self.assertEqual(len(df), 3)
        
        # Check canonical columns
        expected_cols = [
            "area_id", "population", "population_density", 
            "outdoor_worker_fraction", "elderly_fraction", "child_fraction"
        ]
        for col in expected_cols:
            self.assertIn(col, df.columns)
            
        df = df.set_index("area_id")
        
        # WARD_001
        self.assertEqual(df.loc["WARD_001", "population"], 50000)
        self.assertEqual(df.loc["WARD_001", "elderly_fraction"], 0.20)
        
        # WARD_002 (Filled by MOCK_SURVEY)
        self.assertEqual(df.loc["WARD_002", "population"], 30000) # From CENSUS
        self.assertEqual(df.loc["WARD_002", "elderly_fraction"], 0.15) # From SURVEY
        self.assertEqual(df.loc["WARD_002", "child_fraction"], 0.10) # From SURVEY
        
        # WARD_003
        self.assertTrue(pd.isna(df.loc["WARD_003", "population"])) # Not in SURVEY
        self.assertEqual(df.loc["WARD_003", "elderly_fraction"], 0.10)

    def test_geographic_filtering(self):
        """Verify unrelated geographic records are excluded."""
        df = parse_info_pool("Cuttack")
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["area_id"], "WARD_001")
        self.assertEqual(df.iloc[0]["population"], 40000)

    def test_resourcepool_parsing(self):
        """Verify Resource Pool parsing and merging."""
        df = parse_resource_pool("Bhubaneswar")
        
        self.assertEqual(len(df), 3)
        df = df.set_index("area_id")
        
        # WARD_001
        self.assertEqual(df.loc["WARD_001", "hospital_count"], 2)
        
        # WARD_002 (Combined)
        self.assertEqual(df.loc["WARD_002", "hospital_count"], 0)
        self.assertEqual(df.loc["WARD_002", "cooling_centre_count"], 1) # From COOLING
        
        # WARD_003
        self.assertEqual(df.loc["WARD_003", "cooling_centre_count"], 2)

    def test_lazy_creation(self):
        """Verify dataset does not parse repeatedly if cached."""
        # 1. Fetch
        df1 = get_canonical_info_pool("Bhubaneswar")
        self.assertTrue(len(df1) > 0)
        
        # Check that file exists
        parquet_path = DATA_DIR / "info" / "bhubaneswar.parquet"
        self.assertTrue(parquet_path.exists())
        
        # Modify the parquet file to prove it loads from cache
        df_mod = df1.copy()
        df_mod.loc[df_mod["area_id"] == "WARD_001", "population"] = 999999
        df_mod.to_parquet(parquet_path)
        
        # 2. Fetch again
        df2 = get_canonical_info_pool("Bhubaneswar")
        
        # Should have the modified value, proving it didn't re-parse
        val = df2.loc[df2["area_id"] == "WARD_001", "population"].values[0]
        self.assertEqual(val, 999999)
        
        # 3. Force refresh
        df3 = get_canonical_info_pool("Bhubaneswar", force_refresh=True)
        val3 = df3.loc[df3["area_id"] == "WARD_001", "population"].values[0]
        self.assertEqual(val3, 50000) # Re-parsed

    def test_invalid_cache(self):
        """Verify invalid cache forces re-parse."""
        # Create empty invalid file
        _ = get_canonical_info_pool("Bhubaneswar")
        parquet_path = DATA_DIR / "info" / "bhubaneswar.parquet"
        
        with open(parquet_path, "w") as f:
            f.write("invalid parquet")
            
        # Fetch should re-parse and succeed
        df = get_canonical_info_pool("Bhubaneswar")
        self.assertEqual(len(df), 3)

    def test_provenance_metadata(self):
        """Verify generated Parquet contains lightweight dataset provenance metadata."""
        _ = get_canonical_info_pool("Bhubaneswar")
        parquet_path = DATA_DIR / "info" / "bhubaneswar.parquet"
        
        import pyarrow.parquet as pq
        import json
        
        table = pq.read_table(parquet_path)
        metadata = table.schema.metadata
        
        self.assertIsNotNone(metadata)
        self.assertIn(b"source_identifier", metadata)
        self.assertIn(b"source_type", metadata)
        self.assertIn(b"parser_version", metadata)
        self.assertIn(b"parsed_timestamp", metadata)
        
        # Verify it can be decoded
        source_ids = json.loads(metadata[b"source_identifier"].decode())
        self.assertIsInstance(source_ids, list)
        self.assertTrue(len(source_ids) > 0)

if __name__ == "__main__":
    unittest.main()
