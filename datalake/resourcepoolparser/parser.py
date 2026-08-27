"""
Resource Pool Parser.
Responsible for extracting and normalizing Resource Pool data from external sources.
"""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Any
import logging

from datalake.core.config_loader import get_resourcepool_sources
from datalake.core.ingestion import DatasetIngester

logger = logging.getLogger(__name__)

# Canonical schema definition
CANONICAL_SCHEMA = {
    "area_id": pd.StringDtype(),
    "hospital_count": pd.Int64Dtype(),
    "hospital_capacity": pd.Float64Dtype(),
    "cooling_centre_count": pd.Int64Dtype(),
    "distance_to_healthcare_km": pd.Float64Dtype(),
    "resource_capacity_score": pd.Float64Dtype()
}

def parse_resource_pool(location: str) -> pd.DataFrame:
    """
    Parses configured Resource Pool sources for a specific location.
    Merges multiple sources using a priority-based cascading fill.
    Returns a canonical DataFrame with strictly enforced types.
    """
    sources = get_resourcepool_sources()
    if not sources:
        raise ValueError("No Resource Pool sources configured.")

    base_dir = Path(__file__).parent.parent.parent
    merged_df = None

    for src in sources:
        # Determine path (handle local paths explicitly, or pass remote URLs directly)
        if src.get("type") == "local":
            path = base_dir / src.get("path", "")
            if not path.exists():
                logger.warning(f"Source path not found: {path}")
                continue
        else:
            path = src.get("url", src.get("path", ""))

        try:
            # 1. Ingest via generic parser
            df = DatasetIngester.ingest(path, src)
        except Exception as e:
            logger.error(f"Failed to ingest {path}: {str(e)}")
            continue
            
        # 2. Geographic Filtering
        if 'city' in df.columns:
            df = df[df['city'].str.lower() == location.lower()]
            
        if df.empty:
            continue

        # 3. Schema Normalization
        mapping = src.get("mapping", {})
        if mapping:
            df = df.rename(columns=mapping)
            
        # Ensure required column area_id exists
        if "area_id" not in df.columns:
            logger.warning(f"Source {path} missing 'area_id' after mapping.")
            continue
            
        # Add missing canonical columns with pd.NA
        for col in CANONICAL_SCHEMA.keys():
            if col not in df.columns:
                df[col] = pd.NA
                
        df = df[list(CANONICAL_SCHEMA.keys())]
        
        # Validate and coerce types
        for col, dtype in CANONICAL_SCHEMA.items():
            if dtype == pd.Int64Dtype() or dtype == pd.Float64Dtype():
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df[col] = df[col].astype(dtype)

        # Remove duplicates within the source
        df = df.drop_duplicates(subset=["area_id"], keep="first")
        df = df.set_index("area_id")

        # 4. Merge (Priority-based cascading fill)
        if merged_df is None:
            merged_df = df
        else:
            merged_df = merged_df.combine_first(df)

    if merged_df is None:
        merged_df = pd.DataFrame(columns=list(CANONICAL_SCHEMA.keys())).set_index("area_id")
        for col, dtype in CANONICAL_SCHEMA.items():
            if col != "area_id":
                merged_df[col] = merged_df[col].astype(dtype)

    return merged_df.reset_index()
