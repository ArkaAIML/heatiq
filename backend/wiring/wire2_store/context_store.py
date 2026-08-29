"""
Wire 2 Context Store
A lightweight storage store dedicated to holding WardContext instances handed off by Wire 1.
This ensures the Recommendation Engine never has to reach into Wire 1.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from backend.wardfilter.schemas import WardContext, WardFilterResult
from backend.thermalengine.schemas import ThermalOutput
from backend.mortality.schemas import MortalityOutput, InfoPoolRecord, ResourcePoolRecord
from backend.prediction.schemas import PredictionOutput

logger = logging.getLogger(__name__)

class Wire2ContextNotFoundError(Exception):
    pass

class Wire2ContextCorruptionError(Exception):
    pass

class Wire2ContextStore:
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or (Path(__file__).parent / "context_data")
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, area_id: str) -> Path:
        safe_id = "".join(c for c in area_id if c.isalnum() or c in "_-")
        return self.data_dir / f"{safe_id}_context.json"

    def put_ward_filter_result(self, area_id: str, result: WardFilterResult) -> None:
        """
        Stores the WardFilterResult in Wire 2 storage.
        """
        file_path = self._get_file_path(area_id)
        
        try:
            with file_path.open("w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f)
        except Exception as e:
            logger.error(f"stage=Wire2ContextStore area_id={area_id} reason=WRITE_FAILURE details='{str(e)}'")

    def get_ward_filter_result(self, area_id: str) -> WardFilterResult:
        """
        Retrieves the WardFilterResult for the given area_id from Wire 2.
        """
        file_path = self._get_file_path(area_id)
        if not file_path.exists():
            logger.error(f"stage=Wire2ContextStore area_id={area_id} reason=NOT_FOUND")
            raise Wire2ContextNotFoundError(f"Context not found in Wire 2 for {area_id}")

        try:
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                
            ctx_data = data.get("context", {})
            if not ctx_data:
                raise ValueError("Missing context payload in stored result")
                
            thermal = ThermalOutput(**ctx_data["thermal"])
            prediction = PredictionOutput(**ctx_data["prediction"]) if ctx_data.get("prediction") else None
            mortality = MortalityOutput(**ctx_data["mortality"])
            info = InfoPoolRecord(**ctx_data["info_pool"])
            resource = ResourcePoolRecord(**ctx_data["resource_pool"])
            
            context = WardContext(
                area_id=ctx_data["area_id"],
                timestamp=ctx_data["timestamp"],
                thermal=thermal,
                prediction=prediction,
                mortality=mortality,
                info_pool=info,
                resource_pool=resource
            )
            
            return WardFilterResult(
                area_id=data["area_id"],
                timestamp=data["timestamp"],
                severity=data.get("severity"),
                message=data.get("message"),
                condition_message=data.get("condition_message"),
                recommended_actions=data.get("recommended_actions", []),
                triggered_conditions=data.get("triggered_conditions", []),
                context=context,
                calculation_status=data.get("calculation_status", "COMPUTED"),
                method_version=data.get("method_version", "WARD_FILTER_MVP")
            )
        except Exception as e:
            logger.error(f"stage=Wire2ContextStore area_id={area_id} reason=CORRUPT_RECORD details='{str(e)}'")
            raise Wire2ContextCorruptionError(f"Failed to read Wire 2 context for {area_id}: {str(e)}")
