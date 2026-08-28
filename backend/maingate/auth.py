from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from backend.maingate.database import is_key_valid

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)):
    """FastAPI Dependency for authenticating requests."""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key. Provide via X-API-Key header."
        )
        
    if not is_key_valid(api_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or revoked API Key."
        )
    
    return api_key
