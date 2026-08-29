from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class HeatIQProcessRequest(BaseModel):
    """
    Request model for the main /api/process endpoint.
    Accepts either a place name (location) or an area_id.
    """
    location: Optional[str] = Field(default=None, description="A place name like 'Bhubaneswar'")
    area_id: Optional[str] = Field(default=None, description="A ward identifier like 'WARD_001'")

class HeatIQProcessResponse(BaseModel):
    """
    Response model for /api/process.
    """
    request_id: str
    status: str
    route: str # "PLACE_NAME" or "AREA_ID"
    area_id: Optional[str] = None
    results: Any = None
    message: Optional[str] = None

class APIKeyGenerateRequest(BaseModel):
    label: Optional[str] = Field(default="Main Gate API Key")

class APIKeyGenerateResponse(BaseModel):
    key_id: str
    api_key: str  # ONLY RETURNED ONCE
    label: str
    created_at: str
    status: str

class APIKeyRevokeRequest(BaseModel):
    key_id: str

class APIKeyListResponse(BaseModel):
    keys: List[Dict[str, Any]]
