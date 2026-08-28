"""Tests for generic regression baselines and evaluation metrics."""

import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from ml.models import (
    calculate_regression_metrics,
    evaluate_linear_regression_baseline,
    evaluate_persistence_baseline,
    fit_linear_regression,
    persistence_predictions,
)
from ml.preprocessing import ChronologicalSplits, SupervisedPartition


class RegressionMetricTests(unittest.TestCase):
    def test_metrics_match_manual_values(self) -> None:
        actual = np.array([1.0, 2.0, 3.0])
        predicted = np.array([1.0, 3.0, 2.0])

        metrics = calculate_regression_metrics(actual, predicted)

        self.assertAlmostEqual(metrics.mae, 2.0 / 3.0)
        self.assertAlmostEqual(metrics.rmse, np.sqrt(2.0 / 3.0))
        self.assertAlmostEqual(metrics.r2, 0.0)

    def test_metrics_reject_invalid_inputs(self) -> None:
        cases = (
            (np.array([1.0, 2.0]), np.array([1.0])),
            (np.array([1.0]), np.array([1.0])),
            (np.array([1.0, np.nan]), np.array([1.0, 2.0])),
            (np.array([1.0, 2.0]), np.array([1.0, np.inf])),
            (np.array(["one", "two"]), np.array([1.0, 2.0])),
            (np.array([[1.0, 2.0]]), np.array([1.0, 2.0])),
        )
        for actual, predicted in cases:
            with self.subTest(actual=actual, predicted=predicted):
                with self.assertRaises(ValueError):
                    calculate_regression_metrics(actual, predicted)


class BaselineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.splits = _make_splits()

    def test_persistence_predictions_use_current_source_values(self) -> None:
        predictions = persistence_predictions(
            self.splits.validation,
            source_column="current_hazard",
        )

        pd.testing.assert_series_equal(
            predictions,
            self.splits.validation.features["current_hazard"].rename("prediction"),
        )

    def test_persistence_rejects_missing_source(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not exist"):
            persistence_predictions(
                self.splits.validation,
                source_column="missing",
            )

    def test_persistence_validation_and_test_are_evaluated_separately(self) -> None:
        result = evaluate_persistence_baseline(
            self.splits,
            source_column="current_hazard",
        )

        self.assertEqual(result.name, "persistence")
        self.assertEqual(len(result.validation.predictions), 3)
        self.assertEqual(len(result.test.predictions), 3)
        self.assertNotEqual(result.validation.metrics.mae, result.test.metrics.mae)

    def test_linear_regression_fits_training_only_and_predicts_held_out(self) -> None:
        with patch("ml.models.baseline.LinearRegression") as linear_regression:
            model = linear_regression.return_value
            model.predict.side_effect = [
                np.array([10.0, 11.0, 12.0]),
                np.array([20.0, 21.0, 22.0]),
            ]

            evaluate_linear_regression_baseline(self.splits)

        model.fit.assert_called_once()
        fit_features, fit_target = model.fit.call_args.args
        pd.testing.assert_frame_equal(fit_features, self.splits.train.features)
        pd.testing.assert_series_equal(fit_target, self.splits.train.target)
        self.assertEqual(model.predict.call_count, 2)
        pd.testing.assert_frame_equal(
            model.predict.call_args_list[0].args[0],
            self.splits.validation.features,
        )
        pd.testing.assert_frame_equal(
            model.predict.call_args_list[1].args[0],
            self.splits.test.features,
        )

    def test_linear_regression_recovers_synthetic_relationship(self) -> None:
        result = evaluate_linear_regression_baseline(self.splits)

        self.assertAlmostEqual(result.validation.metrics.mae, 0.0, places=10)
        self.assertAlmostEqual(result.validation.metrics.rmse, 0.0, places=10)
        self.assertAlmostEqual(result.validation.metrics.r2, 1.0, places=10)
        self.assertAlmostEqual(result.test.metrics.mae, 0.0, places=10)
        self.assertAlmostEqual(result.test.metrics.rmse, 0.0, places=10)
        self.assertAlmostEqual(result.test.metrics.r2, 1.0, places=10)

    def test_fit_linear_regression_returns_fitted_estimator(self) -> None:
        model = fit_linear_regression(self.splits.train)

        predictions = model.predict(self.splits.validation.features)
        self.assertEqual(len(predictions), len(self.splits.validation.features))
        self.assertEqual(
            tuple(model.feature_names_in_),
            tuple(self.splits.train.features.columns),
        )

    def test_mismatched_feature_schema_is_rejected(self) -> None:
        validation = SupervisedPartition(
            dates=self.splits.validation.dates,
            features=self.splits.validation.features[["feature_b", "current_hazard"]],
            target=self.splits.validation.target,
        )
        mismatched = ChronologicalSplits(
            train=self.splits.train,
            validation=validation,
            test=self.splits.test,
            target_column=self.splits.target_column,
            horizon_days=1,
            purged_boundary_rows=2,
        )

        with self.assertRaisesRegex(ValueError, "feature columns"):
            evaluate_linear_regression_baseline(mismatched)

    def test_target_and_date_are_not_model_features(self) -> None:
        for partition in (
            self.splits.train,
            self.splits.validation,
            self.splits.test,
        ):
            self.assertNotIn(self.splits.target_column, partition.features.columns)
            self.assertNotIn("date", partition.features.columns)

    def test_evaluation_does_not_mutate_splits(self) -> None:
        originals = [
            (
                partition.features.copy(deep=True),
                partition.target.copy(deep=True),
                partition.dates.copy(deep=True),
            )
            for partition in (
                self.splits.train,
                self.splits.validation,
                self.splits.test,
            )
        ]

        evaluate_persistence_baseline(
            self.splits,
            source_column="current_hazard",
        )
        evaluate_linear_regression_baseline(self.splits)

        for partition, original in zip(
            (self.splits.train, self.splits.validation, self.splits.test),
            originals,
            strict=True,
        ):
            pd.testing.assert_frame_equal(partition.features, original[0])
            pd.testing.assert_series_equal(partition.target, original[1])
            pd.testing.assert_series_equal(partition.dates, original[2])


def _make_splits() -> ChronologicalSplits:
    train = _make_partition(start=0, rows=8, target_offset=1.0)
    validation = _make_partition(start=10, rows=3, target_offset=1.0)
    test = _make_partition(start=20, rows=3, target_offset=1.0)
    return ChronologicalSplits(
        train=train,
        validation=validation,
        test=test,
        target_column="future_hazard",
        horizon_days=1,
        purged_boundary_rows=2,
    )


def _make_partition(
    *,
    start: int,
    rows: int,
    target_offset: float,
) -> SupervisedPartition:
    sequence = np.arange(start, start + rows, dtype=float)
    features = pd.DataFrame(
        {
            "current_hazard": sequence,
            "feature_b": sequence * 2.0,
        }
    )
    target = pd.Series(3.0 * sequence + 5.0, name="future_hazard")
    if target_offset != 1.0:
        target = target + target_offset
    return SupervisedPartition(
        dates=pd.Series(
            pd.date_range("2020-01-01", periods=rows, freq="D")
            + pd.Timedelta(days=start),
            name="date",
        ),
        features=features,
        target=target,
    )


if __name__ == "__main__":
    unittest.main()
