"""Tests for the deterministic Linear Regression deployment build."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import xarray as xr

from ml.inference import (
    D1_MAX_AIR_TEMPERATURE_CONTRACT,
    load_model_artifact,
)
from ml.models.build_deployment_artifact import (
    DeploymentBuildConfig,
    build_d1_max_air_temperature_artifact,
    calculate_file_sha256,
    verify_artifact_checksum,
)
from ml.preprocessing import ChronologicalSplits, SupervisedPartition


class DeploymentArtifactBuildTests(unittest.TestCase):
    def test_build_writes_loadable_artifact_manifest_and_checksum(self) -> None:
        splits = _make_splits()
        selected = xr.Dataset(coords={"latitude": 20.3, "longitude": 85.8})

        with TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = tuple(root / f"input-{index}.nc" for index in range(4))
            for index, path in enumerate(inputs):
                path.write_bytes(f"fixture-{index}".encode())
            config = DeploymentBuildConfig(
                era5_paths=inputs,
                output_root=root / "artifacts" / "ml",
                latitude=20.3,
                longitude=85.8,
                radiation_accumulation_seconds=3600.0,
                max_distance_degrees=0.2,
            )

            with (
                patch(
                    "ml.models.build_deployment_artifact.load_era5_files",
                    return_value="raw",
                ) as load,
                patch(
                    "ml.models.build_deployment_artifact.derive_canonical_weather",
                    return_value="canonical",
                ) as derive,
                patch(
                    "ml.models.build_deployment_artifact.select_nearest_point",
                    return_value=selected,
                ) as select,
                patch(
                    "ml.models.build_deployment_artifact.build_daily_feature_frame",
                    return_value="features",
                ) as daily,
                patch(
                    "ml.models.build_deployment_artifact.add_future_target",
                    return_value="labeled",
                ) as target,
                patch(
                    "ml.models.build_deployment_artifact.chronological_split",
                    return_value=splits,
                ) as split,
            ):
                outputs = build_d1_max_air_temperature_artifact(config)

            self.assertTrue(outputs.artifact_path.is_file())
            self.assertTrue(outputs.manifest_path.is_file())
            self.assertTrue(outputs.checksum_path.is_file())
            self.assertTrue(
                verify_artifact_checksum(
                    outputs.artifact_path,
                    outputs.checksum_path,
                )
            )
            loaded = load_model_artifact(
                outputs.artifact_path,
                expected_contract=D1_MAX_AIR_TEMPERATURE_CONTRACT,
            )
            self.assertEqual(loaded.metadata.model_name, "linear_regression")
            self.assertEqual(loaded.model_version, "v1")

            manifest = json.loads(outputs.manifest_path.read_text(encoding="utf-8"))
            required_fields = {
                "artifact_schema_version",
                "model_name",
                "model_version",
                "estimator_type",
                "target_name",
                "target_unit",
                "forecast_horizon_days",
                "ordered_feature_names",
                "training_date_range",
                "validation_date_range",
                "test_date_range",
                "selected_latitude",
                "selected_longitude",
                "validation_metrics",
                "test_metrics",
                "artifact_sha256",
                "creation_timestamp",
                "package_versions",
            }
            self.assertTrue(required_fields.issubset(manifest))
            self.assertEqual(
                manifest["artifact_sha256"],
                calculate_file_sha256(outputs.artifact_path),
            )
            self.assertEqual(manifest["build_parameters"]["fit_partition"], "train_only")
            self.assertEqual(
                manifest["ordered_feature_names"],
                list(splits.train.features.columns),
            )
            self.assertEqual(len(manifest["input_datasets"]), 4)

            load.assert_called_once_with(inputs)
            derive.assert_called_once_with(
                "raw",
                radiation_accumulation_seconds=3600.0,
            )
            select.assert_called_once_with(
                "canonical",
                latitude=20.3,
                longitude=85.8,
                max_distance_degrees=0.2,
            )
            daily.assert_called_once_with(selected, timezone="Asia/Kolkata")
            target.assert_called_once_with(
                "features",
                source_column="temperature_max_c",
                horizon_days=1,
                target_name="target_temperature_max_c_d1",
            )
            split.assert_called_once_with(
                "labeled",
                target_column="target_temperature_max_c_d1",
                train_fraction=0.70,
                validation_fraction=0.15,
                horizon_days=1,
            )

    def test_checksum_detects_artifact_changes(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "model.pkl"
            checksum = root / "model.sha256"
            artifact.write_bytes(b"trusted artifact bytes")
            digest = calculate_file_sha256(artifact)
            checksum.write_text(f"{digest}  {artifact.name}\n", encoding="utf-8")
            self.assertTrue(verify_artifact_checksum(artifact, checksum))

            artifact.write_bytes(b"changed artifact bytes")
            self.assertFalse(verify_artifact_checksum(artifact, checksum))

    def test_build_refuses_to_overwrite_existing_outputs(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "input.nc"
            input_path.write_bytes(b"fixture")
            output_directory = (
                root
                / "artifacts"
                / "ml"
                / D1_MAX_AIR_TEMPERATURE_CONTRACT.target_name
            )
            output_directory.mkdir(parents=True)
            existing = output_directory / "linear_regression-v1.pkl"
            existing.write_bytes(b"existing")
            config = DeploymentBuildConfig(
                era5_paths=(input_path,),
                output_root=root / "artifacts" / "ml",
                latitude=20.3,
                longitude=85.8,
                radiation_accumulation_seconds=3600.0,
            )

            with self.assertRaisesRegex(FileExistsError, "already exist"):
                build_d1_max_air_temperature_artifact(config)


def _make_splits() -> ChronologicalSplits:
    return ChronologicalSplits(
        train=_make_partition(start=0, rows=10),
        validation=_make_partition(start=12, rows=3),
        test=_make_partition(start=17, rows=3),
        target_column=D1_MAX_AIR_TEMPERATURE_CONTRACT.target_name,
        horizon_days=1,
        purged_boundary_rows=2,
    )


def _make_partition(*, start: int, rows: int) -> SupervisedPartition:
    sequence = np.arange(start, start + rows, dtype=float)
    features = pd.DataFrame(
        {
            "temperature_max_c": sequence + 30.0,
            "temperature_max_lag_1d": sequence + 29.0,
        }
    )
    return SupervisedPartition(
        dates=pd.Series(
            pd.date_range("2020-01-01", periods=rows, freq="D")
            + pd.Timedelta(days=start),
            name="date",
        ),
        features=features,
        target=pd.Series(sequence + 31.0, name="target_temperature_max_c_d1"),
    )


if __name__ == "__main__":
    unittest.main()
