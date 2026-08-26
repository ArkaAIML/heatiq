# HeatIQ Backend Core Logic

This directory contains the completely isolated backend and core logic for the HeatIQ project (SIH26083).

## Architecture

- **`app/api/schemas.py`**: Pydantic models mapping incoming and outgoing data, ensuring no missing/corrupted data causes issues.
- **`app/processing/preprocessing.py`**: A dedicated preprocessing layer for validation, normalization, and unit handling.
- **`app/calculations/`**: The core mathematical engine containing NWS Heat Index and WBGT formulas in isolated modules.
- **`app/thermal/htsi.py`**: The Human Thermal Stress Index calculation, determining vulnerability from a weighted formula.
- **`app/risk/mortality.py`**: A risk model interface currently using a configurable baseline proxy, designed specifically so future ML models can easily be plugged in.
- **`app/spatial/grid.py`**: Spatial analysis modeling overall grid/ward risk and affected population.
- **`app/population/exposure.py`**: Derives aggregate exposure insights for vulnerable categories (e.g. outdoor workers).
- **`app/recommendations/engine.py`**: The recommendation engine identifying necessary government action and severity levels.
- **`app/alerts/generator.py`**: The public-alert generator capable of emitting formatted payloads.

## Running the API

1. Set up a virtual environment: `python -m venv .venv`
2. Activate and install dependencies: `pip install fastapi pydantic uvicorn httpx`
3. Run the API: `uvicorn app.main:app --reload`

## Running Tests

```bash
pytest
```

## Not Implemented Yet
- True ML integration (RiskModelInterface is provided).
- 3-5 day time-series forecast rolling predictions.
- Integration with live weather APIs (data ingestion abstraction is pending).
