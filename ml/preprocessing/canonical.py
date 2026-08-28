"""Provider-neutral construction of ML-internal canonical weather data."""

from datetime import timedelta

import numpy as np
import pandas as pd
import xarray as xr

from ml.preprocessing.clean import validate_canonical_weather


PROVIDER_NEUTRAL_WEATHER_COLUMNS = (
    "timestamp",
    "temperature_c",
    "dewpoint_c",
    "relative_humidity_pct",
    "wind_speed_ms",
    "surface_pressure_pa",
    "solar_radiation_wm2",
    "thermal_radiation_wm2",
)

_WEATHER_VARIABLE_METADATA = {
    "temperature_c": ("2 metre air temperature", "degC"),
    "dewpoint_c": ("2 metre dewpoint temperature", "degC"),
    "relative_humidity_pct": ("relative humidity", "%"),
    "wind_speed_ms": ("10 metre wind speed", "m s^-1"),
    "surface_pressure_pa": ("surface pressure", "Pa"),
    "solar_radiation_wm2": (
        "surface solar radiation downward mean flux",
        "W m^-2",
    ),
    "thermal_radiation_wm2": (
        "surface thermal radiation downward mean flux",
        "W m^-2",
    ),
}
_ONE_HOUR = pd.Timedelta(hours=1)


def build_canonical_weather_dataset(
    weather_history: pd.DataFrame,
    *,
    latitude: float,
    longitude: float,
) -> xr.Dataset:
    """Build single-location canonical weather from provider-neutral input.

    Input timestamps must be timezone-aware UTC observations at uninterrupted
    hourly intervals. Weather values must already use the canonical units
    documented by ``PROVIDER_NEUTRAL_WEATHER_COLUMNS``; no unit conversion or
    missing-value imputation is performed.
    """

    if not isinstance(weather_history, pd.DataFrame):
        raise TypeError("weather_history must be a pandas DataFrame")
    if weather_history.empty:
        raise ValueError("weather_history cannot be empty")

    actual_columns = tuple(weather_history.columns)
    missing_columns = [
        column
        for column in PROVIDER_NEUTRAL_WEATHER_COLUMNS
        if column not in actual_columns
    ]
    unexpected_columns = [
        column
        for column in actual_columns
        if column not in PROVIDER_NEUTRAL_WEATHER_COLUMNS
    ]
    if missing_columns or unexpected_columns or len(actual_columns) != len(
        PROVIDER_NEUTRAL_WEATHER_COLUMNS
    ):
        raise ValueError(
            "weather_history columns must match the provider-neutral schema; "
            f"missing={missing_columns}, unexpected={unexpected_columns}"
        )

    validated_latitude = _validated_coordinate(latitude, "latitude", -90.0, 90.0)
    validated_longitude = _validated_coordinate(
        longitude,
        "longitude",
        -180.0,
        180.0,
    )
    valid_time = _validated_utc_hourly_timestamps(weather_history["timestamp"])

    weather_values: dict[str, np.ndarray] = {}
    for variable in PROVIDER_NEUTRAL_WEATHER_COLUMNS[1:]:
        series = weather_history[variable]
        if not pd.api.types.is_numeric_dtype(series) or pd.api.types.is_bool_dtype(
            series
        ):
            raise ValueError(f"{variable} must contain numeric values")
        values = series.to_numpy(dtype=float, copy=True)
        if not bool(np.isfinite(values).all()):
            raise ValueError(f"{variable} must contain finite, non-missing values")
        weather_values[variable] = values

    canonical_grid = xr.Dataset(
        data_vars={
            variable: (
                ("valid_time", "latitude", "longitude"),
                values[:, np.newaxis, np.newaxis],
            )
            for variable, values in weather_values.items()
        },
        coords={
            "valid_time": valid_time.tz_localize(None).to_numpy(),
            "latitude": np.array([validated_latitude]),
            "longitude": np.array([validated_longitude]),
        },
    )
    for variable, (long_name, units) in _WEATHER_VARIABLE_METADATA.items():
        canonical_grid[variable].attrs = {
            "long_name": long_name,
            "units": units,
        }

    validate_canonical_weather(canonical_grid)
    return canonical_grid.sel(
        latitude=validated_latitude,
        longitude=validated_longitude,
    )


def _validated_coordinate(
    value: object,
    name: str,
    minimum: float,
    maximum: float,
) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    numeric_value = float(value)
    if not np.isfinite(numeric_value):
        raise ValueError(f"{name} must be finite")
    if not minimum <= numeric_value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return numeric_value


def _validated_utc_hourly_timestamps(timestamp: pd.Series) -> pd.DatetimeIndex:
    try:
        valid_time = pd.DatetimeIndex(pd.to_datetime(timestamp, errors="raise"))
    except (TypeError, ValueError) as exc:
        raise ValueError("timestamp must contain valid datetime values") from exc

    if valid_time.isna().any():
        raise ValueError("timestamp contains missing values")
    if valid_time.tz is None:
        raise ValueError("timestamp must contain timezone-aware UTC values")
    if any(value.utcoffset() != timedelta(0) for value in valid_time):
        raise ValueError("timestamp must contain UTC values")

    valid_time = valid_time.tz_convert("UTC")
    if not valid_time.is_unique:
        raise ValueError("timestamp values must be unique")
    if not valid_time.is_monotonic_increasing:
        raise ValueError("timestamp values must be ordered")
    if len(valid_time) > 1:
        differences = valid_time.to_series().diff().iloc[1:]
        if not bool((differences == _ONE_HOUR).all()):
            raise ValueError(
                "timestamp must contain uninterrupted hourly observations"
            )
    return valid_time
