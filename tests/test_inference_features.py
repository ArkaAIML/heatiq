"""Tests for provider-neutral inference weather construction."""

from datetime import datetime
import unittest

import numpy as np
import pandas as pd
import xarray as xr
from sklearn.linear_model import LinearRegression

from ml.inference import (
    AIR_TEMPERATURE_TARGET,
    AIR_TEMPERATURE_UNIT,
    ModelArtifact,
    ModelMetadata,
    build_inference_feature_row,
)
from ml.preprocessing import (
    PROVIDER_NEUTRAL_WEATHER_COLUMNS,
    build_canonical_weather_dataset,
    build_daily_feature_frame,
)


class CanonicalWeatherDatasetTests(unittest.TestCase):
    def setUp(self) -> None:
        timestamps = pd.date_range(
            "2026-05-01 00:00",
            periods=48,
            freq="h",
            tz="UTC",
        )
        self.weather_history = pd.DataFrame(
            {
                "timestamp": timestamps,
                "temperature_c": np.linspace(28.0, 34.0, len(timestamps)),
                "dewpoint_c": np.full(len(timestamps), 20.0),
                "relative_humidity_pct": np.full(len(timestamps), 60.0),
                "wind_speed_ms": np.full(len(timestamps), 2.0),
                "surface_pressure_pa": np.full(len(timestamps), 100_000.0),
                "solar_radiation_wm2": np.full(len(timestamps), 200.0),
                "thermal_radiation_wm2": np.full(len(timestamps), 400.0),
            }
        )

    def test_builds_valid_single_location_canonical_dataset(self) -> None:
        dataset = build_canonical_weather_dataset(
            self.weather_history,
            latitude=20.3,
            longitude=85.8,
        )

        self.assertEqual(tuple(dataset.data_vars), PROVIDER_NEUTRAL_WEATHER_COLUMNS[1:])
        self.assertEqual(dataset.sizes, {"valid_time": 48})
        self.assertEqual(float(dataset["latitude"].item()), 20.3)
        self.assertEqual(float(dataset["longitude"].item()), 85.8)
        self.assertIsNone(pd.DatetimeIndex(dataset["valid_time"].values).tz)
        self.assertEqual(dataset["temperature_c"].attrs["units"], "degC")
        self.assertEqual(
            dataset["thermal_radiation_wm2"].attrs["units"],
            "W m^-2",
        )
        self.assertTrue(dataset["temperature_c"].attrs["long_name"])

    def test_accepts_explicit_zero_offset_timestamps(self) -> None:
        history = self.weather_history.copy(deep=True)
        history["timestamp"] = history["timestamp"].map(
            lambda value: value.isoformat()
        )

        dataset = build_canonical_weather_dataset(
            history,
            latitude=20.3,
            longitude=85.8,
        )

        self.assertEqual(dataset.sizes["valid_time"], len(history))

    def test_rejects_invalid_schema(self) -> None:
        cases = {
            "missing": self.weather_history.drop(columns="thermal_radiation_wm2"),
            "unexpected": self.weather_history.assign(provider="example"),
        }
        for name, history in cases.items():
            with self.subTest(name=name), self.assertRaisesRegex(
                ValueError,
                "provider-neutral schema",
            ):
                build_canonical_weather_dataset(
                    history,
                    latitude=20.3,
                    longitude=85.8,
                )

    def test_rejects_invalid_timestamps(self) -> None:
        duplicate = self.weather_history.copy(deep=True)
        duplicate.loc[1, "timestamp"] = duplicate.loc[0, "timestamp"]
        unordered = self.weather_history.iloc[::-1].reset_index(drop=True)
        interrupted = self.weather_history.drop(index=10).reset_index(drop=True)
        naive = self.weather_history.copy(deep=True)
        naive["timestamp"] = naive["timestamp"].dt.tz_localize(None)
        non_utc = self.weather_history.copy(deep=True)
        non_utc["timestamp"] = non_utc["timestamp"].dt.tz_convert("Asia/Kolkata")

        cases = {
            "duplicate": (duplicate, "unique"),
            "unordered": (unordered, "ordered"),
            "interrupted": (interrupted, "uninterrupted hourly"),
            "naive": (naive, "timezone-aware UTC"),
            "non_utc": (non_utc, "UTC values"),
        }
        for name, (history, message) in cases.items():
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, message):
                build_canonical_weather_dataset(
                    history,
                    latitude=20.3,
                    longitude=85.8,
                )

    def test_rejects_nonnumeric_missing_and_nonfinite_weather_values(self) -> None:
        cases = {
            "nonnumeric": self.weather_history.assign(temperature_c="hot"),
            "boolean": self.weather_history.assign(wind_speed_ms=True),
            "missing": self.weather_history.assign(dewpoint_c=np.nan),
            "infinite": self.weather_history.assign(surface_pressure_pa=np.inf),
        }
        for name, history in cases.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                build_canonical_weather_dataset(
                    history,
                    latitude=20.3,
                    longitude=85.8,
                )

    def test_reuses_canonical_physics_and_range_validation(self) -> None:
        invalid = self.weather_history.assign(relative_humidity_pct=101.0)

        with self.assertRaisesRegex(ValueError, "relative_humidity_pct is above"):
            build_canonical_weather_dataset(
                invalid,
                latitude=20.3,
                longitude=85.8,
            )

    def test_rejects_invalid_coordinates(self) -> None:
        cases = (
            (True, 85.8),
            (np.nan, 85.8),
            (91.0, 85.8),
            (20.3, np.inf),
            (20.3, 181.0),
        )
        for latitude, longitude in cases:
            with self.subTest(latitude=latitude, longitude=longitude), self.assertRaises(
                (TypeError, ValueError)
            ):
                build_canonical_weather_dataset(
                    self.weather_history,
                    latitude=latitude,
                    longitude=longitude,
                )

    def test_does_not_mutate_input_dataframe(self) -> None:
        original = self.weather_history.copy(deep=True)

        build_canonical_weather_dataset(
            self.weather_history,
            latitude=20.3,
            longitude=85.8,
        )

        pd.testing.assert_frame_equal(self.weather_history, original)

    def test_rejects_invalid_input_type_and_empty_dataframe(self) -> None:
        with self.assertRaisesRegex(TypeError, "pandas DataFrame"):
            build_canonical_weather_dataset(  # type: ignore[arg-type]
                [],
                latitude=20.3,
                longitude=85.8,
            )
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            build_canonical_weather_dataset(
                pd.DataFrame(columns=PROVIDER_NEUTRAL_WEATHER_COLUMNS),
                latitude=20.3,
                longitude=85.8,
            )


class InferenceFeatureRowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.weather_history = _make_weather_history(days=7)
        self.training_features = _training_style_features(self.weather_history)
        self.artifact = _make_artifact(self.training_features)

    def test_selects_explicit_feature_date_and_preserves_it(self) -> None:
        feature_row = build_inference_feature_row(
            self.weather_history,
            artifact=self.artifact,
            latitude=20.3,
            longitude=85.8,
            feature_date="2026-05-06",
        )

        self.assertEqual(len(feature_row), 1)
        self.assertEqual(feature_row.index.name, "feature_date")
        self.assertEqual(feature_row.index[0], pd.Timestamp("2026-05-06"))
        self.assertEqual(
            feature_row.attrs["feature_date"],
            pd.Timestamp("2026-05-06"),
        )
        self.assertNotIn("date", feature_row.columns)
        expected = self.training_features.loc[
            self.training_features["date"] == pd.Timestamp("2026-05-06"),
            list(self.artifact.metadata.feature_names),
        ]
        pd.testing.assert_frame_equal(
            feature_row.reset_index(drop=True),
            expected.reset_index(drop=True),
        )

    def test_training_and_serving_paths_produce_identical_24_features(self) -> None:
        canonical = _make_existing_canonical_dataset(self.weather_history)
        training_frame = build_daily_feature_frame(canonical)
        artifact = _make_artifact(training_frame)
        expected = training_frame.iloc[[-1]].drop(columns="date")

        actual = build_inference_feature_row(
            self.weather_history,
            artifact=artifact,
            latitude=20.3,
            longitude=85.8,
        )

        self.assertEqual(len(artifact.metadata.feature_names), 24)
        self.assertEqual(tuple(actual.columns), artifact.metadata.feature_names)
        self.assertEqual(tuple(expected.columns), artifact.metadata.feature_names)
        np.testing.assert_allclose(
            actual.to_numpy(),
            expected.to_numpy(),
            rtol=0.0,
            atol=1e-12,
        )

    def test_uses_artifact_metadata_as_authoritative_order(self) -> None:
        reversed_features = tuple(
            reversed(tuple(self.training_features.columns.drop("date")))
        )
        artifact = _make_artifact(
            self.training_features,
            feature_names=reversed_features,
        )

        feature_row = build_inference_feature_row(
            self.weather_history,
            artifact=artifact,
            latitude=20.3,
            longitude=85.8,
        )

        self.assertEqual(tuple(feature_row.columns), reversed_features)

    def test_rejects_unavailable_feature_date(self) -> None:
        for unavailable in ("2026-05-05", "2026-05-08"):
            with self.subTest(unavailable=unavailable), self.assertRaisesRegex(
                ValueError,
                "not available as a complete feature row",
            ):
                build_inference_feature_row(
                    self.weather_history,
                    artifact=self.artifact,
                    latitude=20.3,
                    longitude=85.8,
                    feature_date=unavailable,
                )

    def test_rejects_insufficient_complete_history(self) -> None:
        insufficient = _make_weather_history(days=5)

        with self.assertRaisesRegex(
            ValueError,
            "at least six complete daily rows",
        ):
            build_inference_feature_row(
                insufficient,
                artifact=self.artifact,
                latitude=20.3,
                longitude=85.8,
            )

    def test_rejects_incomplete_internal_local_day(self) -> None:
        incomplete = self.weather_history.drop(index=72).reset_index(drop=True)

        with self.assertRaisesRegex(ValueError, "uninterrupted hourly"):
            build_inference_feature_row(
                incomplete,
                artifact=self.artifact,
                latitude=20.3,
                longitude=85.8,
            )

    def test_latest_selection_ignores_partial_trailing_local_day(self) -> None:
        history_with_partial_day = _make_weather_history(
            days=7,
            trailing_partial_hours=6,
        )

        feature_row = build_inference_feature_row(
            history_with_partial_day,
            artifact=self.artifact,
            latitude=20.3,
            longitude=85.8,
        )

        self.assertEqual(feature_row.index[0], pd.Timestamp("2026-05-07"))

    def test_rejects_artifact_feature_schema_mismatch(self) -> None:
        feature_names = tuple(self.training_features.columns.drop("date"))[:-1]
        mismatched_artifact = _make_artifact(
            self.training_features,
            feature_names=feature_names,
        )

        with self.assertRaisesRegex(
            ValueError,
            "engineered features do not match artifact metadata",
        ):
            build_inference_feature_row(
                self.weather_history,
                artifact=mismatched_artifact,
                latitude=20.3,
                longitude=85.8,
            )

    def test_row_is_accepted_directly_by_model_artifact(self) -> None:
        feature_row = build_inference_feature_row(
            self.weather_history,
            artifact=self.artifact,
            latitude=20.3,
            longitude=85.8,
        )

        result = self.artifact.predict_one(
            feature_row,
            feature_date=feature_row.index[0].to_pydatetime(),
        )

        self.assertTrue(np.isfinite(result.prediction))
        self.assertEqual(result.feature_date, datetime(2026, 5, 7))
        self.assertEqual(result.target_name, AIR_TEMPERATURE_TARGET)
        self.assertEqual(result.target_unit, AIR_TEMPERATURE_UNIT)

    def test_serving_path_normalizes_utc_strings_without_mutating_input(self) -> None:
        history = self.weather_history.copy(deep=True)
        history["timestamp"] = history["timestamp"].map(
            lambda value: value.isoformat()
        )
        original = history.copy(deep=True)

        feature_row = build_inference_feature_row(
            history,
            artifact=self.artifact,
            latitude=20.3,
            longitude=85.8,
        )

        self.assertEqual(feature_row.index[0], pd.Timestamp("2026-05-07"))
        pd.testing.assert_frame_equal(history, original)


def _make_weather_history(
    *,
    days: int,
    trailing_partial_hours: int = 0,
) -> pd.DataFrame:
    timestamps = pd.date_range(
        "2026-04-30 18:30",
        periods=days * 24 + trailing_partial_hours,
        freq="h",
        tz="UTC",
    )
    local_time = timestamps.tz_convert("Asia/Kolkata")
    elapsed_days = (
        local_time.normalize() - local_time[0].normalize()
    ).days.to_numpy(dtype=float)
    local_hour = local_time.hour.to_numpy(dtype=float)
    size = len(timestamps)
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "temperature_c": 28.0 + elapsed_days + local_hour / 100.0,
            "dewpoint_c": np.full(size, 20.0),
            "relative_humidity_pct": np.full(size, 60.0),
            "wind_speed_ms": np.full(size, 2.0),
            "surface_pressure_pa": np.full(size, 100_000.0),
            "solar_radiation_wm2": local_hour * 10.0,
            "thermal_radiation_wm2": np.full(size, 400.0),
        }
    )


def _training_style_features(weather_history: pd.DataFrame) -> pd.DataFrame:
    canonical = build_canonical_weather_dataset(
        weather_history,
        latitude=20.3,
        longitude=85.8,
    )
    return build_daily_feature_frame(canonical)


def _make_existing_canonical_dataset(weather_history: pd.DataFrame) -> xr.Dataset:
    valid_time = pd.DatetimeIndex(weather_history["timestamp"]).tz_convert("UTC")
    dataset = xr.Dataset(
        data_vars={
            variable: (
                ("valid_time",),
                weather_history[variable].to_numpy(dtype=float, copy=True),
            )
            for variable in PROVIDER_NEUTRAL_WEATHER_COLUMNS[1:]
        },
        coords={
            "valid_time": valid_time.tz_localize(None).to_numpy(),
            "latitude": 20.3,
            "longitude": 85.8,
        },
    )
    units = {
        "temperature_c": "degC",
        "dewpoint_c": "degC",
        "relative_humidity_pct": "%",
        "wind_speed_ms": "m s^-1",
        "surface_pressure_pa": "Pa",
        "solar_radiation_wm2": "W m^-2",
        "thermal_radiation_wm2": "W m^-2",
    }
    for variable, unit in units.items():
        dataset[variable].attrs = {
            "long_name": variable,
            "units": unit,
        }
    return dataset


def _make_artifact(
    training_frame: pd.DataFrame,
    *,
    feature_names: tuple[str, ...] | None = None,
) -> ModelArtifact:
    if feature_names is None:
        feature_names = tuple(training_frame.columns.drop("date"))
    features = training_frame.loc[:, list(feature_names)]
    target = pd.Series(np.arange(len(features), dtype=float))
    estimator = LinearRegression().fit(features, target)
    metadata = ModelMetadata(
        model_name="linear_regression",
        feature_names=feature_names,
        forecast_horizon_days=1,
        target_name=AIR_TEMPERATURE_TARGET,
        target_unit=AIR_TEMPERATURE_UNIT,
    )
    return ModelArtifact(estimator, metadata, model_version="v1")


if __name__ == "__main__":
    unittest.main()
