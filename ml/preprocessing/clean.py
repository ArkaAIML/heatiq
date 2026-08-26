"""Reusable preprocessing utilities for ERA5-Land weather data.

The canonical dataset produced here is internal to the ML component. It is
not a backend payload or a shared backend/ML schema.
"""

from collections.abc import Iterable
from pathlib import Path

import numpy as np
import xarray as xr


REQUIRED_ERA5_VARIABLES = (
    "t2m",
    "d2m",
    "sp",
    "ssrd",
    "strd",
    "u10",
    "v10",
)
REQUIRED_COORDINATES = ("valid_time", "latitude", "longitude")
CANONICAL_WEATHER_VARIABLES = (
    "temperature_c",
    "dewpoint_c",
    "relative_humidity_pct",
    "wind_speed_ms",
    "surface_pressure_pa",
    "solar_radiation_wm2",
    "thermal_radiation_wm2",
)

_EXPECTED_RAW_UNITS = {
    "t2m": {"k", "kelvin"},
    "d2m": {"k", "kelvin"},
    "sp": {"pa", "pascal", "pascals"},
    "ssrd": {"jm**-2", "jm^-2", "j/m^2", "jm-2"},
    "strd": {"jm**-2", "jm^-2", "j/m^2", "jm-2"},
    "u10": {"ms**-1", "ms^-1", "m/s", "ms-1"},
    "v10": {"ms**-1", "ms^-1", "m/s", "ms-1"},
}
_CANONICAL_UNITS = {
    "temperature_c": "degC",
    "dewpoint_c": "degC",
    "relative_humidity_pct": "%",
    "wind_speed_ms": "m s^-1",
    "surface_pressure_pa": "Pa",
    "solar_radiation_wm2": "W m^-2",
    "thermal_radiation_wm2": "W m^-2",
}


def load_era5_files(paths: Iterable[str | Path]) -> xr.Dataset:
    """Load and exactly merge compatible ERA5 NetCDF files into memory.

    Loading before closing the files keeps the returned dataset independent
    from file handles. This is suitable for the small MVP datasets currently
    used by HeatIQ; larger datasets may later need chunked processing.
    """

    if isinstance(paths, (str, Path)):
        raise TypeError("paths must be an iterable of NetCDF file paths")

    resolved_paths = [Path(path) for path in paths]
    if not resolved_paths:
        raise ValueError("at least one ERA5 NetCDF file is required")
    if len(set(resolved_paths)) != len(resolved_paths):
        raise ValueError("duplicate ERA5 file paths are not allowed")

    for path in resolved_paths:
        if not path.is_file():
            raise FileNotFoundError(f"ERA5 file does not exist: {path}")
        if path.suffix.lower() != ".nc":
            raise ValueError(f"ERA5 input must be a .nc file: {path}")

    loaded_datasets: list[xr.Dataset] = []
    for path in resolved_paths:
        with xr.open_dataset(path) as dataset:
            loaded_datasets.append(dataset.load())

    try:
        aligned = xr.align(*loaded_datasets, join="exact", copy=False)
        merged = xr.merge(aligned, join="exact", compat="no_conflicts")
    except (ValueError, xr.AlignmentError) as exc:
        raise ValueError(f"ERA5 files have incompatible coordinates: {exc}") from exc

    validate_era5_inputs(merged)
    return merged


def validate_era5_inputs(dataset: xr.Dataset) -> None:
    """Validate variables, dimensions, units, values, and time ordering."""

    missing_variables = [
        variable for variable in REQUIRED_ERA5_VARIABLES if variable not in dataset
    ]
    if missing_variables:
        raise ValueError(
            "missing required ERA5 variables: " + ", ".join(missing_variables)
        )

    missing_coordinates = [
        coordinate
        for coordinate in REQUIRED_COORDINATES
        if coordinate not in dataset.coords
    ]
    if missing_coordinates:
        raise ValueError(
            "missing required ERA5 coordinates: " + ", ".join(missing_coordinates)
        )

    required_dimensions = set(REQUIRED_COORDINATES)
    for variable in REQUIRED_ERA5_VARIABLES:
        data = dataset[variable]
        if set(data.dims) != required_dimensions:
            raise ValueError(
                f"{variable} must have dimensions {REQUIRED_COORDINATES}; "
                f"received {data.dims}"
            )

        unit = data.attrs.get("units")
        if unit is None:
            raise ValueError(f"{variable} is missing units metadata")
        if _normalize_unit(unit) not in _EXPECTED_RAW_UNITS[variable]:
            raise ValueError(f"{variable} has unsupported units: {unit!r}")

        _validate_finite_and_complete(data, variable)

    _validate_time_coordinate(dataset)


def derive_canonical_weather(
    dataset: xr.Dataset,
    *,
    radiation_accumulation_seconds: float,
    solar_negative_tolerance_wm2: float = 0.01,
) -> xr.Dataset:
    """Derive the ML-internal canonical weather variables from ERA5 data.

    ERA5 radiation fields are accumulated energy. The caller must explicitly
    provide the accumulation interval so that the conversion to mean flux is
    not based on an implicit hourly assumption.
    """

    validate_era5_inputs(dataset)

    if not np.isfinite(radiation_accumulation_seconds):
        raise ValueError("radiation_accumulation_seconds must be finite")
    if radiation_accumulation_seconds <= 0:
        raise ValueError("radiation_accumulation_seconds must be greater than zero")
    if not np.isfinite(solar_negative_tolerance_wm2):
        raise ValueError("solar_negative_tolerance_wm2 must be finite")
    if solar_negative_tolerance_wm2 < 0:
        raise ValueError("solar_negative_tolerance_wm2 cannot be negative")

    temperature_c = dataset["t2m"] - 273.15
    dewpoint_c = dataset["d2m"] - 273.15
    wind_speed_ms = np.hypot(dataset["u10"], dataset["v10"])

    relative_humidity_pct = 100.0 * np.exp(
        (17.625 * dewpoint_c) / (243.04 + dewpoint_c)
        - (17.625 * temperature_c) / (243.04 + temperature_c)
    )

    solar_radiation_wm2 = dataset["ssrd"] / radiation_accumulation_seconds
    if bool((solar_radiation_wm2 < -solar_negative_tolerance_wm2).any().item()):
        minimum = float(solar_radiation_wm2.min().item())
        raise ValueError(
            "solar radiation contains values below the permitted cleaning "
            f"tolerance: minimum={minimum} W m^-2"
        )
    solar_radiation_wm2 = solar_radiation_wm2.clip(min=0.0)

    canonical = xr.Dataset(
        data_vars={
            "temperature_c": temperature_c,
            "dewpoint_c": dewpoint_c,
            "relative_humidity_pct": relative_humidity_pct,
            "wind_speed_ms": wind_speed_ms,
            "surface_pressure_pa": dataset["sp"].copy(deep=False),
            "solar_radiation_wm2": solar_radiation_wm2,
            "thermal_radiation_wm2": (
                dataset["strd"] / radiation_accumulation_seconds
            ),
        },
        attrs=dataset.attrs.copy(),
    )

    long_names = {
        "temperature_c": "2 metre air temperature",
        "dewpoint_c": "2 metre dewpoint temperature",
        "relative_humidity_pct": "relative humidity",
        "wind_speed_ms": "10 metre wind speed",
        "surface_pressure_pa": "surface pressure",
        "solar_radiation_wm2": "surface solar radiation downward mean flux",
        "thermal_radiation_wm2": "surface thermal radiation downward mean flux",
    }
    for variable in CANONICAL_WEATHER_VARIABLES:
        canonical[variable].attrs = {
            "long_name": long_names[variable],
            "units": _CANONICAL_UNITS[variable],
        }

    validate_canonical_weather(canonical)
    return canonical


def validate_canonical_weather(dataset: xr.Dataset) -> None:
    """Validate the ML-internal canonical weather dataset."""

    missing_variables = [
        variable
        for variable in CANONICAL_WEATHER_VARIABLES
        if variable not in dataset
    ]
    if missing_variables:
        raise ValueError(
            "missing canonical weather variables: " + ", ".join(missing_variables)
        )

    missing_coordinates = [
        coordinate
        for coordinate in REQUIRED_COORDINATES
        if coordinate not in dataset.coords
    ]
    if missing_coordinates:
        raise ValueError(
            "missing canonical weather coordinates: " + ", ".join(missing_coordinates)
        )

    required_dimensions = set(REQUIRED_COORDINATES)
    for variable in CANONICAL_WEATHER_VARIABLES:
        data = dataset[variable]
        if set(data.dims) != required_dimensions:
            raise ValueError(
                f"{variable} must have dimensions {REQUIRED_COORDINATES}; "
                f"received {data.dims}"
            )
        if data.attrs.get("units") != _CANONICAL_UNITS[variable]:
            raise ValueError(f"{variable} has missing or incorrect units metadata")
        if not data.attrs.get("long_name"):
            raise ValueError(f"{variable} is missing long_name metadata")
        _validate_finite_and_complete(data, variable)

    _validate_time_coordinate(dataset)
    _validate_range(dataset["temperature_c"], "temperature_c", -100.0, 70.0)
    _validate_range(dataset["dewpoint_c"], "dewpoint_c", -120.0, 60.0)
    _validate_range(
        dataset["relative_humidity_pct"],
        "relative_humidity_pct",
        -1e-6,
        100.0 + 1e-6,
    )
    _validate_range(dataset["wind_speed_ms"], "wind_speed_ms", 0.0, None)
    _validate_range(
        dataset["surface_pressure_pa"],
        "surface_pressure_pa",
        30_000.0,
        110_000.0,
    )
    _validate_range(
        dataset["solar_radiation_wm2"], "solar_radiation_wm2", 0.0, None
    )
    _validate_range(
        dataset["thermal_radiation_wm2"], "thermal_radiation_wm2", 0.0, None
    )

    if bool(
        (dataset["dewpoint_c"] > dataset["temperature_c"] + 0.1).any().item()
    ):
        raise ValueError("dewpoint_c cannot materially exceed temperature_c")


def select_nearest_point(
    dataset: xr.Dataset,
    *,
    latitude: float,
    longitude: float,
    max_distance_degrees: float | None = None,
) -> xr.Dataset:
    """Select the grid point nearest to the requested coordinates."""

    if not np.isfinite(latitude) or not np.isfinite(longitude):
        raise ValueError("latitude and longitude must be finite")
    if "latitude" not in dataset.coords or "longitude" not in dataset.coords:
        raise ValueError("dataset must contain latitude and longitude coordinates")
    if max_distance_degrees is not None:
        if not np.isfinite(max_distance_degrees) or max_distance_degrees < 0:
            raise ValueError("max_distance_degrees must be finite and nonnegative")

    selected = dataset.sel(
        latitude=latitude,
        longitude=longitude,
        method="nearest",
    )

    if max_distance_degrees is not None:
        selected_latitude = float(selected["latitude"].item())
        selected_longitude = float(selected["longitude"].item())
        distance = float(
            np.hypot(selected_latitude - latitude, selected_longitude - longitude)
        )
        if distance > max_distance_degrees:
            raise ValueError(
                "nearest grid point exceeds max_distance_degrees: "
                f"distance={distance}"
            )

    return selected


def _normalize_unit(unit: object) -> str:
    return str(unit).strip().lower().replace(" ", "")


def _validate_finite_and_complete(data: xr.DataArray, name: str) -> None:
    if bool(data.isnull().any().item()):
        raise ValueError(f"{name} contains missing values")
    if not bool(np.isfinite(data).all().item()):
        raise ValueError(f"{name} contains non-finite values")


def _validate_time_coordinate(dataset: xr.Dataset) -> None:
    time_index = dataset.indexes.get("valid_time")
    if time_index is None:
        raise ValueError("valid_time must be an indexed coordinate")
    if not time_index.is_unique:
        raise ValueError("valid_time timestamps must be unique")
    if not time_index.is_monotonic_increasing:
        raise ValueError("valid_time timestamps must be ordered")


def _validate_range(
    data: xr.DataArray,
    name: str,
    minimum: float | None,
    maximum: float | None,
) -> None:
    observed_minimum = float(data.min().item())
    observed_maximum = float(data.max().item())
    if minimum is not None and observed_minimum < minimum:
        raise ValueError(f"{name} is below {minimum}: {observed_minimum}")
    if maximum is not None and observed_maximum > maximum:
        raise ValueError(f"{name} is above {maximum}: {observed_maximum}")
