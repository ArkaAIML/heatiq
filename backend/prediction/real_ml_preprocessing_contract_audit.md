# REAL ML PREPROCESSING CONTRACT AUDIT

## MOST IMPORTANT QUESTIONS

**1. EXACTLY what raw hourly data must weekhistory provide?**
The pipeline internally expects an `xarray.Dataset` containing perfectly continuous, hourly, timezone-naive UTC timestamps (`valid_time`). If bypassing the ERA5-specific cleaning step, it expects the 7 canonical variables: `temperature_c`, `dewpoint_c`, `relative_humidity_pct`, `wind_speed_ms`, `surface_pressure_pa`, `solar_radiation_wm2`, and `thermal_radiation_wm2`. If feeding the ERA5 raw layer, it expects `t2m` (K), `d2m` (K), `u10` (m/s), `v10` (m/s), `sp` (Pa), `ssrd` (accumulated J/m²), and `strd` (accumulated J/m²).

**2. EXACTLY how much historical data is required to produce one valid prediction?**
**At least 6 complete local days**. The temporal feature logic (in `features.py`) shifts variables up to 3 days and rolls means up to 5 days. It explicitly drops the first 5 rows to prevent NaN leakage. To output a single valid prediction for Day $D$, the pipeline needs complete daily aggregates for Day $D-5$ through Day $D$.

**3. EXACTLY what timezone/day definition does the ML pipeline use?**
The pipeline explicitly converts UTC `valid_time` hourly records into a **local timezone** (defaulting to `"Asia/Kolkata"`). A "day" is defined as a local calendar day. It strictly calculates the expected number of hours for each local day (e.g., handling DST if applicable) and drops boundary days that don't have the full complement of hours.

**4. EXACTLY what 24 features does the pipeline generate?**
1. `temperature_max_c`, 2. `temperature_min_c`, 3. `temperature_mean_c`, 4. `dewpoint_mean_c`, 5. `relative_humidity_mean_pct`, 6. `relative_humidity_max_pct`, 7. `wind_speed_mean_ms`, 8. `wind_speed_max_ms`, 9. `solar_radiation_max_wm2`, 10. `solar_radiation_mean_wm2`, 11. `thermal_radiation_mean_wm2`, 12. `surface_pressure_mean_pa`, 13. `temperature_max_lag_1d`, 14. `temperature_max_lag_2d`, 15. `temperature_max_lag_3d`, 16. `temperature_min_lag_1d`, 17. `temperature_mean_prev_3d`, 18. `temperature_mean_prev_5d`, 19. `temperature_max_prev_3d`, 20. `humidity_mean_prev_3d`, 21. `month`, 22. `day_of_year`, 23. `day_of_year_sin`, 24. `day_of_year_cos`.

**5. EXACTLY what order are those 24 features passed to the model?**
The order is exactly as listed in Question #4 (derived by sequentially applying `DAILY_WEATHER_COLUMNS`, `TEMPORAL_FEATURE_COLUMNS`, and `CALENDAR_FEATURE_COLUMNS` from `features.py`).

**6. Can our existing Open-Meteo acquisition supply all required raw variables?**
Yes, but with caveats. Open-Meteo provides solar radiation as mean flux (W/m²), whereas the raw ML entrypoint (`clean.py`) expects ERA5 accumulated radiation (J/m²). Also, Open-Meteo provides wind speed/direction or directly provides `wind_speed_10m`, whereas the ERA5 logic expects u/v vectors (`u10`, `v10`). 

**7. What provider → ML transformations are required?**
If using `clean.py` as the entrypoint: 
- °C to Kelvin (`t2m`, `d2m`)
- Mean flux (W/m²) to Accumulated (J/m²) using the accumulation seconds (`ssrd`, `strd`)
- Wind magnitude/direction to u/v vectors (`u10`, `v10`)
If using `features.py` (canonical) as the entrypoint:
- No transformations required; Open-Meteo directly maps to the canonical dataset.

**8. Are there any actual ERA5-specific assumptions?**
Yes. The `clean.py` module is deeply tied to ERA5 NetCDF conventions. It expects `valid_time`, `latitude`, `longitude` coordinates, accumulated radiation (`ssrd`, `strd`), Kelvin temperatures, u/v wind vectors, and Pascal surface pressure.

**9. What exact object/schema should Prediction Gate eventually provide to the ML preprocessing layer?**
An `xarray.Dataset` (or equivalently a `pandas.DataFrame` converted to xarray) containing the 7 `CANONICAL_WEATHER_VARIABLES` indexed by a timezone-naive UTC `valid_time`. This completely bypasses the ERA5-specific cleaning step while retaining all mathematical feature engineering.

---

## AUDIT DETAILS

### 1. ML preprocessing entry point
- Raw ERA5 Entry: `ml.preprocessing.clean.derive_canonical_weather(dataset)`
- Canonical Entry (Recommended): `ml.preprocessing.features.build_daily_feature_frame(dataset, timezone)`

### 2. Exact raw hourly input schema (Canonical)
- **Type**: `xarray.Dataset`
- **Dimension**: `valid_time`
- **Fields**: 7 canonical weather variables.

### 3. Exact field names
`temperature_c`, `dewpoint_c`, `relative_humidity_pct`, `wind_speed_ms`, `surface_pressure_pa`, `solar_radiation_wm2`, `thermal_radiation_wm2`.

### 4. Exact units
°C, °C, %, m/s, Pa, W/m², W/m².

### 5. Timestamp requirements
Must be uniquely indexed by `valid_time`.

### 6. Timezone requirements
`valid_time` must be timezone-naive UTC. The pipeline localizes it and converts it to a target timezone string (e.g., "Asia/Kolkata").

### 7. Frequency requirements
Exactly 1-hour intervals (`pd.Timedelta(hours=1)`).

### 8. Consecutiveness requirements
Strictly consecutive. Missing hours raise `ValueError("valid_time must contain uninterrupted hourly observations")`.

### 9. Minimum history requirement
6 complete local days (5 for rolling window + 1 for the day being predicted).

### 10. Exact daily aggregation rules
- Time is converted to local timezone.
- Partial local boundary days (e.g., the first and last days which don't have 24 hours) are dropped.
- Aggregations: `mean` (temperature, dewpoint, RH, wind, solar, thermal, pressure), `max` (temperature, RH, wind, solar), `min` (temperature).

### 11. Exact temporal/lag requirements
Shifted by 1, 2, and 3 local days for Max Temp. Shifted by 1 local day for Min Temp.

### 12. Exact rolling-window requirements
- 3-day rolling mean: Temp Mean, RH Mean
- 3-day rolling max: Temp Max
- 5-day rolling mean: Temp Mean

### 13. Exact calendar-feature generation
- `month`: integer (1-12)
- `day_of_year`: integer (1-366)
- `day_of_year_sin`: `sin(2 * pi * (day_of_year - 1) / 365.25)`
- `day_of_year_cos`: `cos(2 * pi * (day_of_year - 1) / 365.25)`

### 14 & 15. Exact 24-feature output & order
See Question #4.

### 16. Model input contract
A `pandas.DataFrame` containing the exact 24 features in the correct order. The model artifact's `metadata.feature_names` strictly enforces this.

### 17. Model target
`target_temperature_max_c_d1` (Unit: degC, Horizon: 1 day).

### 18. ERA5-specific assumptions
The `clean.py` module is explicitly hardcoded for ERA5 `t2m`, `ssrd`, etc. The rest of the pipeline (`features.py`, `supervised.py`) is completely independent of ERA5.

### 19. Open-Meteo compatibility
Open-Meteo perfectly matches the required *canonical* dataset, meaning it can bypass `clean.py` and feed directly into `features.py`.

### 20. Required provider-to-pipeline transformations
No transformations are required if we target the `CANONICAL_WEATHER_VARIABLES` interface instead of the raw ERA5 interface.

### 21 & 22. Missing-data / Duplicate / Out-of-order behavior
**STRICT REJECTION.** Any missing value (`NaN`), non-finite value, duplicate timestamp, out-of-order timestamp, or gap in the hourly sequence results in an immediate `ValueError`. No interpolation is performed.

### 23. Recommended Prediction → ML boundary
The Prediction Gate should supply an `xarray.Dataset` (containing the 7 canonical variables with a UTC hourly `valid_time` index) directly to `ml.preprocessing.features.build_daily_feature_frame()`. This avoids translating HeatIQ's Open-Meteo data into fake ERA5 NetCDF formats.

### 24. Requirements that the future weekhistory subsystem MUST satisfy
- Must maintain a contiguous, gapless hourly series.
- Must provide at least 6 full local days (in target timezone) prior to the prediction day.
- Must never return missing values; if the provider is down or gaps exist, it must either explicitly backfill/interpolate *before* handing off to the ML pipeline, or fail gracefully.

### 25. Unknowns requiring clarification
- If Prediction requires a 7-day rolling window but the ML drops boundary days (first/last), `weekhistory` may need to over-fetch by at least 1-2 days to ensure 6 *complete* local days remain after truncation. We need to define exactly how many hours to request to guarantee 6 intact local days in "Asia/Kolkata".
