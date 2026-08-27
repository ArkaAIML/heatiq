"""
Ward Context Store
A lightweight, true-persistence store for complete WardFilterResult contexts.
Files are saved as JSON to a local data directory.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

class ContextNotFoundError(Exception):
    pass

class ContextCorruptionError(Exception):
    pass

from backend.wardfilter.schemas import WardFilterResult, WardContext
from backend.thermalengine.schemas import ThermalOutput
from backend.mortality.schemas import MortalityOutput, InfoPoolRecord, ResourcePoolRecord
from backend.prediction.schemas import PredictionOutput

@dataclass
class WardFreshnessMetadata:
    observation_timestamp: str
    generated_timestamp: str

class WardContextStore:
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or (Path(__file__).parent / "data")
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, area_id: str) -> Path:
        # Sanitize area_id to prevent path traversal
        safe_id = "".join(c for c in area_id if c.isalnum() or c in "_-")
        return self.data_dir / f"{safe_id}.json"

    def put(self, area_id: str, result: WardFilterResult) -> None:
        """
        Stores the complete WardFilterResult (including WardContext) for the given area_id.
        Wraps the result with freshness metadata.
        """
        file_path = self._get_file_path(area_id)
        
        # Determine timestamps
        observation_timestamp = result.timestamp
        generated_timestamp = datetime.now(timezone.utc).isoformat()
        
        metadata = WardFreshnessMetadata(
            observation_timestamp=observation_timestamp,
            generated_timestamp=generated_timestamp
        )
        
        result_dict = json.loads(result.to_json()) if hasattr(result, "to_json") else result.to_dict()
        
        wrapped_data = {
            "area_id": area_id,
            "metadata": asdict(metadata),
            "result": result_dict
        }
        
        with file_path.open("w", encoding="utf-8") as f:
            json.dump(wrapped_data, f)

    def _parse_ward_filter_result(self, data: Dict[str, Any]) -> Optional[WardFilterResult]:
        try:
            # Reconstruct context if available
            context_data = data.pop("context", None)
            context = None
            if context_data:
                thermal = ThermalOutput(**context_data["thermal"])
                prediction = PredictionOutput(**context_data["prediction"]) if context_data.get("prediction") else None
                mortality = MortalityOutput(**context_data["mortality"])
                info = InfoPoolRecord(**context_data["info_pool"])
                resource = ResourcePoolRecord(**context_data["resource_pool"])
                
                context = WardContext(
                    area_id=context_data["area_id"],
                    timestamp=context_data["timestamp"],
                    thermal=thermal,
                    prediction=prediction,
                    mortality=mortality,
                    info_pool=info,
                    resource_pool=resource
                )
            
            # Reconstruct result
            return WardFilterResult(
                area_id=data["area_id"],
                timestamp=data["timestamp"],
                severity=data.get("severity"),
                message=data.get("message"),
                recommended_actions=data.get("recommended_actions", []),
                triggered_conditions=data.get("triggered_conditions", []),
                context=context,
                calculation_status=data.get("calculation_status", "COMPUTED"),
                method_version=data.get("method_version", "WARD_FILTER_MVP")
            )
        except Exception:
            return None

    def get(self, area_id: str) -> WardFilterResult:
        """
        Retrieves the complete WardFilterResult for the given area_id.
        Reconstructs all nested dataclasses safely.
        Handles both the new wrapped metadata format and the old direct format.
        """
        file_path = self._get_file_path(area_id)
        if not file_path.exists():
            logger.error(f"stage=WardContextStore area_id={area_id} reason=NOT_FOUND")
            raise ContextNotFoundError(f"Context not found for {area_id}")

        try:
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                
            # If "result" key exists, it's the new wrapped format
            if "result" in data and isinstance(data["result"], dict):
                result_data = data["result"]
            else:
                result_data = data  # Old format
                
            res = self._parse_ward_filter_result(result_data)
            if res is None:
                raise ContextCorruptionError(f"Context malformed for {area_id}")
            return res
        except ContextCorruptionError:
            raise
        except Exception as e:
            logger.error(f"stage=WardContextStore area_id={area_id} reason=CORRUPT_RECORD details='{str(e)}'")
            raise ContextCorruptionError(f"Failed to read context for {area_id}: {str(e)}")

    def get_freshness(self, area_id: str) -> Dict[str, Any]:
        """
        Retrieves explicit freshness and lifecycle metadata for a given area_id.
        Returns explicit UNKNOWN state if metadata cannot be determined (e.g. older files).
        """
        file_path = self._get_file_path(area_id)
        if not file_path.exists():
            return {
                "area_id": area_id,
                "is_fresh_determinable": False,
                "status": "NOT_FOUND"
            }

        try:
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                
            if "metadata" in data and "result" in data:
                # New wrapped format
                metadata = data["metadata"]
                return {
                    "area_id": area_id,
                    "is_fresh_determinable": True,
                    "observation_timestamp": metadata.get("observation_timestamp"),
                    "generated_timestamp": metadata.get("generated_timestamp")
                }
            else:
                # Old format - we can only guess observation_timestamp from the result payload
                observation_timestamp = data.get("timestamp")
                return {
                    "area_id": area_id,
                    "is_fresh_determinable": False, # Cannot determine generation time
                    "observation_timestamp": observation_timestamp,
                    "generated_timestamp": None,
                    "status": "MISSING_METADATA"
                }
        except Exception:
            return {
                "area_id": area_id,
                "is_fresh_determinable": False,
                "status": "ERROR_READING_STORE"
            }
