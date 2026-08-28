"""
HeatIQ Backend Main Gate
The primary entrypoint for the HeatIQ backend API/service.
"""
from typing import List, Dict, Any
from backend.wiring.wire1 import process_location
from backend.wiring.wire2 import get_recommendation
from backend.wardfilter.schemas import WardFilterResult
from backend.recommendation.schemas import RecommendationOutput

class MainGate:
    """
    Main Gateway exposing the primary backend use cases.
    """
    @staticmethod
    def process_location(location: str, allow_partial_failures: bool = True) -> List[WardFilterResult]:
        """
        Executes Wire 1: Full System Flow.
        Acquires data for a location, computes thermal/prediction indices, 
        and fans out the context and risk assessment to all wards in the location.
        """
        return process_location(location, allow_partial_failures)
        
    @staticmethod
    def get_recommendation(area_id: str, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Executes Wire 2: Recommendation Generation.
        Retrieves stored ward context and generates an actionable recommendation.
        """
        return get_recommendation(area_id, force_refresh)
