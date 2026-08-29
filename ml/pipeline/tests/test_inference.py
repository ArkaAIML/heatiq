"""Tests for strict ML-internal single-row inference."""

import unittest
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from xgboost import XGBRegressor

from ml.inference import ModelMetadata, PredictionResult, predict_one


class InferenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.training_features = pd.DataFrame(
            {
                "feature_a": [1.0, 2.0, 3.0, 4.0],
                "feature_b": [2.0, 1.0, 4.0, 3.0],
            }
        )
        self.training_target = pd.Series([4.0, 5.0, 10.0, 11.0])
        self.estimator = LinearRegression().fit(
            self.training_features,
            self.training_target,
        )
        self.metadata = ModelMetadata(
            model_name="linear_regression",
            feature_names=("feature_a", "feature_b"),
            forecast_horizon_days=1,
            target_name="target_temperature_max_c_d1",
            target_unit="degC",
        )
        self.feature_row = pd.DataFrame(
            {"feature_a": [5.0], "feature_b": [6.0]}
        )

    def test_fitted_estimator_returns_structured_prediction(self) -> None:
        feature_date = datetime(2026, 5, 10)

        result = predict_one(
            self.estimator,
            self.feature_row,
            self.metadata,
            feature_date=feature_date,
        )

        self.assertIsInstance(result, PredictionResult)
        self.assertIsInstance(result.prediction, float)
        self.assertTrue(np.isfinite(result.prediction))
        self.assertEqual(result.model_name, "linear_regression")
        self.assertEqual(result.forecast_horizon_days, 1)
        self.assertEqual(result.feature_date, feature_date)
        self.assertEqual(result.target_name, "target_temperature_max_c_d1")
        self.assertEqual(result.target_unit, "degC")

    def test_fitted_xgboost_uses_the_same_interface(self) -> None:
        estimator = XGBRegressor(
            objective="reg:squarederror",
            n_estimators=3,
            max_depth=2,
            tree_method="hist",
            random_state=42,
            n_jobs=1,
            verbosity=0,
        ).fit(self.training_features, self.training_target)
        metadata = ModelMetadata(
            model_name="xgboost",
            feature_names=("feature_a", "feature_b"),
            forecast_horizon_days=1,
            target_name="target_temperature_max_c_d1",
            target_unit="degC",
        )

        result = predict_one(estimator, self.feature_row, metadata)

        self.assertIsInstance(result.prediction, float)
        self.assertTrue(np.isfinite(result.prediction))
        self.assertEqual(result.model_name, "xgboost")

    def test_inference_does_not_fit_or_mutate_input(self) -> None:
        class MutatingEstimator:
            feature_names_in_ = np.array(["feature_a", "feature_b"])
            n_features_in_ = 2

            def __init__(self) -> None:
                self.fit_called = False

            def fit(self, *_args: object, **_kwargs: object) -> None:
                self.fit_called = True

            def predict(self, features: pd.DataFrame) -> np.ndarray:
                features.loc[:, "feature_a"] = -999.0
                return np.array([3.5])

        estimator = MutatingEstimator()
        original = self.feature_row.copy(deep=True)

        result = predict_one(estimator, self.feature_row, self.metadata)

        self.assertEqual(result.prediction, 3.5)
        self.assertFalse(estimator.fit_called)
        pd.testing.assert_frame_equal(self.feature_row, original)

    def test_requires_exactly_one_dataframe_row(self) -> None:
        invalid_rows = (
            pd.DataFrame(columns=self.metadata.feature_names),
            pd.concat([self.feature_row, self.feature_row], ignore_index=True),
        )
        for row in invalid_rows:
            with self.subTest(rows=len(row)), self.assertRaisesRegex(
                ValueError,
                "exactly one row",
            ):
                predict_one(self.estimator, row, self.metadata)

        with self.assertRaisesRegex(TypeError, "DataFrame"):
            predict_one(self.estimator, self.feature_row.iloc[0], self.metadata)

    def test_rejects_missing_extra_and_reordered_features(self) -> None:
        cases = {
            "missing": self.feature_row.drop(columns="feature_b"),
            "extra": self.feature_row.assign(feature_c=1.0),
            "reordered": self.feature_row[["feature_b", "feature_a"]],
        }
        for name, row in cases.items():
            with self.subTest(name=name), self.assertRaisesRegex(
                ValueError,
                "feature columns",
            ):
                predict_one(self.estimator, row, self.metadata)

    def test_rejects_invalid_feature_values(self) -> None:
        cases = {
            "string": self.feature_row.assign(feature_a="hot"),
            "boolean": self.feature_row.assign(feature_a=True),
            "missing": self.feature_row.assign(feature_a=np.nan),
            "infinite": self.feature_row.assign(feature_a=np.inf),
        }
        for name, row in cases.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                predict_one(self.estimator, row, self.metadata)

    def test_rejects_invalid_metadata(self) -> None:
        invalid_metadata = (
            ModelMetadata("", ("feature_a",), 1),
            ModelMetadata("model", (), 1),
            ModelMetadata("model", ("feature_a", "feature_a"), 1),
            ModelMetadata("model", ("date",), 1),
            ModelMetadata("model", ("target",), 1, target_name="target"),
            ModelMetadata("model", ("feature_a",), 0),
            ModelMetadata("model", ("feature_a",), True),
            ModelMetadata("model", ("feature_a",), 1, target_name=""),
            ModelMetadata("model", ("feature_a",), 1, target_unit=""),
        )
        for metadata in invalid_metadata:
            with self.subTest(metadata=metadata), self.assertRaises(ValueError):
                predict_one(self.estimator, self.feature_row, metadata)

    def test_rejects_metadata_that_disagrees_with_estimator_schema(self) -> None:
        wrong_names = ModelMetadata(
            "linear_regression",
            ("feature_a", "feature_c"),
            1,
        )
        matching_row = pd.DataFrame({"feature_a": [5.0], "feature_c": [6.0]})

        with self.assertRaisesRegex(ValueError, "estimator schema"):
            predict_one(self.estimator, matching_row, wrong_names)

        class CountOnlyEstimator:
            n_features_in_ = 3

            def predict(self, _features: pd.DataFrame) -> np.ndarray:
                return np.array([1.0])

        with self.assertRaisesRegex(ValueError, "feature count"):
            predict_one(CountOnlyEstimator(), self.feature_row, self.metadata)

    def test_unfitted_estimator_is_reported_clearly(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "must be fitted"):
            predict_one(LinearRegression(), self.feature_row, self.metadata)

    def test_requires_callable_predict(self) -> None:
        with self.assertRaisesRegex(TypeError, "callable predict"):
            predict_one(object(), self.feature_row, self.metadata)

    def test_rejects_invalid_prediction_outputs(self) -> None:
        class InvalidOutputEstimator:
            def __init__(self, output: object) -> None:
                self.output = output

            def predict(self, _features: pd.DataFrame) -> object:
                return self.output

        cases = (
            np.array([]),
            np.array([1.0, 2.0]),
            np.array([[1.0]]),
            np.array(["hot"]),
            np.array([True]),
            np.array([np.inf]),
        )
        for output in cases:
            with self.subTest(output=output), self.assertRaises(ValueError):
                predict_one(
                    InvalidOutputEstimator(output),
                    self.feature_row,
                    self.metadata,
                )

    def test_rejects_invalid_feature_date(self) -> None:
        with self.assertRaisesRegex(TypeError, "feature_date"):
            predict_one(
                self.estimator,
                self.feature_row,
                self.metadata,
                feature_date="2026-05-10",  # type: ignore[arg-type]
            )


if __name__ == "__main__":
    unittest.main()
