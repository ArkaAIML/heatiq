import pandas as pd
from pathlib import Path
from datalake.core.ingestion import DatasetIngester
import pytest
import io
import zipfile

def test_f014_nullable_integer():
    from datalake.infopoolparser.parser import parse_info_pool
    df = parse_info_pool("Bhubaneswar")
    # WARD_001 has 50000 population, WARD_003 has missing population
    assert pd.isna(df.loc[df["area_id"] == "WARD_003", "population"].iloc[0])
    # The dtype should be Int64, not float64
    assert df["population"].dtype == "Int64"
    assert df.loc[df["area_id"] == "WARD_001", "population"].iloc[0] == 50000

def test_ingest_json():
    json_data = b'[{"ward": "A", "val": 1}, {"ward": "B", "val": 2}]'
    buffer = io.BytesIO(json_data)
    df = DatasetIngester.ingest(buffer, {"format": "json"})
    assert len(df) == 2
    assert df["ward"].iloc[0] == "A"

def test_ingest_ndjson():
    ndjson_data = b'{"ward": "A", "val": 1}\n{"ward": "B", "val": 2}\n'
    buffer = io.BytesIO(ndjson_data)
    df = DatasetIngester.ingest(buffer, {"format": "ndjson"})
    assert len(df) == 2

def test_ingest_excel():
    df_out = pd.DataFrame({"ward": ["A", "B"], "val": [1, 2]})
    buffer = io.BytesIO()
    df_out.to_excel(buffer, index=False)
    buffer.seek(0)
    df_in = DatasetIngester.ingest(buffer, {"format": "excel"})
    assert len(df_in) == 2

def test_ingest_parquet():
    df_out = pd.DataFrame({"ward": ["A", "B"], "val": [1, 2]})
    buffer = io.BytesIO()
    df_out.to_parquet(buffer, index=False)
    buffer.seek(0)
    df_in = DatasetIngester.ingest(buffer, {"format": "parquet"})
    assert len(df_in) == 2

def test_ingest_zip():
    df_out = pd.DataFrame({"ward": ["A", "B"], "val": [1, 2]})
    csv_buf = io.BytesIO()
    df_out.to_csv(csv_buf, index=False)
    csv_buf.seek(0)
    
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr("data.csv", csv_buf.read())
    zip_buf.seek(0)
    
    df_in = DatasetIngester.ingest(zip_buf, {"format": "zip"})
    assert len(df_in) == 2
