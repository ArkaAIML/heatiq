"""
HeatIQ Wiring Layer - Wire 2 (On-Demand Recommendation Flow)
"""
from typing import Optional, Dict, Any
from backend.wardfilter.schemas import WardContext
from backend.wiring.wire2_store.context_store import Wire2ContextStore, Wire2ContextNotFoundError, Wire2ContextCorruptionError
from backend.recommendation.adapter import RecommendationAdapter
from backend.recommendation.filter import RecommendationFilter
from backend.wiring.wire2_store.store import RecommendationStore

def get_recommendation(area_id: str, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Executes the on-demand recommendation flow for a given area_id.
    
    Retrieves the existing context, applies the Recommendation Filter, 
    and delegates to the Recommendation Engine Gate.
    Handles missing/unknown wards cleanly.
    Stores the output in Wire 2 temporary storage.
    """
    if not area_id:
        return {"status": "ERROR", "message": "area_id is required", "area_id": None}
        
    rec_store = RecommendationStore()
    
    if not force_refresh:
        # Check Wire 2 storage first
        existing_rec = rec_store.get(area_id)
        if existing_rec:
            # We already have a recommendation in Wire 2
            output = existing_rec.to_dict()
            output["freshness"] = {"status": "CACHED_IN_WIRE2"}
            return output

    context_store = Wire2ContextStore()
    
    # 1. Retrieve the already-available structured information for that ward.
    try:
        ward_result = context_store.get_ward_filter_result(area_id)
    except Wire2ContextNotFoundError:
        return {
            "status": "NOT_FOUND", 
            "message": f"No context found in Wire 2 for area_id: {area_id}", 
            "area_id": area_id
        }
    except Wire2ContextCorruptionError as e:
        return {
            "status": "CORRUPT_RECORD", 
            "message": f"Stored context is corrupt in Wire 2 for area_id: {area_id} - {str(e)}", 
            "area_id": area_id
        }
    except Exception as e:
        return {
            "status": "SOURCE_UNAVAILABLE", 
            "message": f"Store unavailable for area_id: {area_id} - {str(e)}", 
            "area_id": area_id
        }
        
    # 2. Filter the context to extract provisional recommendation inputs
    try:
        filtered_input = RecommendationFilter.filter(ward_result)
    except Exception as e:
         return {
            "status": "ERROR", 
            "message": f"Recommendation filter failed: {str(e)}", 
            "area_id": area_id
        }
    
    # 3. Pass the provisional structured information into Recommendation Engine Gate
    adapter = RecommendationAdapter()
    result = adapter.generate_recommendation(filtered_input)
    
    # 4. Store the result in Wire 2
    rec_store.put(area_id, result)
        
    # Attach the freshness metadata to the response so callers can evaluate staleness
    # Note: Cache freshness validation is deferred per architectural instructions.
    freshness = {"status": "FRESHNESS_CHECK_DEFERRED"}
    
    output = result.to_dict()
    output["freshness"] = freshness
    return output
