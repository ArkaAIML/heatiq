# Weather History Implementation Report

## 1. Files Created
- `backend/prediction/weather_history/__init__.py`
- `backend/prediction/weather_history/schemas.py`
- `backend/prediction/weather_history/storage.py`
- `backend/prediction/weather_history/api.py`
- `backend/prediction/weather_history/parser.py`
- `backend/prediction/weather_history/tests/test_weather_history.py`
- `backend/prediction/weather_history/smoke_test.py`
- `backend/prediction/weather_history/README.md`

## 2. Database Schema
SQLite database (defaulting to `weather_history.db`) containing the `hourly_history` table with composite primary key `(location, timestamp)`. Uses `PRAGMA journal_mode=WAL` for concurrent write/read optimization.

## 3. API Provider
Open-Meteo via `httpx`, querying the standard `/v1/forecast` endpoint with `start_date` and `end_date` mapped to retrieve historical data chunks efficiently.

## 4. Provider-to-Canonical Mappings
- `temperature_2m` (°C) -> `temperature_c`
- `dew_point_2m` (°C) -> `dewpoint_c`
- `relative_humidity_2m` (%) -> `relative_humidity_pct`
- `wind_speed_10m` (`wind_speed_unit=ms`) -> `wind_speed_ms`
- `surface_pressure` (hPa * 100) -> `surface_pressure_pa` (Pa)
- `shortwave_radiation` -> `solar_radiation_wm2`
- `thermal_radiation` -> Not provided by Open-Meteo free tier; safely mapped to `None`.

## 5. Timestamp Handling
Timezone-naive UTC strictly serialized as ISO-8601 strings (e.g. `YYYY-MM-DDTHH:MM:SSZ`). 

## 6. Parser Behavior
Takes a requested range, determines exactly which ISO-8601 timestamps are required at a 1-hour cadence, diffs this against what `storage.py` says is already on disk, extracts the minimum bounding box of missing time, and asks `api.py` to fetch it.

## 7. Storage Behavior
Uses `INSERT OR IGNORE` so duplicate fetching caused by bounded box requests silently succeeds without throwing IntegrityErrors. Never creates duplicates.

## 8. Retention Behavior
Default is rolling 60 days. Executed strictly *after* API fetches to prevent data destruction in case the API goes down. Timestamps strictly older than `NOW - 60 days` are deleted via a `DELETE` query.

## 9. Gap Detection
If `storage.py` still lacks timestamps even after `api.py` returns, `parser.py` logs a clear gap warning and returns only the data it successfully found. It does not interpolate.

## 10. Validation Behavior
`api.py` verifies the response schema, discarding any records where even a single required canonical variable is missing/NaN (effectively turning bad API rows into a gap the parser detects).

## 11. Test Results
8 passing Pytest tests verifying all required rules:
- Empty database fetching
- Existing history reuse
- Partial/missing fetching
- Duplicate records ignore
- Missing timestamp gap detection
- Rolling retention pruning
- Multiple locations isolation
- Failed API call resilience

## 12. Real Bhubaneswar Smoke-Test Result
Successfully requested the past 72 hours for Bhubaneswar. Fetched 73 distinct hourly rows. Storage correctly persisted them. No duplicate issues. Fast query response. Canonical parsing succeeded (`surface_pressure_pa` correctly returned as ~100100.0 Pa).

## 13. Known Limitations
Open-Meteo's standard endpoints do not provide downward longwave thermal radiation (`strd` in ERA5). The ML canonical schema expects `thermal_radiation_wm2`. As instructed, I did not fabricate this value; it is passed as `None`. The downstream ML may need to either adapt to this missing feature or source it from a premium tier API.

## 14. Exact future interface to Prediction Filter/Gate
```python
manager = WeatherHistoryManager(store, api)
canonical_records = manager.get_history(
    location="Bhubaneswar", 
    latitude=20.296, 
    longitude=85.824, 
    start_time="2026-08-01T00:00:00Z", 
    end_time="2026-08-07T23:00:00Z"
)
# Prediction Gate can then easily convert `canonical_records` to xarray.Dataset
```

## 15. Confirmation of Non-Interference
The existing `PredictionFilter` -> `PredictionAdapter` -> `dummyml` architecture was completely untouched. The new `weather_history` module operates as a parallel, dormant subsystem until explicitly wired up in a future task.
