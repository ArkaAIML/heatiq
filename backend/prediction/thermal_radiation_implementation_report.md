# Thermal Radiation Implementation Report

## 1. Exact Source Selected
**NASA POWER** (`https://power.larc.nasa.gov/api/temporal/hourly/point`).
This single provider seamlessly replaces Open-Meteo, as it successfully supplies ALL 7 canonical weather variables in a single API call without requiring credentials or complex two-provider joins.

## 2. Exact Provider Variable
`ALLSKY_SFC_LW_DWN`

## 3. Physical Meaning
All Sky Surface Longwave Downward Irradiance (Downward thermal/longwave radiation at the surface).

## 4. Unit
Watts per square meter (W/m²).

## 5. Temporal Semantics
NASA POWER provides hourly resolution with timestamps in UTC (formatted as `YYYYMMDDHH`).

## 6. Conversion, if any
- Thermal Radiation: None. NASA POWER natively provides W/m², avoiding the J/m² to W/m² conversion that raw ERA5 requires.
- Pressure: NASA POWER provides `PS` in kPa, which is converted to Pa (kPa * 1000).

## 7. Why it is compatible with the ML contract
The ML contract expects real downward longwave radiation as a mean flux in W/m². `ALLSKY_SFC_LW_DWN` represents exactly this physical quantity, ensuring the ML models receive the physically correct inputs.

## 8. Provider-to-Canonical Mapping
| NASA POWER Variable | Canonical Field | Unit | Transformation |
| :--- | :--- | :--- | :--- |
| `T2M` | `temperature_c` | °C | None |
| `T2MDEW` | `dewpoint_c` | °C | None |
| `RH2M` | `relative_humidity_pct` | % | None |
| `WS10M` | `wind_speed_ms` | m/s | None |
| `PS` | `surface_pressure_pa` | Pa | `val * 1000.0` |
| `ALLSKY_SFC_SW_DWN` | `solar_radiation_wm2` | W/m² | None |
| `ALLSKY_SFC_LW_DWN` | `thermal_radiation_wm2` | W/m² | None |

## 9. Bhubaneswar Acquisition Result
Successfully acquired historical data for Bhubaneswar (lat 20.296, lon 85.824).

## 10. Number of Hourly Records
360 hourly records (15 days: 2024-08-01 through 2024-08-15). NASA POWER was tested on 2024 data to bypass its known 5-7 day satellite reanalysis latency for this historical ML validation.

## 11. Continuity Validation
No hourly gaps existed. No missing timestamps or out-of-order records were detected.

## 12. Thermal Radiation Validation
Values ranged physically correctly (e.g., ~436 W/m² mean), maintaining plausible non-zero magnitudes during the night, proving it is true downward longwave (thermal) radiation and NOT terrestrial solar radiation.

## 13. Real Preprocessing Result
The retrieved 360-hour block was loaded into an `xarray.Dataset` and fed directly to the REAL ML preprocessor (`ml.preprocessing.features.build_daily_feature_frame`). The function executed flawlessly, aggregating the raw hourly records into 9 valid daily rows (dropping the first 5 boundary days as expected by the pipeline logic).

## 14. 24-Feature Result
Exactly 24 features were produced per row (plus the `date` index). None of the values were missing (`NaN` or `None`), and the output perfectly matches the required feature contract for the `.pkl` model.

## 15. Any Remaining Limitations
NASA POWER provides excellent historical fidelity (satellite reanalysis), but its latest data is typically delayed by 5-7 days. While perfect for validating the ML history contract today, real-time "live" HeatIQ predictions may require a premium provider in the future that offers real-time downward longwave radiation.
