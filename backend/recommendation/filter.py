from typing import Dict, Any
from backend.wardfilter.schemas import WardFilterResult

class RecommendationFilter:
    """
    Filters the WardFilterResult into a structured dictionary suitable for 
    RecommendationEngine consumption.
    """
    @staticmethod
    def filter(result: WardFilterResult) -> Dict[str, Any]:
        """
        Converts the WardFilterResult into a dictionary.
        This provides a boundary to filter out any sensitive or irrelevant 
        internal state before it hits the Gemini Prompt.
        """
        context = result.context
        return {
            "area_id": result.area_id,
            "timestamp": result.timestamp,
            "deterministic_result": {
                "severity": result.severity,
                "condition_message": result.condition_message,
                "triggered_conditions": result.triggered_conditions,
                "recommended_actions": result.recommended_actions,
                "calculation_status": result.calculation_status,
                "method_version": result.method_version
            },
            "thermal": context.thermal.to_dict(),
            "prediction": context.prediction.to_dict() if context.prediction else None,
            "mortality": context.mortality.to_dict(),
            "info_pool": {
                "population": context.info_pool.population,
                "vulnerability_score": context.info_pool.vulnerability_score,
            },
            "resource_pool": {
                "hospital_count": context.resource_pool.hospital_count,
                "hospital_capacity": context.resource_pool.hospital_capacity,
                "cooling_centre_count": context.resource_pool.cooling_centre_count,
                "distance_to_healthcare_km": context.resource_pool.distance_to_healthcare_km,
                "resource_capacity_score": context.resource_pool.resource_capacity_score
            }
        }
