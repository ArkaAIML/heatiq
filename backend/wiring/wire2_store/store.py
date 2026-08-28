"""
Wire 2 Recommendation Store
A temporary storage for the completed recommendations to satisfy the 
"Wire 2 Loop ends at Wire 2" architectural constraint.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from backend.recommendation.schemas import RecommendationOutput, FailedRecommendationOutput

logger = logging.getLogger(__name__)

class RecommendationNotFoundError(Exception):
    pass

class RecommendationStore:
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or (Path(__file__).parent / "data")
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, area_id: str) -> Path:
        safe_id = "".join(c for c in area_id if c.isalnum() or c in "_-")
        return self.data_dir / f"{safe_id}_rec.json"

    def put(self, area_id: str, recommendation: RecommendationOutput | FailedRecommendationOutput) -> None:
        """
        Stores the RecommendationOutput in Wire 2 storage.
        """
        file_path = self._get_file_path(area_id)
        
        try:
            with file_path.open("w", encoding="utf-8") as f:
                json.dump(recommendation.to_dict(), f)
        except Exception as e:
            logger.error(f"stage=RecommendationStore area_id={area_id} reason=WRITE_FAILURE details='{str(e)}'")

    def get(self, area_id: str) -> Optional[RecommendationOutput | FailedRecommendationOutput]:
        """
        Retrieves the recommendation for the given area_id from Wire 2.
        """
        file_path = self._get_file_path(area_id)
        if not file_path.exists():
            return None

        try:
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Simple check to see if it's failed or successful
            if data.get("status") == "ERROR" or data.get("generated_at") is None:
                return FailedRecommendationOutput(
                    area_id=data.get("area_id", area_id),
                    status=data.get("status", "ERROR"),
                    message=data.get("message", "Unknown error")
                )
            else:
                return RecommendationOutput.from_dict(data)
        except Exception as e:
            logger.error(f"stage=RecommendationStore area_id={area_id} reason=CORRUPT_RECORD details='{str(e)}'")
            return None
