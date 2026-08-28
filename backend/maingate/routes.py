import uuid
import time
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any

from backend.maingate.models import (
    HeatIQProcessRequest,
    HeatIQProcessResponse,
    APIKeyGenerateRequest,
    APIKeyGenerateResponse,
    APIKeyRevokeRequest,
    APIKeyListResponse
)
from backend.maingate.auth import verify_api_key
from backend.maingate.database import generate_key, revoke_key, list_keys
from backend.maingate.monitor import add_request_trace
from backend.wiring.wire1 import process_location
from backend.wiring.wire2 import get_recommendation

logger = logging.getLogger(__name__)

api_router = APIRouter()

# --- API KEY MANAGEMENT ---

@api_router.post("/keys", response_model=APIKeyGenerateResponse)
def create_api_key(req: APIKeyGenerateRequest):
    """Generates a new API Key."""
    key_id, raw_key = generate_key(req.label)
    return APIKeyGenerateResponse(
        key_id=key_id,
        api_key=raw_key,
        label=req.label,
        status="active",
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    )

@api_router.get("/keys", response_model=APIKeyListResponse)
def get_all_keys():
    """Lists all API Keys (metadata only)."""
    return APIKeyListResponse(keys=list_keys())

@api_router.delete("/keys")
def delete_api_key(req: APIKeyRevokeRequest):
    """Revokes an API Key."""
    success = revoke_key(req.key_id)
    if not success:
        raise HTTPException(status_code=404, detail="Key ID not found")
    return {"status": "revoked"}

# --- MONITORING ---

@api_router.get("/monitor")
def get_live_monitor():
    """Returns the latest request traces."""
    from backend.maingate.monitor import get_recent_traces
    return {"traces": get_recent_traces()}

# --- CORE HEATIQ ENDPOINTS ---

@api_router.post("/process", response_model=HeatIQProcessResponse)
def process_heatiq_input(req: HeatIQProcessRequest, api_key: str = Depends(verify_api_key)):
    """
    Main Gate entry point.
    Routes to either Wire 1 (place name) or Wire 2 (area_id).
    """
    request_id = f"req_{uuid.uuid4().hex[:8]}"
    start_time = time.time()
    
    if req.location:
        # Route: PLACE_NAME -> Wire 1
        logger.info(f"[REQ {request_id}] API authenticated")
        logger.info(f"[REQ {request_id}] input={req.location}")
        logger.info(f"[REQ {request_id}] routing=PLACE_NAME")
        logger.info(f"[REQ {request_id}] Wire1 started")
        
        try:
            results = process_location(req.location, allow_partial_failures=True)
            duration = time.time() - start_time
            logger.info(f"[REQ {request_id}] Wire1 completed wards={len(results)}")
            logger.info(f"[REQ {request_id}] response completed duration={duration:.2f}s")
            
            add_request_trace({
                "request_id": request_id,
                "input": req.location,
                "route": "PLACE_NAME",
                "status": "SUCCESS",
                "duration_ms": int(duration * 1000)
            })
            
            return HeatIQProcessResponse(
                request_id=request_id,
                status="success",
                route="PLACE_NAME",
                results=[r.to_dict() for r in results]
            )
            
        except Exception as e:
            logger.error(f"[REQ {request_id}] Wire 1 Failed: {e}")
            add_request_trace({
                "request_id": request_id,
                "input": req.location,
                "route": "PLACE_NAME",
                "status": "ERROR",
                "duration_ms": int((time.time() - start_time) * 1000)
            })
            raise HTTPException(status_code=500, detail="Wire 1 processing failed.")
            
    elif req.area_id:
        # Route: AREA_ID -> Wire 2
        logger.info(f"[REQ {request_id}] API authenticated")
        logger.info(f"[REQ {request_id}] input={req.area_id}")
        logger.info(f"[REQ {request_id}] routing=AREA_ID")
        
        try:
            # Wire 2 executes Recommendation Engine
            logger.info(f"[REQ {request_id}] Wire2 started")
            rec = get_recommendation(req.area_id)
            
            duration = time.time() - start_time
            
            if rec.get("status") == "NOT_FOUND":
                # Wire 1 prerequisite not met
                logger.warning(f"[REQ {request_id}] Wire 1 context missing")
                logger.warning(f"[REQ {request_id}] Wire2 NOT invoked")
                
                add_request_trace({
                    "request_id": request_id,
                    "input": req.area_id,
                    "route": "AREA_ID",
                    "status": "NOT_READY",
                    "duration_ms": int(duration * 1000)
                })
                
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, 
                    detail="ward_context_not_available"
                )
                
            logger.info(f"[REQ {request_id}] Wire2 completed")
            logger.info(f"[REQ {request_id}] response completed duration={duration:.2f}s")
            
            add_request_trace({
                "request_id": request_id,
                "input": req.area_id,
                "route": "AREA_ID",
                "status": "SUCCESS",
                "duration_ms": int(duration * 1000)
            })
            
            return HeatIQProcessResponse(
                request_id=request_id,
                status="success",
                route="AREA_ID",
                area_id=req.area_id,
                results=rec
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[REQ {request_id}] Wire 2 Failed: {e}")
            add_request_trace({
                "request_id": request_id,
                "input": req.area_id,
                "route": "AREA_ID",
                "status": "ERROR",
                "duration_ms": int((time.time() - start_time) * 1000)
            })
            raise HTTPException(status_code=500, detail="Wire 2 processing failed.")
            
    else:
        # Invalid input
        add_request_trace({
            "request_id": request_id,
            "input": "unknown",
            "route": "UNKNOWN",
            "status": "BAD_REQUEST",
            "duration_ms": 0
        })
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Must provide either 'location' or 'area_id'"
        )

@api_router.get("/health")
def health_check():
    """Basic health check endpoint."""
    return {"status": "ok"}
