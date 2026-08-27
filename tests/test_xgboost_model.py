"""Tests for the fixed-configuration XGBoost regression pipeline."""

import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from ml.models import train_and_evaluate_xgboost
from ml.models.train_xgboost import _build_model
from ml.preprocessing import ChronologicalSplits, SupervisedPartition


class XGBoostModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.splits = _make_splits()

    def test_fixed_model_configuration(self) -> None:
        parameters = _build_model(42).get_params()

        expected = {
            "objective": "reg:squarederror",
            "n_estimators": 500,
            "learning_rate": 0.05,
            "max_depth": 3,
            "min_child_weight": 5,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "reg_lambda": 1.0,
            "reg_alpha": 0.0,
            "tree_method": "hist",
            "eval_metric": "rmse",
            "early_stopping_rounds": 30,
            "importance_type": "gain",
            "random_state": 42,
            "n_jobs": 1,
        }
        for name, value in expected.items():
            with self.subTest(parameter=name):
                self.assertEqual(parameters[name], value)

    def test_fit_uses_train_and_validation_only_and_test_is_predicted_last(self) -> None:
        events = []
        with patch("ml.models.train_xgboost.XGBRegressor") as regressor:
            model = regressor.return_value
            model.best_iteration = 7
            model.feature_importances_ = np.array([0.6, 0.3, 0.1])
            model.fit.side_effect = lambda *args, **kwargs: events.append("fit")
            model.predict.side_effect = [
                np.array([10.0, 11.0, 12.0]),
                np.array([20.0, 21.0, 22.0]),
            ]

            result = train_and_evaluate_xgboost(self.splits)
            events.extend(["validation_predict", "test_predict"])

        model.fit.assert_called_once()
        fit_features, fit_target = model.fit.call_args.args
        pd.testing.assert_frame_equal(fit_features, self.splits.train.features)
        pd.testing.assert_series_equal(fit_target, self.splits.train.target)
        eval_set = model.fit.call_args.kwargs["eval_set"]
        self.assertEqual(len(eval_set), 1)
        pd.testing.assert_frame_equal(eval_set[0][0], self.splits.validation.features)
        pd.testing.assert_series_equal(eval_set[0][1], self.splits.validation.target)
        self.assertEqual(model.predict.call_count, 2)
        pd.testing.assert_frame_equal(
            model.predict.call_args_list[0].args[0],
            self.splits.validation.features,
        )
        pd.testing.assert_frame_equal(
            model.predict.call_args_list[1].args[0],
            self.splits.test.features,
        )
        self.assertEqual(result.best_iteration, 7)

    def test_actual_training_returns_metrics_and_feature_importance(self) -> None:
        result = train_and_evaluate_xgboost(self.splits)

        self.assertEqual(len(result.validation.predictions), 3)
        self.assertEqual(len(result.test.predictions), 3)
        self.assertGreaterEqual(result.best_iteration, 0)
        self.assertGreaterEqual(result.training_duration_seconds, 0.0)
        self.assertEqual(
            result.feature_importance["feature"].tolist(),
            [
                feature
                for feature in result.feature_importance.sort_values(
                    "importance_gain",
                    ascending=False,
                    kind="stable",
                )["feature"]
            ],
        )
        self.assertEqual(
            set(result.feature_importance["feature"]),
            set(self.splits.train.features.columns),
        )
        self.assertTrue(np.isfinite(result.feature_importance["importance_gain"]).all())
        self.assertTrue((result.feature_importance["importance_gain"] >= 0).all())

    def test_fixed_seed_is_deterministic(self) -> None:
        first = train_and_evaluate_xgboost(self.splits, random_seed=42)
        second = train_and_evaluate_xgboost(self.splits, random_seed=42)

        np.testing.assert_allclose(
            first.validation.predictions,
            second.validation.predictions,
        )
        np.testing.assert_allclose(first.test.predictions, second.test.predictions)
        self.assertEqual(first.best_iteration, second.best_iteration)

    def test_mismatched_feature_order_is_rejected(self) -> None:
        validation = SupervisedPartition(
            dates=self.splits.validation.dates,
            features=self.splits.validation.features[
                ["feature_c", "feature_b", "feature_a"]
            ],
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
            train_and_evaluate_xgboost(mismatched)

    def test_nonfinite_features_are_rejected(self) -> None:
        train_features = self.splits.train.features.copy(deep=True)
        train_features.loc[0, "feature_a"] = np.inf
        train = SupervisedPartition(
            dates=self.splits.train.dates,
            features=train_features,
            target=self.splits.train.target,
        )
        invalid = ChronologicalSplits(
            train=train,
            validation=self.splits.validation,
            test=self.splits.test,
            target_column=self.splits.target_column,
            horizon_days=1,
            purged_boundary_rows=2,
        )

        with self.assertRaisesRegex(ValueError, "non-finite"):
            train_and_evaluate_xgboost(invalid)

    def test_training_does_not_mutate_splits(self) -> None:
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

        train_and_evaluate_xgboost(self.splits)

        for partition, original in zip(
            (self.splits.train, self.splits.validation, self.splits.test),
            originals,
            strict=True,
        ):
            pd.testing.assert_frame_equal(partition.features, original[0])
            pd.testing.assert_series_equal(partition.target, original[1])
            pd.testing.assert_series_equal(partition.dates, original[2])


def _make_splits() -> ChronologicalSplits:
    return ChronologicalSplits(
        train=_make_partition(start=0, rows=40),
        validation=_make_partition(start=42, rows=3),
        test=_make_partition(start=47, rows=3),
        target_column="future_hazard",
        horizon_days=1,
        purged_boundary_rows=2,
    )


def _make_partition(*, start: int, rows: int) -> SupervisedPartition:
    sequence = np.arange(start, start + rows, dtype=float)
    features = pd.DataFrame(
        {
            "feature_a": sequence,
            "feature_b": np.sin(sequence / 3.0),
            "feature_c": np.cos(sequence / 5.0),
        }
    )
    target = pd.Series(
        0.4 * sequence + 2.0 * np.sin(sequence / 3.0),
        name="future_hazard",
    )
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
