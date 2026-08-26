"""Tests for local-day aggregation and leakage-safe temporal features."""

import unittest

import numpy as np
import pandas as pd
import xarray as xr

from ml.preprocessing import (
    add_daily_temporal_features,
    aggregate_daily_weather,
    build_daily_feature_frame,
)


class DailyFeatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dataset = _make_complete_local_day_dataset(days=10)
        self.daily = aggregate_daily_weather(self.dataset)

    def test_daily_aggregation(self) -> None:
        first = self.daily.iloc[0]

        self.assertEqual(len(self.daily), 10)
        self.assertEqual(first["date"], pd.Timestamp("2026-05-01"))
        self.assertAlmostEqual(first["temperature_min_c"], 20.0)
        self.assertAlmostEqual(first["temperature_max_c"], 20.23)
        self.assertAlmostEqual(first["temperature_mean_c"], 20.115)
        self.assertAlmostEqual(first["dewpoint_mean_c"], 15.0)
        self.assertAlmostEqual(first["relative_humidity_mean_pct"], 60.0)
        self.assertAlmostEqual(first["relative_humidity_max_pct"], 60.0)
        self.assertAlmostEqual(first["wind_speed_mean_ms"], 2.0)
        self.assertAlmostEqual(first["wind_speed_max_ms"], 2.0)
        self.assertAlmostEqual(first["solar_radiation_max_wm2"], 230.0)
        self.assertAlmostEqual(first["solar_radiation_mean_wm2"], 115.0)
        self.assertAlmostEqual(first["thermal_radiation_mean_wm2"], 400.0)
        self.assertAlmostEqual(first["surface_pressure_mean_pa"], 100_000.0)

    def test_utc_times_are_grouped_by_local_timezone(self) -> None:
        utc_boundary_dataset = _make_utc_boundary_dataset()

        daily = aggregate_daily_weather(
            utc_boundary_dataset,
            timezone="Asia/Kolkata",
        )

        self.assertEqual(daily["date"].tolist(), [pd.Timestamp("2026-05-02")])
        self.assertEqual(daily.attrs["boundary_days_dropped"], 2)
        self.assertEqual(
            daily.attrs["boundary_dates_dropped"],
            ["2026-05-01", "2026-05-03"],
        )

    def test_internal_incomplete_day_is_rejected(self) -> None:
        incomplete = self.dataset.isel(valid_time=np.arange(len(self.dataset.valid_time)) != 30)

        with self.assertRaisesRegex(ValueError, "uninterrupted hourly"):
            aggregate_daily_weather(incomplete)

    def test_lags_use_prior_days(self) -> None:
        featured = add_daily_temporal_features(
            self.daily,
            drop_incomplete_history=False,
        )

        self.assertAlmostEqual(
            featured.loc[3, "temperature_max_lag_1d"],
            self.daily.loc[2, "temperature_max_c"],
        )
        self.assertAlmostEqual(
            featured.loc[3, "temperature_max_lag_2d"],
            self.daily.loc[1, "temperature_max_c"],
        )
        self.assertAlmostEqual(
            featured.loc[3, "temperature_max_lag_3d"],
            self.daily.loc[0, "temperature_max_c"],
        )
        self.assertAlmostEqual(
            featured.loc[3, "temperature_min_lag_1d"],
            self.daily.loc[2, "temperature_min_c"],
        )

    def test_three_day_rolling_values_use_previous_days(self) -> None:
        featured = add_daily_temporal_features(
            self.daily,
            drop_incomplete_history=False,
        )

        self.assertAlmostEqual(
            featured.loc[3, "temperature_mean_prev_3d"],
            self.daily.loc[0:2, "temperature_mean_c"].mean(),
        )
        self.assertAlmostEqual(
            featured.loc[3, "temperature_max_prev_3d"],
            self.daily.loc[0:2, "temperature_max_c"].max(),
        )
        self.assertAlmostEqual(
            featured.loc[3, "humidity_mean_prev_3d"],
            self.daily.loc[0:2, "relative_humidity_mean_pct"].mean(),
        )

    def test_five_day_rolling_and_history_filter(self) -> None:
        featured = add_daily_temporal_features(self.daily)

        self.assertEqual(len(featured), 5)
        self.assertEqual(featured.iloc[0]["date"], self.daily.iloc[5]["date"])
        self.assertAlmostEqual(
            featured.iloc[0]["temperature_mean_prev_5d"],
            self.daily.loc[0:4, "temperature_mean_c"].mean(),
        )
        self.assertEqual(featured.attrs["history_days_required"], 5)
        self.assertEqual(featured.attrs["rows_dropped_for_incomplete_history"], 5)
        self.assertFalse(featured.attrs["rolling_features_include_current_day"])

    def test_current_day_outlier_does_not_leak_into_rolling_features(self) -> None:
        daily = self.daily.copy(deep=True)
        daily.loc[5, "temperature_mean_c"] = 1_000.0
        daily.loc[5, "temperature_max_c"] = 1_000.0

        featured = add_daily_temporal_features(
            daily,
            drop_incomplete_history=False,
        )

        self.assertAlmostEqual(
            featured.loc[5, "temperature_mean_prev_3d"],
            self.daily.loc[2:4, "temperature_mean_c"].mean(),
        )
        self.assertAlmostEqual(
            featured.loc[5, "temperature_max_prev_3d"],
            self.daily.loc[2:4, "temperature_max_c"].max(),
        )

    def test_calendar_and_cyclical_features(self) -> None:
        featured = add_daily_temporal_features(
            self.daily,
            drop_incomplete_history=False,
        )
        first = featured.iloc[0]
        expected_angle = 2.0 * np.pi * (first["day_of_year"] - 1) / 365.25

        self.assertEqual(first["month"], 5)
        self.assertEqual(first["day_of_year"], 121)
        self.assertAlmostEqual(first["day_of_year_sin"], np.sin(expected_angle))
        self.assertAlmostEqual(first["day_of_year_cos"], np.cos(expected_angle))

    def test_inputs_are_not_mutated(self) -> None:
        original_dataset = self.dataset.copy(deep=True)
        original_daily = self.daily.copy(deep=True)

        aggregate_daily_weather(self.dataset)
        add_daily_temporal_features(self.daily)

        xr.testing.assert_identical(self.dataset, original_dataset)
        pd.testing.assert_frame_equal(self.daily, original_daily)

    def test_convenience_wrapper_matches_two_step_pipeline(self) -> None:
        expected = add_daily_temporal_features(aggregate_daily_weather(self.dataset))

        actual = build_daily_feature_frame(self.dataset)

        pd.testing.assert_frame_equal(actual, expected)
        self.assertEqual(actual.attrs, expected.attrs)


def _make_complete_local_day_dataset(days: int) -> xr.Dataset:
    utc_time = pd.date_range(
        "2026-04-30 18:30",
        periods=days * 24,
        freq="h",
        tz="UTC",
    )
    local_time = utc_time.tz_convert("Asia/Kolkata")
    local_day = np.repeat(np.arange(days, dtype=float), 24)
    local_hour = local_time.hour.to_numpy(dtype=float)
    temperature = 20.0 + local_day + local_hour / 100.0

    values = {
        "temperature_c": temperature,
        "dewpoint_c": np.full(days * 24, 15.0),
        "relative_humidity_pct": np.full(days * 24, 60.0),
        "wind_speed_ms": np.full(days * 24, 2.0),
        "surface_pressure_pa": np.full(days * 24, 100_000.0),
        "solar_radiation_wm2": local_hour * 10.0,
        "thermal_radiation_wm2": np.full(days * 24, 400.0),
    }
    return _make_canonical_dataset(utc_time, values)


def _make_utc_boundary_dataset() -> xr.Dataset:
    utc_time = pd.date_range(
        "2026-05-01 00:00",
        periods=48,
        freq="h",
        tz="UTC",
    )
    size = len(utc_time)
    values = {
        "temperature_c": np.full(size, 30.0),
        "dewpoint_c": np.full(size, 20.0),
        "relative_humidity_pct": np.full(size, 60.0),
        "wind_speed_ms": np.full(size, 2.0),
        "surface_pressure_pa": np.full(size, 100_000.0),
        "solar_radiation_wm2": np.full(size, 200.0),
        "thermal_radiation_wm2": np.full(size, 400.0),
    }
    return _make_canonical_dataset(utc_time, values)


def _make_canonical_dataset(
    utc_time: pd.DatetimeIndex,
    values: dict[str, np.ndarray],
) -> xr.Dataset:
    dataset = xr.Dataset(
        data_vars={
            name: (("valid_time",), data)
            for name, data in values.items()
        },
        coords={
            "valid_time": utc_time.tz_localize(None).to_numpy(),
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
            "units": unit,
            "long_name": variable,
        }
    return dataset


if __name__ == "__main__":
    unittest.main()
