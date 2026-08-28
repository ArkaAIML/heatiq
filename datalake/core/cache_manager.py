"""
Cache Manager.
Handles reading and writing to canonical Parquet datasets.
Implements lazy-creation semantics (parse only if not exists/invalid).
"""

import pandas as pd
from pathlib import Path
from datetime import datetime

from datalake.infopoolparser.parser import parse_info_pool
from datalake.resourcepoolparser.parser import parse_resource_pool

DATA_DIR = Path(__file__).parent.parent / "data"

def _ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)

def _is_valid_parquet(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        # Check if it's readable and contains area_id
        df = pd.read_parquet(path)
        if "area_id" not in df.columns:
            return False
        if df.empty:
            return False
        return True
    except Exception:
        return False

def get_canonical_info_pool(location: str, force_refresh: bool = False) -> pd.DataFrame:
    """
    Retrieves the canonical Info Pool dataset for a location.
    If it does not exist or is invalid, parses it from sources and saves to Parquet.
    """
    _ensure_dir(DATA_DIR / "info")
    file_path = DATA_DIR / "info" / f"{location.lower()}.parquet"

    if not force_refresh and _is_valid_parquet(file_path):
        # Cache hit: Load directly
        return pd.read_parquet(file_path)

    # Cache miss: Parse, write, and return
    df = parse_info_pool(location)
    
    # Add simple provenance metadata via pyarrow
    import pyarrow as pa
    import pyarrow.parquet as pq
    import json
    from datalake.core.config_loader import get_infopool_sources

    sources = get_infopool_sources()
    source_ids = [s.get("name", "unknown") for s in sources]
    source_types = [s.get("type", "unknown") for s in sources]
    
    table = pa.Table.from_pandas(df)
    metadata = {
        b"source_identifier": json.dumps(source_ids).encode(),
        b"source_type": json.dumps(source_types).encode(),
        b"parser_version": b"1.0.0",
        b"parsed_timestamp": str(datetime.now().isoformat()).encode()
    }
    
    new_meta = table.schema.metadata or {}
    new_meta.update(metadata)
    table = table.replace_schema_metadata(new_meta)
    
    pq.write_table(table, file_path)
    
    return df

def get_canonical_resource_pool(location: str, force_refresh: bool = False) -> pd.DataFrame:
    """
    Retrieves the canonical Resource Pool dataset for a location.
    If it does not exist or is invalid, parses it from sources and saves to Parquet.
    """
    _ensure_dir(DATA_DIR / "resources")
    file_path = DATA_DIR / "resources" / f"{location.lower()}.parquet"

    if not force_refresh and _is_valid_parquet(file_path):
        # Cache hit: Load directly
        return pd.read_parquet(file_path)

    # Cache miss: Parse, write, and return
    df = parse_resource_pool(location)
    
    import pyarrow as pa
    import pyarrow.parquet as pq
    import json
    from datalake.core.config_loader import get_resourcepool_sources

    sources = get_resourcepool_sources()
    source_ids = [s.get("name", "unknown") for s in sources]
    source_types = [s.get("type", "unknown") for s in sources]
    
    table = pa.Table.from_pandas(df)
    metadata = {
        b"source_identifier": json.dumps(source_ids).encode(),
        b"source_type": json.dumps(source_types).encode(),
        b"parser_version": b"1.0.0",
        b"parsed_timestamp": str(datetime.now().isoformat()).encode()
    }
    
    new_meta = table.schema.metadata or {}
    new_meta.update(metadata)
    table = table.replace_schema_metadata(new_meta)
    
    pq.write_table(table, file_path)
    
    return df
