"""
HeatIQ Wiring Layer - Wire 2 (On-Demand Recommendation Flow)
"""
from typing import Optional, Dict, Any
from backend.wardfilter.schemas import WardContext
from backend.wiring.ward_context_store.store import WardContextStore, ContextNotFoundError, ContextCorruptionError
from backend.recommendation.adapter import RecommendationAdapter

def get_recommendation(area_id: str) -> Dict[str, Any]:
    """
    Executes the on-demand recommendation flow for a given area_id.
    
    Retrieves the existing context and delegates to the Recommendation Engine.
    Handles missing/unknown wards cleanly.
    """
    if not area_id:
        return {"status": "ERROR", "message": "area_id is required", "area_id": None}
        
    store = WardContextStore()
    
    # 1. Retrieve the already-available structured information for that ward.
    try:
        ward_result = store.get(area_id)
        if not ward_result or not ward_result.context:
            return {
                "status": "ERROR", 
                "message": f"No context found for area_id: {area_id}", 
                "area_id": area_id
            }
    except ContextNotFoundError:
        return {
            "status": "NOT_FOUND", 
            "message": f"No context found for area_id: {area_id}", 
            "area_id": area_id
        }
    except ContextCorruptionError as e:
        return {
            "status": "CORRUPT_RECORD", 
            "message": f"Stored context is corrupt for area_id: {area_id} - {str(e)}", 
            "area_id": area_id
        }
    except Exception as e:
        return {
            "status": "SOURCE_UNAVAILABLE", 
            "message": f"Store unavailable for area_id: {area_id} - {str(e)}", 
            "area_id": area_id
        }
        
    # 2. Pass the required structured information into Recommendation Engine via the boundary adapter
    adapter = RecommendationAdapter()
    result = adapter.generate_recommendation(ward_result.context)
        
    # Attach the freshness metadata to the response so callers can evaluate staleness
    freshness = store.get_freshness(area_id)
    
    output = result.to_dict()
    output["freshness"] = freshness
    return output
