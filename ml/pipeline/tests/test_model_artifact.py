"""Tests for reusable D+1 maximum air-temperature model artifacts."""

import pickle
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from xgboost import XGBRegressor

from ml.inference import (
    AIR_TEMPERATURE_TARGET,
    AIR_TEMPERATURE_UNIT,
    ARTIFACT_FORMAT_VERSION,
    D1_MAX_AIR_TEMPERATURE_CONTRACT,
    ArtifactContract,
    ModelArtifact,
    ModelMetadata,
    load_model_artifact,
    predict_one,
    save_model_artifact,
)


class ModelArtifactTests(unittest.TestCase):
    def setUp(self) -> None:
        self.training_features = pd.DataFrame(
            {
                "temperature_max_c": [31.0, 33.0, 35.0, 37.0],
                "relative_humidity_mean_pct": [70.0, 65.0, 60.0, 55.0],
            }
        )
        self.training_target = pd.Series([32.0, 34.0, 36.0, 38.0])
        self.feature_row = pd.DataFrame(
            {
                "temperature_max_c": [39.0],
                "relative_humidity_mean_pct": [50.0],
            }
        )
        self.metadata = ModelMetadata(
            model_name="linear_regression",
            feature_names=tuple(self.training_features.columns),
            forecast_horizon_days=1,
            target_name=AIR_TEMPERATURE_TARGET,
            target_unit=AIR_TEMPERATURE_UNIT,
        )

    def test_linear_regression_round_trip_preserves_prediction_and_contract(self) -> None:
        estimator = LinearRegression().fit(
            self.training_features,
            self.training_target,
        )
        artifact = ModelArtifact(estimator=estimator, metadata=self.metadata)

        with TemporaryDirectory() as directory:
            path = Path(directory) / "temperature_model.pkl"
            returned_path = save_model_artifact(artifact, path)
            loaded = load_model_artifact(
                path,
                expected_contract=D1_MAX_AIR_TEMPERATURE_CONTRACT,
            )

        expected = predict_one(estimator, self.feature_row, self.metadata)
        actual = loaded.predict_one(self.feature_row)
        self.assertEqual(returned_path, path)
        self.assertAlmostEqual(actual.prediction, expected.prediction)
        self.assertEqual(loaded.metadata, self.metadata)
        self.assertEqual(loaded.target_unit, AIR_TEMPERATURE_UNIT)
        self.assertEqual(actual.target_unit, AIR_TEMPERATURE_UNIT)

    def test_xgboost_round_trip_uses_the_same_public_interface(self) -> None:
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
            feature_names=tuple(self.training_features.columns),
            forecast_horizon_days=2,
            target_name="target_temperature_max_c_d2",
            target_unit=AIR_TEMPERATURE_UNIT,
        )

        with TemporaryDirectory() as directory:
            path = Path(directory) / "temperature_xgboost.pkl"
            save_model_artifact(ModelArtifact(estimator, metadata), path)
            result = load_model_artifact(path).predict_one(self.feature_row)

        self.assertTrue(np.isfinite(result.prediction))
        self.assertEqual(result.target_name, "target_temperature_max_c_d2")
        self.assertEqual(result.forecast_horizon_days, 2)

    def test_generic_artifact_accepts_valid_alternative_target_semantics(self) -> None:
        estimator = LinearRegression().fit(
            self.training_features,
            self.training_target,
        )
        metadata = ModelMetadata(
            model_name="rainfall_linear_regression",
            feature_names=tuple(self.training_features.columns),
            forecast_horizon_days=2,
            target_name="target_precipitation_sum_mm_d2",
            target_unit="mm",
        )

        artifact = ModelArtifact(estimator, metadata, model_version="rain-v1")

        with TemporaryDirectory() as directory:
            path = Path(directory) / "rainfall.pkl"
            save_model_artifact(artifact, path)
            loaded = load_model_artifact(path)

        self.assertEqual(loaded.metadata, metadata)
        self.assertEqual(loaded.target_unit, "mm")

    def test_d1_contract_accepts_matching_artifact_and_rejects_mismatch(self) -> None:
        estimator = LinearRegression().fit(
            self.training_features,
            self.training_target,
        )
        matching = ModelArtifact(estimator, self.metadata)
        matching.predict_one(
            self.feature_row,
            expected_contract=D1_MAX_AIR_TEMPERATURE_CONTRACT,
        )

        mismatches = (
            ArtifactContract("target_temperature_mean_c_d1", "degC", 1),
            ArtifactContract(AIR_TEMPERATURE_TARGET, "degF", 1),
            ArtifactContract(AIR_TEMPERATURE_TARGET, "degC", 2),
        )
        for contract in mismatches:
            with self.subTest(contract=contract), self.assertRaisesRegex(
                ValueError,
                "contract mismatch",
            ):
                matching.predict_one(
                    self.feature_row,
                    expected_contract=contract,
                )

        alternative_metadata = ModelMetadata(
            model_name="linear_regression",
            feature_names=tuple(self.training_features.columns),
            forecast_horizon_days=2,
            target_name="target_temperature_max_c_d2",
            target_unit="degC",
        )
        with TemporaryDirectory() as directory:
            path = Path(directory) / "d2-model.pkl"
            save_model_artifact(ModelArtifact(estimator, alternative_metadata), path)
            with self.assertRaisesRegex(ValueError, "contract mismatch"):
                load_model_artifact(
                    path,
                    expected_contract=D1_MAX_AIR_TEMPERATURE_CONTRACT,
                )

    def test_artifact_requires_explicit_target_semantics_and_model_version(self) -> None:
        estimator = LinearRegression().fit(
            self.training_features,
            self.training_target,
        )
        missing_semantics = (
            ModelMetadata("model", tuple(self.training_features.columns), 1),
            ModelMetadata(
                "model",
                tuple(self.training_features.columns),
                1,
                target_name=AIR_TEMPERATURE_TARGET,
            ),
        )
        for metadata in missing_semantics:
            with self.subTest(metadata=metadata), self.assertRaises(ValueError):
                ModelArtifact(estimator, metadata)
        with self.assertRaisesRegex(ValueError, "model_version"):
            ModelArtifact(estimator, self.metadata, model_version="")

    def test_artifact_rejects_unfitted_or_schema_mismatched_estimator(self) -> None:
        with self.assertRaisesRegex(ValueError, "fitted"):
            ModelArtifact(LinearRegression(), self.metadata)

        mismatched = LinearRegression().fit(
            self.training_features[["relative_humidity_mean_pct", "temperature_max_c"]],
            self.training_target,
        )
        with self.assertRaisesRegex(ValueError, "estimator schema"):
            ModelArtifact(mismatched, self.metadata)

    def test_load_rejects_corrupt_and_unsupported_payloads(self) -> None:
        with TemporaryDirectory() as directory:
            corrupt_path = Path(directory) / "corrupt.pkl"
            corrupt_path.write_bytes(b"not a pickle")
            with self.assertRaisesRegex(ValueError, "could not be loaded"):
                load_model_artifact(corrupt_path)

            unsupported_path = Path(directory) / "unsupported.pkl"
            with unsupported_path.open("wb") as output:
                pickle.dump({"estimator": "not-an-artifact"}, output)
            with self.assertRaisesRegex(ValueError, "unsupported payload"):
                load_model_artifact(unsupported_path)

    def test_load_rejects_unsupported_artifact_schema(self) -> None:
        estimator = LinearRegression().fit(
            self.training_features,
            self.training_target,
        )
        artifact = ModelArtifact(estimator, self.metadata)
        object.__setattr__(
            artifact,
            "format_version",
            ARTIFACT_FORMAT_VERSION + 1,
        )

        with TemporaryDirectory() as directory:
            path = Path(directory) / "future-format.pkl"
            with path.open("wb") as output:
                pickle.dump(artifact, output)
            with self.assertRaisesRegex(ValueError, "format version"):
                load_model_artifact(path)

    def test_save_requires_existing_parent_and_load_requires_file(self) -> None:
        estimator = LinearRegression().fit(
            self.training_features,
            self.training_target,
        )
        artifact = ModelArtifact(estimator, self.metadata)

        with TemporaryDirectory() as directory:
            missing_parent = Path(directory) / "missing" / "model.pkl"
            with self.assertRaises(FileNotFoundError):
                save_model_artifact(artifact, missing_parent)
            with self.assertRaises(FileNotFoundError):
                load_model_artifact(Path(directory) / "missing.pkl")


if __name__ == "__main__":
    unittest.main()
