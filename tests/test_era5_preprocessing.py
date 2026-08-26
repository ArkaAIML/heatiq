"""Focused tests for reusable ERA5 preprocessing."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import xarray as xr

from ml.preprocessing import (
    derive_canonical_weather,
    load_era5_files,
    select_nearest_point,
    validate_era5_inputs,
)


class Era5PreprocessingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dataset = _make_era5_dataset()

    def test_load_era5_files_merges_compatible_datasets(self) -> None:
        variable_groups = (
            ("t2m", "d2m"),
            ("sp",),
            ("ssrd", "strd"),
            ("u10", "v10"),
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = []
            for index, variables in enumerate(variable_groups):
                path = Path(temporary_directory) / f"era5_{index}.nc"
                self.dataset[list(variables)].to_netcdf(path)
                paths.append(path)

            loaded = load_era5_files(paths)

        self.assertEqual(set(loaded.data_vars), set(self.dataset.data_vars))
        xr.testing.assert_equal(loaded, self.dataset)

    def test_validate_era5_inputs_rejects_missing_variable(self) -> None:
        with self.assertRaisesRegex(ValueError, "v10"):
            validate_era5_inputs(self.dataset.drop_vars("v10"))

    def test_load_era5_files_rejects_incompatible_coordinates(self) -> None:
        incompatible_pressure = self.dataset[["sp"]].assign_coords(
            latitude=[20.25, 20.35]
        )
        variable_datasets = (
            self.dataset[["t2m", "d2m"]],
            incompatible_pressure,
            self.dataset[["ssrd", "strd"]],
            self.dataset[["u10", "v10"]],
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = []
            for index, dataset in enumerate(variable_datasets):
                path = Path(temporary_directory) / f"era5_{index}.nc"
                dataset.to_netcdf(path)
                paths.append(path)

            with self.assertRaisesRegex(ValueError, "incompatible coordinates"):
                load_era5_files(paths)

    def test_derive_converts_kelvin_to_celsius(self) -> None:
        canonical = derive_canonical_weather(
            self.dataset,
            radiation_accumulation_seconds=3600,
        )

        np.testing.assert_allclose(canonical["temperature_c"], 26.85)
        np.testing.assert_allclose(canonical["dewpoint_c"], 16.85)

    def test_relative_humidity_is_sane(self) -> None:
        dataset = self.dataset.copy(deep=True)
        dataset["d2m"] = dataset["t2m"].copy(deep=True)
        dataset["d2m"].attrs["units"] = "K"

        canonical = derive_canonical_weather(
            dataset,
            radiation_accumulation_seconds=3600,
        )

        np.testing.assert_allclose(canonical["relative_humidity_pct"], 100.0)

    def test_wind_speed_uses_vector_magnitude(self) -> None:
        canonical = derive_canonical_weather(
            self.dataset,
            radiation_accumulation_seconds=3600,
        )

        np.testing.assert_allclose(canonical["wind_speed_ms"], 5.0)

    def test_radiation_uses_explicit_accumulation_interval(self) -> None:
        canonical = derive_canonical_weather(
            self.dataset,
            radiation_accumulation_seconds=3600,
        )

        np.testing.assert_allclose(canonical["solar_radiation_wm2"], 1000.0)
        np.testing.assert_allclose(canonical["thermal_radiation_wm2"], 400.0)

    def test_tiny_negative_solar_value_is_clamped_without_mutating_raw(self) -> None:
        dataset = self.dataset.copy(deep=True)
        original = -4.0
        dataset["ssrd"][0, 0, 0] = original

        canonical = derive_canonical_weather(
            dataset,
            radiation_accumulation_seconds=3600,
        )

        self.assertEqual(float(canonical["solar_radiation_wm2"][0, 0, 0]), 0.0)
        self.assertEqual(float(dataset["ssrd"][0, 0, 0]), original)

    def test_canonical_output_has_variables_metadata_and_no_missing_values(self) -> None:
        canonical = derive_canonical_weather(
            self.dataset,
            radiation_accumulation_seconds=3600,
        )
        expected_variables = {
            "temperature_c",
            "dewpoint_c",
            "relative_humidity_pct",
            "wind_speed_ms",
            "surface_pressure_pa",
            "solar_radiation_wm2",
            "thermal_radiation_wm2",
        }

        self.assertEqual(set(canonical.data_vars), expected_variables)
        for variable in canonical.data_vars:
            self.assertIn("units", canonical[variable].attrs)
            self.assertIn("long_name", canonical[variable].attrs)
            self.assertFalse(bool(canonical[variable].isnull().any().item()))

    def test_select_nearest_point(self) -> None:
        selected = select_nearest_point(
            self.dataset,
            latitude=20.29,
            longitude=85.81,
        )

        self.assertAlmostEqual(float(selected.latitude.item()), 20.3)
        self.assertAlmostEqual(float(selected.longitude.item()), 85.8)
        self.assertEqual(selected["t2m"].dims, ("valid_time",))


def _make_era5_dataset() -> xr.Dataset:
    coordinates = {
        "valid_time": np.array(
            ["2026-05-01T00:00:00", "2026-05-01T01:00:00"],
            dtype="datetime64[ns]",
        ),
        "latitude": np.array([20.2, 20.3]),
        "longitude": np.array([85.8, 85.9]),
    }
    dimensions = ("valid_time", "latitude", "longitude")
    shape = (2, 2, 2)

    dataset = xr.Dataset(
        data_vars={
            "t2m": (dimensions, np.full(shape, 300.0)),
            "d2m": (dimensions, np.full(shape, 290.0)),
            "sp": (dimensions, np.full(shape, 100_000.0)),
            "ssrd": (dimensions, np.full(shape, 3_600_000.0)),
            "strd": (dimensions, np.full(shape, 1_440_000.0)),
            "u10": (dimensions, np.full(shape, 3.0)),
            "v10": (dimensions, np.full(shape, 4.0)),
        },
        coords=coordinates,
    )
    units = {
        "t2m": "K",
        "d2m": "K",
        "sp": "Pa",
        "ssrd": "J m**-2",
        "strd": "J m**-2",
        "u10": "m s**-1",
        "v10": "m s**-1",
    }
    for variable, unit in units.items():
        dataset[variable].attrs["units"] = unit

    return dataset


if __name__ == "__main__":
    unittest.main()
