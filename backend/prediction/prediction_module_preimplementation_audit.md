# Prediction Module Pre-Implementation Audit

## 1. Current Prediction Module Structure
The Prediction Module is located at `HeatIQ/backend/prediction/` and consists of:
- `__init__.py`: Initialization file.
- `adapter.py`: Acts as the Prediction Gate, insulating the dummy ML.
- `filter.py`: Extracts features from the globally acquired data.
- `schemas.py`: Defines the `PredictionOutput` schema.
- `tests/test_adapter.py`: Scaffold tests for the adapter.

## 2. Current Entry Point
The module has two primary entry points invoked sequentially by `wire1.py`:
1. `PredictionFilter.filter(canonical_data)`
2. `PredictionAdapter.predict_batch(ml_inputs)`

## 3. Current Data Flow
```text
location
   ↓
(GlobalDataAcquisitionAdapter)
   ↓
CanonicalAcquiredData (Currently containing pre-engineered lag/temporal features)
   ↓
PredictionFilter (Extracts the exact 24 ML features required)
   ↓
ml_inputs (List[Dict[str, Any]])
   ↓
PredictionAdapter (Constructs fake ThermalOutput objects to satisfy dummy ML interface)
   ↓
dummy_prediction_and_recommendation_batch (dummyml.service)
   ↓
PredictionAdapter (Maps dummy results to PredictionOutput)
   ↓
PredictionOutput
```

## 4. Current Schemas
- **`PredictionOutput`**: Contains `area_id`, `prediction_generated_at`, `forecast_for`, `forecast_horizon_days`, `thermal_hazard_score`, `predicted_max_utci_c`, `thermal_stress_level`, `model_name`, `model_version`. **Mismatch:** The real ML model only predicts `target_temperature_max_c_d1`. It does not output UTCI or Hazard Scores.
- **`CanonicalAcquiredData`**: Owned by Global Acquisition, but contains ML-specific features (e.g., `temperature_max_lag_1d`, `temperature_mean_prev_3d`, `day_of_year_sin`).

## 5. Current Filter
The `PredictionFilter` extracts exactly 24 pre-engineered features from `CanonicalAcquiredData`. It explicitly checks for features like `temperature_max_lag_3d`. This means the filter expects **already-engineered 24 features**, not raw/hourly weather data.

## 6. Current Gate
The `PredictionAdapter` serves as the Gate. It accepts `ml_inputs`, validates `area_id` alignment, translates them into `ThermalOutput` objects (a hack to feed the dummy ML), invokes the model, and translates the dummy output back to `PredictionOutput`. Currently, it connects strictly to `dummyml`.

## 7. Current Dummy ML Boundary
The dummy ML (`dummy_prediction_and_recommendation_batch`) is completely insulated behind the `PredictionAdapter`. It accepts `ThermalOutput` and produces a dummy result. Replacing it will only require changes inside the `PredictionAdapter` (the Gate).

## 8. Current Weather Acquisition
The Prediction Module currently **owns NO weather acquisition**. It relies entirely on the Global Data Acquisition layer to pass it `CanonicalAcquiredData`.

## 9. Current History Storage
The Prediction Module currently has **NO history storage mechanism** (no databases, SQLite, Parquet, or in-memory caches). It expects the global data object to already contain the past historical feature rollups.

## 10. Current Tests
- `tests/test_adapter.py`: This is a **mock/scaffold test**. It directly instantiates a `ThermalOutput` object and passes it to `PredictionAdapter.predict_batch()`, completely bypassing `PredictionFilter` and actual weather data. It only proves that the dummy ML can be invoked with mocked input and returns a mocked output schema.

## 11. Current Dependencies
- `backend.data_acquisition.schemas.CanonicalAcquiredData`
- `backend.thermalengine.schemas.ThermalOutput`
- `dummyml.service`

## 12. Current Relationship with Global Data Acquisition
The Prediction Module is tightly coupled to Global Data Acquisition for its feature engineering. Instead of receiving raw hourly data and deriving the ML features itself, it forces Global Acquisition to calculate ML lags, means, and calendar sines/cosines.

## 13. Comparison with Real ML Requirements

| Requirement | Current implementation | Status | Notes |
|-------------|------------------------|--------|-------|
| Hourly weather history | Relies on `CanonicalAcquiredData` which only provides current snapshot + pre-rolled lags. | **MISSING** | No hourly series is passed to Prediction. |
| ≥7 complete local days | No local history storage exists. | **MISSING** | Prediction cannot maintain 7 days of data. |
| ML preprocessing | Feature engineering is done by Global Data Acquisition. | **CONFLICTING** | Real ML preprocessing pipeline must handle this. |
| 24 engineered features | Hardcoded in `PredictionFilter`. | **PARTIAL** | The filter grabs them, but from the wrong place. |
| Linear Regression v1 | Uses `dummyml` | **MISSING** | Will be integrated via Gate later. |
| PredictionOutput schema | Outputs UTCI, Stress Level, Hazard Score. | **CONFLICTING** | Real model only outputs Max Air Temperature. |

## 14. Missing Components
- **History Storage**: A local storage mechanism (e.g., SQLite, Parquet) inside the Prediction Module to maintain a rolling window of ≥7 days of hourly weather per location.
- **History Fetching**: A mechanism to ingest raw hourly weather data into the Prediction Module's history store.

## 15. Conflicting Components
- **`PredictionOutput` Schema**: Demands outputs (UTCI, WBGT, etc.) that the Linear Regression v1 model simply cannot provide.
- **`PredictionFilter`**: Demands 24 engineered features instead of raw hourly data.
- **`CanonicalAcquiredData`**: Contains ML-specific feature fields that should belong strictly to the ML preprocessing layer.

## 16. Potential Architectural Risks
- **Duplicate Feature Engineering**: If the real ML pipeline is plugged in, but Global Data Acquisition keeps calculating lags, we will have duplicated and potentially conflicting feature logic.
- **Schema Mismatch**: If the real ML model outputs temperature, but the system expects UTCI in the `PredictionOutput`, the system will crash unless the predicted temperature is routed through the Thermal Engine to calculate a future UTCI.

## 17. Recommended Implementation Order
1. **Schema Update**: Revise `PredictionOutput` to reflect the actual model output (just predicted max temperature).
2. **History Storage**: Implement a local rolling history storage (SQLite/Parquet) inside `prediction/`.
3. **Filter Update**: Rewrite `PredictionFilter` to accept raw hourly updates, store them in history, and extract the 7-day raw window.
4. **Gate Update**: Update `PredictionAdapter` to take the 7-day raw history, pass it to the real ML preprocessing pipeline (`heatiq-ml/pipeline`), and invoke the real ML model artifact.
5. **Global Cleanup**: Remove ML-specific lag calculations from `CanonicalAcquiredData`.

---

## Final Question Answer

**"What must be added/changed INSIDE the Prediction Module so that it can eventually accept the required hourly weather history, maintain the required historical window, pass the correct raw data to the friend's preprocessing pipeline, invoke the real Linear Regression v1 model through a Gate, and return a correct PredictionOutput?"**

1. **Added:** A History Storage mechanism (e.g., SQLite/Parquet or in-memory ring buffer) strictly inside the Prediction Module to persist and manage the required ≥7 days of hourly weather per location.
2. **Changed:** `PredictionFilter` must be rewritten to accept raw hourly weather payloads, append them to the History Storage, and output the required raw 7-day historical window (instead of blindly demanding 24 pre-engineered features).
3. **Changed:** `PredictionAdapter` (the Gate) must take this raw 7-day window, route it through the real ML preprocessing pipeline (which handles aggregation, lags, and calendar features), and then pass the resulting 24 features into the relocated Linear Regression v1 model artifact.
4. **Changed:** `PredictionOutput` must be stripped of `predicted_max_utci_c`, `thermal_hazard_score`, and `thermal_stress_level`, as the model strictly outputs `target_temperature_max_c_d1` (°C). If the wider HeatIQ system requires future UTCI, the output of the Prediction Module must be mathematically chained into the Thermal Engine elsewhere in the architecture.
