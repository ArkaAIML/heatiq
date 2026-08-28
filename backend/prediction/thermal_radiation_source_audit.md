# Thermal Radiation Source Audit

## 1. What exact variable does the ML pipeline require?
The canonical representation requires `thermal_radiation_wm2`.

## 2. What exact physical quantity does it represent?
It represents **downward thermal (longwave) radiation at the surface**, expressed as a mean flux in Watts per square meter (W/m²).

## 3. Why does the current Open-Meteo implementation fail to provide it?
The current implementation in `api.py` requests `temperature_2m,dew_point_2m,relative_humidity_2m,wind_speed_10m,surface_pressure,shortwave_radiation`. It deliberately omits thermal radiation because standard Open-Meteo forecast variables prioritize shortwave (solar) radiation, and downward longwave is often undocumented or named differently (e.g., `terrestrial_radiation`) depending on the specific underlying model (GFS/ICON vs ERA5). Thus, `api.py` hardcodes the mapping to `None`.

## 4. Is ERA5 suitable?
Yes. The ML pipeline was originally built with ERA5 assumptions (as seen in `clean.py`), meaning it natively expects and mathematically supports ERA5's thermal radiation semantics.

## 5. What exact ERA5 variable should be used?
`strd` (Surface thermal radiation downwards).

## 6. What conversion is required?
In ERA5, `strd` is provided as **accumulated energy** in Joules per square meter (J/m²) since the start of the forecast. To match the canonical `thermal_radiation_wm2`, it must be divided by the accumulation interval in seconds (e.g., 3600 seconds for hourly data) to yield the mean flux in W/m².

## 7. Is a second provider required?
**No, a second provider is not strictly required.** Open-Meteo hosts a dedicated **Historical Weather API (ERA5/ERA5-Land)** that natively serves `strd` (often mapped to `terrestrial_radiation` or similar longwave variables in W/m² directly). However, if HeatIQ must predict the *future* or the *immediate past 5 days* (where ERA5 data is not yet published), we must rely on Open-Meteo's standard forecast API (which stitches together models like GFS or ICON). We just need to explicitly query Open-Meteo's equivalent longwave radiation field (e.g., `terrestrial_radiation`) from the forecast API if supported.

## 8. What is the cleanest provider architecture?
**OPTION A (One provider)** is the cleanest architecture. The Prediction Gate should query a single provider (Open-Meteo) that seamlessly stitches recent/forecast data with historical data. Using a two-source design (e.g., Open-Meteo for temp/wind + Copernicus CDS for radiation) would require complex timezone/timestamp alignment, differing spatial resolutions, and would fail for real-time predictions because Copernicus ERA5 lags behind real-time by several days.

## 9. What is the recommended implementation?
Update `backend/prediction/weather_history/api.py` to append Open-Meteo's downward longwave radiation variable (e.g., `terrestrial_radiation` or `terrestrial_radiation_instant`) to the `hourly=` parameter string. If Open-Meteo provides it directly in W/m² (mean flux), no ERA5-style J/m² conversion is necessary, and it maps cleanly to `thermal_radiation_wm2`. 

## 10. What credentials/dependencies are required?
Using Open-Meteo requires **no API credentials** (for the free tier) and no additional Python dependencies beyond the existing `httpx` client.

## 11. Can we realistically acquire enough Bhubaneswar hourly history for the ML pipeline?
**Yes.** Open-Meteo's historical API contains decades of hourly data, and its forecast API contains up to 3 months of past data. This easily satisfies the ML pipeline's minimum requirement of 6 complete local days.

## 12. What should api.py eventually return?
`api.py` must eventually return a complete `List[CanonicalHourlyWeather]` where `thermal_radiation_wm2` is populated with valid, finite float values in W/m², rather than `None`.

---

## CURRENT OPEN-METEO IMPLEMENTATION TRACE
Located in `backend/prediction/weather_history/api.py`:

| Provider Variable | Canonical Field | Unit | Transformation |
| :--- | :--- | :--- | :--- |
| `temperature_2m` | `temperature_c` | °C | None |
| `dew_point_2m` | `dewpoint_c` | °C | None |
| `relative_humidity_2m` | `relative_humidity_pct` | % | None |
| `wind_speed_10m` | `wind_speed_ms` | m/s | Uses `wind_speed_unit=ms` |
| `surface_pressure` | `surface_pressure_pa` | hPa | `val * 100.0` |
| `shortwave_radiation` | `solar_radiation_wm2` | W/m² | None |
| *(Omitted)* | `thermal_radiation_wm2` | W/m² | Hardcoded to `None` |

---

## PROVIDER COMPARISON OPTIONS

| Provider | Variable | Resolution | Unit | Historical hourly? | Bhubaneswar? | API/access | Training compatibility | Recommended? |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Open-Meteo (Forecast)** | `terrestrial_radiation` | ~11km | W/m² | Yes (up to 3 months) | Yes | Free, no key | Moderate (diff models) | **Yes (for live predictions)** |
| **Open-Meteo (Archive)** | `terrestrial_radiation` | 9km (ERA5) | W/m² | Yes (decades) | Yes | Free, no key | High (matches ERA5) | **Yes (for deep history)** |
| **Copernicus CDS (ERA5)** | `strd` | 9km / 31km | J/m² | Yes (decades) | Yes | Account + Key + Wait times | Perfect | No (Too slow for live API) |
