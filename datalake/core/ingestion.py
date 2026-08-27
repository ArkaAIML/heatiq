import pandas as pd
from pathlib import Path
from typing import Dict, Any, Union
import zipfile
import io

class UnsupportedFormatError(Exception):
    pass

class DatasetIngester:
    """
    Robust dataset ingester.
    Capable of parsing CSV, TSV, JSON, NDJSON, Excel, Parquet, and ZIPs.
    """
    
    @classmethod
    def ingest(cls, path: Union[str, Path, io.BytesIO], config: Dict[str, Any]) -> pd.DataFrame:
        """
        Ingests a dataset into a pandas DataFrame based on the source config.
        """
        # If it's not a buffer, we can determine format from path if set to auto
        format_type = config.get("format", "auto").lower()
        if format_type == "auto" and not isinstance(path, io.BytesIO):
            format_type = cls._detect_format(str(path))
            
        # Handle ZIP unpacking
        if format_type == "zip":
            if isinstance(path, io.BytesIO):
                return cls._ingest_zip(path, config)
            else:
                return cls._ingest_zip(str(path), config)
            
        # Dispatch to specific parser
        if format_type in ["csv", "tsv"]:
            return cls._ingest_csv(path, config, is_tsv=(format_type == "tsv"))
        elif format_type == "json":
            return cls._ingest_json(path, config)
        elif format_type == "ndjson":
            return cls._ingest_ndjson(path, config)
        elif format_type in ["xlsx", "xls", "excel"]:
            return cls._ingest_excel(path, config)
        elif format_type == "parquet":
            return cls._ingest_parquet(path, config)
        else:
            raise UnsupportedFormatError(f"Unsupported format: {format_type}")
            
    @staticmethod
    def _detect_format(path: str) -> str:
        lower_path = path.lower()
        if lower_path.endswith(".zip"): return "zip"
        if lower_path.endswith(".csv"): return "csv"
        if lower_path.endswith(".tsv"): return "tsv"
        if lower_path.endswith(".json"): return "json"
        if lower_path.endswith(".ndjson") or lower_path.endswith(".jsonl"): return "ndjson"
        if lower_path.endswith(".xlsx") or lower_path.endswith(".xls"): return "excel"
        if lower_path.endswith(".parquet"): return "parquet"
        raise UnsupportedFormatError("Could not auto-detect format. Specify 'format' in config.")
        
    @classmethod
    def _ingest_zip(cls, path_or_buffer: Union[str, io.BytesIO], config: Dict[str, Any]) -> pd.DataFrame:
        with zipfile.ZipFile(path_or_buffer, 'r') as z:
            names = z.namelist()
            # If target_file is specified in config
            target = config.get("target_file")
            if not target:
                # auto-select the first supported structured file
                for n in names:
                    if not n.endswith("/") and not n.startswith("__MACOSX"):
                        try:
                            fmt = cls._detect_format(n)
                            if fmt != "zip":
                                target = n
                                break
                        except UnsupportedFormatError:
                            continue
            
            if not target:
                raise ValueError(f"No supported structured file found in ZIP")
            if target not in names:
                raise ValueError(f"Target file {target} not found in ZIP")
                
            with z.open(target) as f:
                # We extract the content to BytesIO so pandas can read it easily
                content = io.BytesIO(f.read())
                # Create a subconfig for the inner file
                sub_config = config.copy()
                sub_config["format"] = cls._detect_format(target)
                return cls.ingest(content, sub_config)
                
    @staticmethod
    def _ingest_csv(path_or_buffer: Union[str, Path, io.BytesIO], config: Dict[str, Any], is_tsv: bool) -> pd.DataFrame:
        sep = "\t" if is_tsv else config.get("delimiter", ",")
        encoding = config.get("encoding", "utf-8")
        # Do not treat missing strings automatically as zero. Keep pd.NA behavior.
        df = pd.read_csv(path_or_buffer, sep=sep, encoding=encoding, engine="python")
        return df
        
    @staticmethod
    def _ingest_json(path_or_buffer: Union[str, Path, io.BytesIO], config: Dict[str, Any]) -> pd.DataFrame:
        orient = config.get("orient", "records")
        return pd.read_json(path_or_buffer, orient=orient)
        
    @staticmethod
    def _ingest_ndjson(path_or_buffer: Union[str, Path, io.BytesIO], config: Dict[str, Any]) -> pd.DataFrame:
        return pd.read_json(path_or_buffer, orient="records", lines=True)
        
    @staticmethod
    def _ingest_excel(path_or_buffer: Union[str, Path, io.BytesIO], config: Dict[str, Any]) -> pd.DataFrame:
        sheet_name = config.get("sheet_name", 0)
        return pd.read_excel(path_or_buffer, sheet_name=sheet_name)
        
    @staticmethod
    def _ingest_parquet(path_or_buffer: Union[str, Path, io.BytesIO], config: Dict[str, Any]) -> pd.DataFrame:
        return pd.read_parquet(path_or_buffer)
