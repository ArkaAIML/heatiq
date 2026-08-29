from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os
from backend.maingate.routes import api_router

# Initialize FastAPI application
app = FastAPI(
    title="HeatIQ Main Gate",
    description="External API Boundary for HeatIQ",
    version="1.0.0"
)

# Include API router
app.include_router(api_router, prefix="/api")

# Dashboard Templates
TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """Serves the main API Key Management Dashboard."""
    return templates.TemplateResponse(request=request, name="dashboard.html")

