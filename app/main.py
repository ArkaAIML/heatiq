from fastapi import FastAPI
from app.api.routes.analysis import router as analysis_router

app = FastAPI(title="HeatIQ Backend API", version="2.0")

app.include_router(analysis_router, prefix="/api/v1")

@app.get("/health")
def health_check():
    return {"status": "ok"}
