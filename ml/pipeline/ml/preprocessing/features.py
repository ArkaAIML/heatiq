"""Daily weather aggregation and leakage-safe temporal features.

These features are internal to the ML component and do not define a shared
backend/ML data contract or construct a supervised-learning target.
"""

import numpy as np
import pandas as pd
import xarray as xr

from ml.preprocessing.clean import CANONICAL_WEATHER_VARIABLES


DAILY_WEATHER_COLUMNS = (
    "temperature_max_c",
    "temperature_min_c",
    "temperature_mean_c",
    "dewpoint_mean_c",
    "relative_humidity_mean_pct",
    "relative_humidity_max_pct",
    "wind_speed_mean_ms",
    "wind_speed_max_ms",
    "solar_radiation_max_wm2",
    "solar_radiation_mean_wm2",
    "thermal_radiation_mean_wm2",
    "surface_pressure_mean_pa",
)
TEMPORAL_FEATURE_COLUMNS = (
    "temperature_max_lag_1d",
    "temperature_max_lag_2d",
    "temperature_max_lag_3d",
    "temperature_min_lag_1d",
    "temperature_mean_prev_3d",
    "temperature_mean_prev_5d",
    "temperature_max_prev_3d",
    "humidity_mean_prev_3d",
)
CALENDAR_FEATURE_COLUMNS = (
    "month",
    "day_of_year",
    "day_of_year_sin",
    "day_of_year_cos",
)

_ONE_HOUR = pd.Timedelta(hours=1)


def aggregate_daily_weather(
    dataset: xr.Dataset,
    *,
    timezone: str = "Asia/Kolkata",
) -> pd.DataFrame:
    """Aggregate single-location canonical hourly weather by local day.

    ERA5 ``valid_time`` values are interpreted as UTC and converted to
    ``timezone`` before dates are assigned. Partial first or last local days
    are dropped and recorded in ``DataFrame.attrs``. Missing hours or an
    incomplete day inside the series raise ``ValueError``.
    """

    _validate_single_location_hourly(dataset)

    utc_time = pd.DatetimeIndex(dataset["valid_time"].values).tz_localize("UTC")
    try:
        local_time = utc_time.tz_convert(timezone)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid timezone: {timezone!r}") from exc

    hourly = pd.DataFrame(
        {
            variable: np.asarray(dataset[variable].values)
            for variable in CANONICAL_WEATHER_VARIABLES
        },
        index=local_time,
    )
    hourly.index.name = "local_time"
    hourly["date"] = hourly.index.normalize().tz_localize(None)

    counts = hourly.groupby("date", sort=True).size()
    incomplete_dates = [
        date
        for date, count in counts.items()
        if count != _expected_hours_for_local_date(pd.Timestamp(date), timezone)
    ]
    boundary_dates = {counts.index[0], counts.index[-1]}
    internal_incomplete = [
        date for date in incomplete_dates if date not in boundary_dates
    ]
    if internal_incomplete:
        formatted = ", ".join(date.strftime("%Y-%m-%d") for date in internal_incomplete)
        raise ValueError(f"incomplete local day inside time series: {formatted}")

    dropped_boundary_dates = [
        date for date in incomplete_dates if date in boundary_dates
    ]
    if dropped_boundary_dates:
        hourly = hourly[~hourly["date"].isin(dropped_boundary_dates)]
    if hourly.empty:
        raise ValueError("no complete local days remain after boundary-day removal")

    daily = (
        hourly.groupby("date", sort=True)
        .agg(
            temperature_max_c=("temperature_c", "max"),
            temperature_min_c=("temperature_c", "min"),
            temperature_mean_c=("temperature_c", "mean"),
            dewpoint_mean_c=("dewpoint_c", "mean"),
            relative_humidity_mean_pct=("relative_humidity_pct", "mean"),
            relative_humidity_max_pct=("relative_humidity_pct", "max"),
            wind_speed_mean_ms=("wind_speed_ms", "mean"),
            wind_speed_max_ms=("wind_speed_ms", "max"),
            solar_radiation_max_wm2=("solar_radiation_wm2", "max"),
            solar_radiation_mean_wm2=("solar_radiation_wm2", "mean"),
            thermal_radiation_mean_wm2=("thermal_radiation_wm2", "mean"),
            surface_pressure_mean_pa=("surface_pressure_pa", "mean"),
        )
        .reset_index()
    )
    daily.attrs = {
        "timezone": timezone,
        "source_hourly_rows": len(dataset["valid_time"]),
        "boundary_days_dropped": len(dropped_boundary_dates),
        "boundary_dates_dropped": [
            date.strftime("%Y-%m-%d") for date in dropped_boundary_dates
        ],
    }
    return daily


def add_daily_temporal_features(
    daily_weather: pd.DataFrame,
    *,
    drop_incomplete_history: bool = True,
) -> pd.DataFrame:
    """Add calendar and strictly prior-day lag/rolling features.

    Rolling calculations shift their source by one day before applying the
    window. Consequently, the row for day D never uses day D in a historical
    rolling feature. With ``drop_incomplete_history=True``, the first five
    rows are explicitly removed and the count is recorded in frame metadata.
    Otherwise those rows are retained with NaN history values; no values are
    imputed.
    """

    _validate_daily_weather_frame(daily_weather)
    featured = daily_weather.copy(deep=True)
    source_attrs = daily_weather.attrs.copy()

    featured["temperature_max_lag_1d"] = featured["temperature_max_c"].shift(1)
    featured["temperature_max_lag_2d"] = featured["temperature_max_c"].shift(2)
    featured["temperature_max_lag_3d"] = featured["temperature_max_c"].shift(3)
    featured["temperature_min_lag_1d"] = featured["temperature_min_c"].shift(1)

    previous_temperature_mean = featured["temperature_mean_c"].shift(1)
    previous_temperature_max = featured["temperature_max_c"].shift(1)
    previous_humidity_mean = featured["relative_humidity_mean_pct"].shift(1)
    featured["temperature_mean_prev_3d"] = previous_temperature_mean.rolling(
        window=3, min_periods=3
    ).mean()
    featured["temperature_mean_prev_5d"] = previous_temperature_mean.rolling(
        window=5, min_periods=5
    ).mean()
    featured["temperature_max_prev_3d"] = previous_temperature_max.rolling(
        window=3, min_periods=3
    ).max()
    featured["humidity_mean_prev_3d"] = previous_humidity_mean.rolling(
        window=3, min_periods=3
    ).mean()

    featured["month"] = featured["date"].dt.month.astype("int16")
    featured["day_of_year"] = featured["date"].dt.dayofyear.astype("int16")
    annual_angle = 2.0 * np.pi * (featured["day_of_year"] - 1) / 365.25
    featured["day_of_year_sin"] = np.sin(annual_angle)
    featured["day_of_year_cos"] = np.cos(annual_angle)

    incomplete_history = featured[list(TEMPORAL_FEATURE_COLUMNS)].isna().any(axis=1)
    if bool(incomplete_history.iloc[5:].any()):
        raise ValueError("unexpected missing temporal features after history window")

    rows_dropped = int(incomplete_history.sum()) if drop_incomplete_history else 0
    if drop_incomplete_history:
        featured = featured.loc[~incomplete_history].reset_index(drop=True)
        if featured.empty:
            raise ValueError("at least six complete daily rows are required")

    featured.attrs = source_attrs | {
        "history_days_required": 5,
        "rows_dropped_for_incomplete_history": rows_dropped,
        "rolling_features_include_current_day": False,
    }
    return featured


def build_daily_feature_frame(
    dataset: xr.Dataset,
    *,
    timezone: str = "Asia/Kolkata",
    drop_incomplete_history: bool = True,
) -> pd.DataFrame:
    """Aggregate hourly weather and add leakage-safe temporal features."""

    daily = aggregate_daily_weather(dataset, timezone=timezone)
    return add_daily_temporal_features(
        daily,
        drop_incomplete_history=drop_incomplete_history,
    )


def _validate_single_location_hourly(dataset: xr.Dataset) -> None:
    missing_variables = [
        variable
        for variable in CANONICAL_WEATHER_VARIABLES
        if variable not in dataset
    ]
    if missing_variables:
        raise ValueError(
            "missing canonical weather variables: " + ", ".join(missing_variables)
        )
    if "valid_time" not in dataset.coords:
        raise ValueError("dataset must contain valid_time")

    for coordinate in ("latitude", "longitude"):
        if coordinate in dataset.coords and dataset[coordinate].ndim != 0:
            raise ValueError(f"{coordinate} must be scalar for a single location")

    for variable in CANONICAL_WEATHER_VARIABLES:
        data = dataset[variable]
        if data.dims != ("valid_time",):
            raise ValueError(
                f"{variable} must have only the valid_time dimension; "
                f"received {data.dims}"
            )
        if bool(data.isnull().any().item()):
            raise ValueError(f"{variable} contains missing values")
        if not bool(np.isfinite(data).all().item()):
            raise ValueError(f"{variable} contains non-finite values")

    time_index = pd.DatetimeIndex(dataset["valid_time"].values)
    if time_index.empty:
        raise ValueError("valid_time cannot be empty")
    if time_index.tz is not None:
        raise ValueError("ERA5 valid_time must be timezone-naive UTC values")
    if not time_index.is_unique:
        raise ValueError("valid_time timestamps must be unique")
    if not time_index.is_monotonic_increasing:
        raise ValueError("valid_time timestamps must be ordered")
    if len(time_index) > 1 and not bool((time_index.to_series().diff().iloc[1:] == _ONE_HOUR).all()):
        raise ValueError("valid_time must contain uninterrupted hourly observations")


def _validate_daily_weather_frame(daily_weather: pd.DataFrame) -> None:
    required_columns = ("date", *DAILY_WEATHER_COLUMNS)
    missing_columns = [
        column for column in required_columns if column not in daily_weather.columns
    ]
    if missing_columns:
        raise ValueError("missing daily weather columns: " + ", ".join(missing_columns))
    if daily_weather.empty:
        raise ValueError("daily weather frame cannot be empty")
    if not pd.api.types.is_datetime64_any_dtype(daily_weather["date"]):
        raise ValueError("date must use a datetime64 dtype")
    if daily_weather["date"].isna().any():
        raise ValueError("date contains missing values")
    if not daily_weather["date"].is_unique:
        raise ValueError("date values must be unique")
    if not daily_weather["date"].is_monotonic_increasing:
        raise ValueError("date values must be chronological")
    if len(daily_weather) > 1:
        date_differences = daily_weather["date"].diff().iloc[1:]
        if not bool((date_differences == pd.Timedelta(days=1)).all()):
            raise ValueError("daily weather dates must be consecutive")

    values = daily_weather[list(DAILY_WEATHER_COLUMNS)]
    if values.isna().any().any():
        raise ValueError("daily weather contains missing values")
    if not bool(np.isfinite(values.to_numpy()).all()):
        raise ValueError("daily weather contains non-finite values")


def _expected_hours_for_local_date(date: pd.Timestamp, timezone: str) -> int:
    try:
        start = date.tz_localize(timezone)
        end = (date + pd.Timedelta(days=1)).tz_localize(timezone)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"cannot determine local-day duration for {timezone!r}") from exc
    return int((end.tz_convert("UTC") - start.tz_convert("UTC")) / _ONE_HOUR)
