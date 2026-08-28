"""Tests for generic future targets and chronological supervised splits."""

import unittest

import numpy as np
import pandas as pd

from ml.preprocessing import add_future_target, chronological_split


class FutureTargetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = _make_feature_frame(30)

    def test_default_target_alignment_row_loss_metadata_and_non_mutation(self) -> None:
        original = self.frame.copy(deep=True)

        labeled = add_future_target(
            self.frame,
            source_column="temperature_max_c",
            horizon_days=1,
        )

        target = "target_temperature_max_c_d1"
        self.assertEqual(len(labeled), 29)
        self.assertEqual(labeled.loc[0, target], self.frame.loc[1, "temperature_max_c"])
        self.assertEqual(labeled.loc[28, target], self.frame.loc[29, "temperature_max_c"])
        self.assertEqual(labeled.attrs["target_source_column"], "temperature_max_c")
        self.assertEqual(labeled.attrs["target_column"], target)
        self.assertEqual(labeled.attrs["target_horizon_days"], 1)
        self.assertEqual(labeled.attrs["rows_dropped_without_future_target"], 1)
        pd.testing.assert_frame_equal(self.frame, original)

    def test_horizon_two_and_custom_target_name(self) -> None:
        labeled = add_future_target(
            self.frame,
            source_column="hazard_proxy",
            horizon_days=2,
            target_name="future_hazard",
        )

        self.assertEqual(len(labeled), 28)
        self.assertEqual(labeled.loc[0, "future_hazard"], self.frame.loc[2, "hazard_proxy"])
        self.assertEqual(labeled.loc[27, "future_hazard"], self.frame.loc[29, "hazard_proxy"])
        self.assertEqual(labeled.attrs["rows_dropped_without_future_target"], 2)

    def test_rejects_invalid_source_values(self) -> None:
        cases = {
            "missing": self.frame.drop(columns="hazard_proxy"),
            "nonnumeric": self.frame.assign(hazard_proxy="hot"),
            "missing_value": self.frame.assign(
                hazard_proxy=self.frame["hazard_proxy"].mask(self.frame.index == 2)
            ),
            "infinite": self.frame.assign(
                hazard_proxy=self.frame["hazard_proxy"].mask(
                    self.frame.index == 2,
                    np.inf,
                )
            ),
        }
        for name, frame in cases.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                add_future_target(frame, source_column="hazard_proxy")

    def test_rejects_invalid_or_oversized_horizons(self) -> None:
        for horizon in (0, -1, 1.5, True, len(self.frame)):
            with self.subTest(horizon=horizon), self.assertRaises(ValueError):
                add_future_target(
                    self.frame,
                    source_column="hazard_proxy",
                    horizon_days=horizon,
                )

    def test_rejects_invalid_daily_dates(self) -> None:
        unordered = self.frame.copy(deep=True)
        unordered.loc[[1, 2], "date"] = unordered.loc[[2, 1], "date"].to_numpy()
        duplicated = self.frame.copy(deep=True)
        duplicated.loc[2, "date"] = duplicated.loc[1, "date"]
        gapped = self.frame.drop(index=2).reset_index(drop=True)

        for name, frame in {
            "unordered": unordered,
            "duplicated": duplicated,
            "gapped": gapped,
        }.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                add_future_target(frame, source_column="hazard_proxy")


class ChronologicalSplitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.labeled = add_future_target(
            _make_feature_frame(31),
            source_column="hazard_proxy",
            horizon_days=1,
        )
        self.target_column = "target_hazard_proxy_d1"

    def test_split_sizes_order_and_no_shuffle(self) -> None:
        splits = chronological_split(
            self.labeled,
            target_column=self.target_column,
        )

        self.assertEqual(len(splits.train.features), 20)
        self.assertEqual(len(splits.validation.features), 3)
        self.assertEqual(len(splits.test.features), 5)
        self.assertEqual(splits.purged_boundary_rows, 2)
        self.assertEqual(
            splits.train.dates.tolist(),
            self.labeled.loc[0:19, "date"].tolist(),
        )
        self.assertEqual(
            splits.validation.dates.tolist(),
            self.labeled.loc[21:23, "date"].tolist(),
        )
        self.assertEqual(
            splits.test.dates.tolist(),
            self.labeled.loc[25:29, "date"].tolist(),
        )

    def test_target_and_date_are_absent_from_model_features(self) -> None:
        splits = chronological_split(
            self.labeled,
            target_column=self.target_column,
        )

        for partition in (splits.train, splits.validation, splits.test):
            self.assertNotIn(self.target_column, partition.features.columns)
            self.assertNotIn("date", partition.features.columns)
            self.assertEqual(
                list(partition.features.columns),
                ["temperature_max_c", "hazard_proxy", "lag_feature"],
            )

    def test_targets_remain_aligned_with_feature_dates(self) -> None:
        splits = chronological_split(
            self.labeled,
            target_column=self.target_column,
        )
        lookup = self.labeled.set_index("date")

        for partition in (splits.train, splits.validation, splits.test):
            for date, target in zip(partition.dates, partition.target, strict=True):
                self.assertEqual(target, lookup.loc[date, self.target_column])

    def test_horizon_purge_prevents_boundary_crossing(self) -> None:
        horizon = pd.Timedelta(days=1)
        splits = chronological_split(
            self.labeled,
            target_column=self.target_column,
        )

        self.assertLess(
            splits.train.dates.iloc[-1] + horizon,
            splits.validation.dates.iloc[0],
        )
        self.assertLess(
            splits.validation.dates.iloc[-1] + horizon,
            splits.test.dates.iloc[0],
        )
        self.assertLess(splits.train.dates.iloc[-1], splits.validation.dates.iloc[0])
        self.assertLess(splits.validation.dates.iloc[-1], splits.test.dates.iloc[0])

    def test_two_day_horizon_uses_two_row_boundary_purges(self) -> None:
        labeled = add_future_target(
            _make_feature_frame(40),
            source_column="hazard_proxy",
            horizon_days=2,
        )
        splits = chronological_split(
            labeled,
            target_column="target_hazard_proxy_d2",
        )
        horizon = pd.Timedelta(days=2)

        self.assertEqual(splits.horizon_days, 2)
        self.assertEqual(splits.purged_boundary_rows, 4)
        self.assertLess(
            splits.train.dates.iloc[-1] + horizon,
            splits.validation.dates.iloc[0],
        )
        self.assertLess(
            splits.validation.dates.iloc[-1] + horizon,
            splits.test.dates.iloc[0],
        )

    def test_invalid_fractions_and_small_splits_are_rejected(self) -> None:
        invalid_fractions = (
            {"train_fraction": 0.0},
            {"train_fraction": 1.0},
            {"validation_fraction": 0.0},
            {"train_fraction": 0.9, "validation_fraction": 0.2},
        )
        for values in invalid_fractions:
            with self.subTest(values=values), self.assertRaises(ValueError):
                chronological_split(
                    self.labeled,
                    target_column=self.target_column,
                    **values,
                )

        small = add_future_target(
            _make_feature_frame(6),
            source_column="hazard_proxy",
        )
        with self.assertRaisesRegex(ValueError, "insufficient rows"):
            chronological_split(
                small,
                target_column="target_hazard_proxy_d1",
            )

    def test_split_does_not_mutate_input(self) -> None:
        original = self.labeled.copy(deep=True)
        original_attrs = self.labeled.attrs.copy()

        chronological_split(
            self.labeled,
            target_column=self.target_column,
        )

        pd.testing.assert_frame_equal(self.labeled, original)
        self.assertEqual(self.labeled.attrs, original_attrs)

    def test_explicit_horizon_must_match_target_metadata(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not match"):
            chronological_split(
                self.labeled,
                target_column=self.target_column,
                horizon_days=2,
            )


def _make_feature_frame(rows: int) -> pd.DataFrame:
    sequence = np.arange(rows, dtype=float)
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=rows, freq="D"),
            "temperature_max_c": 30.0 + sequence,
            "hazard_proxy": 100.0 + 2.0 * sequence,
            "lag_feature": 10.0 + sequence,
        }
    )
    frame.attrs["pipeline_stage"] = "test_fixture"
    return frame


if __name__ == "__main__":
    unittest.main()
