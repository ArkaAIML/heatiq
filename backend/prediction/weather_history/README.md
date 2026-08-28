# Weather History Subsystem

This subsystem is responsible for persisting and maintaining a contiguous block of RAW canonical hourly weather data to be used by the HeatIQ prediction engine. 

**IMPORTANT NOTE**: This subsystem stores raw hourly weather. It does **not** generate ML engineered features (such as rolling lags, sines/cosines, or aggregations). Those belong strictly to the ML preprocessing pipeline.

## Purpose & Architecture
The subsystem guarantees that the final integration point (the Prediction Gate) can query an unbroken, contiguous history of hourly records to pass into the ML preprocessing module. 

- `parser.py`: The "brain" (`WeatherHistoryManager`). Checks local storage, finds missing intervals in the requested date range, triggers API fetches only for missing blocks, and enforces rolling retention.
- `api.py`: External Open-Meteo API wrapper. Connects to `api.open-meteo.com/v1/forecast`, requesting specific historical windows, and normalizes fields to Canonical formats.
- `storage.py`: SQLite-based local persistence (`WeatherHistoryStore`). Uses `INSERT OR IGNORE` to prevent duplication, supports configurable retention, and indexes quickly on `(location, timestamp)`.
- `schemas.py`: Defines the `CanonicalHourlyWeather` dataclass representing the exact fields required by the ML contract.

## Database & Schema
The subsystem uses SQLite (`hourly_history` table) stored locally (by default in `weather_history.db`).
Schema guarantees unique rows for the composite key `(location, timestamp)`:
- `location` (TEXT)
- `timestamp` (TEXT) - ISO-8601 UTC Timezone Naive (e.g., "2026-08-01T00:00:00Z")
- `latitude`, `longitude` (REAL)
- `temperature_c`, `dewpoint_c`, `relative_humidity_pct`, `wind_speed_ms`, `surface_pressure_pa`, `solar_radiation_wm2`, `thermal_radiation_wm2` (REAL)

## Timestamp Convention
All timestamps stored in the database are strings normalized to timezone-naive UTC (represented in standard ISO-8601 strings ending in "Z"). 

## Provider-to-Canonical Mapping (Open-Meteo)
- `temperature_2m` (°C) -> `temperature_c`
- `dew_point_2m` (°C) -> `dewpoint_c`
- `relative_humidity_2m` (%) -> `relative_humidity_pct`
- `wind_speed_10m` (using `wind_speed_unit=ms`) -> `wind_speed_ms`
- `surface_pressure` (hPa) * 100 -> `surface_pressure_pa` (Pa)
- `shortwave_radiation` (W/m²) -> `solar_radiation_wm2`
- **Known Limitation**: `thermal_radiation_wm2` (downward longwave) is not natively exposed in the Open-Meteo forecast API's free tier. In compliance with the rules forbidding fabricated data, it is cleanly mapped to `None`.

## Retention Policy
Configured via `WeatherHistoryManager.RETENTION_DAYS` (default: 60 days). 
Old records are silently pruned (deleted) *after* new records are fetched and validated to ensure no data is deleted prematurely in case of an API failure.

## Gap Detection & Validation
The manager computes the list of exactly what hourly timestamps *should* exist between the start and end dates. Any missing hourly timestamp triggers an API fetch. If the API cannot fulfill the data (e.g. provider gap), the gap is logged and returned as is, ensuring the caller knows the data isn't perfectly contiguous.

## Tests
Tested with `pytest` covering all required scenarios: Empty DB, Existing Complete, Partial Missing, Gap Detection, Out-of-Order behavior, Retention, Duplication, and Failed API states.

## Future Prediction Gate Integration Point
In the next phase, `PredictionGate` will invoke `WeatherHistoryManager.get_history(loc, lat, lon, start, end)` to get the contiguous `CanonicalHourlyWeather` list, convert it to an `xarray.Dataset`, and feed it directly to the real ML model.
