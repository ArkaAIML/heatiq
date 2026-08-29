"""Build the trusted D+1 maximum-air-temperature deployment artifact.

This module intentionally composes the existing ML preprocessing, splitting,
fitting, evaluation, and artifact APIs. It does not define a second training
pipeline. Generated pickle files must only be loaded from trusted HeatIQ
builds.
"""

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import hmac
from importlib.metadata import PackageNotFoundError, version
import json
from os import PathLike, fsync, replace
from pathlib import Path
import platform
import re
from tempfile import NamedTemporaryFile

import numpy as np

from ml.inference import (
    ARTIFACT_FORMAT_VERSION,
    D1_MAX_AIR_TEMPERATURE_CONTRACT,
    ModelArtifact,
    ModelMetadata,
    load_model_artifact,
    save_model_artifact,
)
from ml.models.baseline import fit_linear_regression
from ml.models.evaluate import evaluate_predictions
from ml.preprocessing import (
    add_future_target,
    build_daily_feature_frame,
    chronological_split,
    derive_canonical_weather,
    load_era5_files,
    select_nearest_point,
)


DEPLOYMENT_MODEL_NAME = "linear_regression"
DEFAULT_MODEL_VERSION = "v1"
_MODEL_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_PACKAGE_NAMES = ("netCDF4", "numpy", "pandas", "scikit-learn", "xarray")


@dataclass(frozen=True)
class DeploymentBuildConfig:
    """Explicit inputs and parameters for one reproducible artifact build."""

    era5_paths: tuple[Path, ...]
    output_root: Path
    latitude: float
    longitude: float
    radiation_accumulation_seconds: float
    model_version: str = DEFAULT_MODEL_VERSION
    timezone_name: str = "Asia/Kolkata"
    max_distance_degrees: float | None = None
    train_fraction: float = 0.70
    validation_fraction: float = 0.15


@dataclass(frozen=True)
class DeploymentBuildOutputs:
    """Paths written by a completed deployment artifact build."""

    artifact_path: Path
    manifest_path: Path
    checksum_path: Path


def build_d1_max_air_temperature_artifact(
    config: DeploymentBuildConfig,
) -> DeploymentBuildOutputs:
    """Fit, evaluate, persist, document, and verify the selected model."""

    _validate_config(config)
    contract = D1_MAX_AIR_TEMPERATURE_CONTRACT
    output_directory = config.output_root / contract.target_name
    stem = f"{DEPLOYMENT_MODEL_NAME}-{config.model_version}"
    outputs = DeploymentBuildOutputs(
        artifact_path=output_directory / f"{stem}.pkl",
        manifest_path=output_directory / f"{stem}.manifest.json",
        checksum_path=output_directory / f"{stem}.sha256",
    )
    _ensure_outputs_do_not_exist(outputs)
    input_datasets = [
        {
            "path": str(path),
            "sha256": calculate_file_sha256(path),
        }
        for path in config.era5_paths
    ]

    raw = load_era5_files(config.era5_paths)
    canonical = derive_canonical_weather(
        raw,
        radiation_accumulation_seconds=config.radiation_accumulation_seconds,
    )
    selected = select_nearest_point(
        canonical,
        latitude=config.latitude,
        longitude=config.longitude,
        max_distance_degrees=config.max_distance_degrees,
    )
    feature_frame = build_daily_feature_frame(
        selected,
        timezone=config.timezone_name,
    )
    labeled = add_future_target(
        feature_frame,
        source_column="temperature_max_c",
        horizon_days=contract.forecast_horizon_days,
        target_name=contract.target_name,
    )
    splits = chronological_split(
        labeled,
        target_column=contract.target_name,
        train_fraction=config.train_fraction,
        validation_fraction=config.validation_fraction,
        horizon_days=contract.forecast_horizon_days,
    )

    estimator = fit_linear_regression(splits.train)
    validation = evaluate_predictions(
        splits.validation.target,
        estimator.predict(splits.validation.features),
    )
    test = evaluate_predictions(
        splits.test.target,
        estimator.predict(splits.test.features),
    )
    metadata = ModelMetadata(
        model_name=DEPLOYMENT_MODEL_NAME,
        feature_names=tuple(splits.train.features.columns),
        forecast_horizon_days=contract.forecast_horizon_days,
        target_name=contract.target_name,
        target_unit=contract.target_unit,
    )
    artifact = ModelArtifact(
        estimator=estimator,
        metadata=metadata,
        model_version=config.model_version,
    )

    output_directory.mkdir(parents=True, exist_ok=True)
    reference_row = splits.test.features.iloc[[0]].copy(deep=True)
    expected_prediction = artifact.predict_one(
        reference_row,
        expected_contract=contract,
    ).prediction
    save_model_artifact(artifact, outputs.artifact_path)
    artifact_digest = calculate_file_sha256(outputs.artifact_path)

    manifest = {
        "artifact_schema_version": ARTIFACT_FORMAT_VERSION,
        "model_name": metadata.model_name,
        "model_version": artifact.model_version,
        "estimator_type": (
            f"{type(estimator).__module__}.{type(estimator).__qualname__}"
        ),
        "target_name": metadata.target_name,
        "target_unit": metadata.target_unit,
        "forecast_horizon_days": metadata.forecast_horizon_days,
        "ordered_feature_names": list(metadata.feature_names),
        "training_date_range": _date_range(splits.train.dates),
        "validation_date_range": _date_range(splits.validation.dates),
        "test_date_range": _date_range(splits.test.dates),
        "selected_latitude": float(selected["latitude"].item()),
        "selected_longitude": float(selected["longitude"].item()),
        "validation_metrics": asdict(validation.metrics),
        "test_metrics": asdict(test.metrics),
        "artifact_sha256": artifact_digest,
        "creation_timestamp": datetime.now(timezone.utc).isoformat(),
        "package_versions": _package_versions(),
        "input_datasets": input_datasets,
        "build_parameters": {
            "requested_latitude": config.latitude,
            "requested_longitude": config.longitude,
            "radiation_accumulation_seconds": (
                config.radiation_accumulation_seconds
            ),
            "timezone": config.timezone_name,
            "max_distance_degrees": config.max_distance_degrees,
            "train_fraction": config.train_fraction,
            "validation_fraction": config.validation_fraction,
            "fit_partition": "train_only",
        },
    }
    _write_json_atomic(outputs.manifest_path, manifest)
    _write_text_atomic(
        outputs.checksum_path,
        f"{artifact_digest}  {outputs.artifact_path.name}\n",
    )

    if not verify_artifact_checksum(outputs.artifact_path, outputs.checksum_path):
        raise RuntimeError("saved artifact checksum verification failed")
    loaded = load_model_artifact(
        outputs.artifact_path,
        expected_contract=contract,
    )
    loaded_prediction = loaded.predict_one(
        reference_row,
        expected_contract=contract,
    ).prediction
    if not np.isclose(expected_prediction, loaded_prediction, rtol=0.0, atol=1e-12):
        raise RuntimeError("reloaded artifact prediction does not match fitted model")

    return outputs


def calculate_file_sha256(path: str | PathLike[str]) -> str:
    """Calculate the SHA-256 digest of one existing file."""

    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"file does not exist: {source}")
    digest = sha256()
    with source.open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_artifact_checksum(
    artifact_path: str | PathLike[str],
    checksum_path: str | PathLike[str],
) -> bool:
    """Verify a standard SHA-256 sidecar against its named artifact."""

    artifact = Path(artifact_path)
    checksum = Path(checksum_path)
    if not checksum.is_file():
        raise FileNotFoundError(f"checksum file does not exist: {checksum}")
    fields = checksum.read_text(encoding="utf-8").strip().split()
    if len(fields) != 2 or fields[1] != artifact.name:
        raise ValueError("checksum file must contain '<sha256>  <artifact filename>'")
    expected_digest = fields[0].lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
        raise ValueError("checksum file contains an invalid SHA-256 digest")
    return hmac.compare_digest(expected_digest, calculate_file_sha256(artifact))


def _validate_config(config: object) -> None:
    if not isinstance(config, DeploymentBuildConfig):
        raise TypeError("config must be a DeploymentBuildConfig instance")
    if not config.era5_paths:
        raise ValueError("at least one ERA5 input path is required")
    if len(set(config.era5_paths)) != len(config.era5_paths):
        raise ValueError("ERA5 input paths must not contain duplicates")
    for path in config.era5_paths:
        if not isinstance(path, Path):
            raise TypeError("era5_paths must contain pathlib.Path values")
        if not path.is_file():
            raise FileNotFoundError(f"ERA5 input does not exist: {path}")
    if not isinstance(config.output_root, Path):
        raise TypeError("output_root must be a pathlib.Path")
    if not _MODEL_VERSION_PATTERN.fullmatch(config.model_version):
        raise ValueError("model_version contains unsupported filename characters")
    if not isinstance(config.timezone_name, str) or not config.timezone_name.strip():
        raise ValueError("timezone_name must be a non-empty string")


def _ensure_outputs_do_not_exist(outputs: DeploymentBuildOutputs) -> None:
    existing = [
        path
        for path in (
            outputs.artifact_path,
            outputs.manifest_path,
            outputs.checksum_path,
        )
        if path.exists()
    ]
    if existing:
        raise FileExistsError(f"deployment outputs already exist: {existing}")


def _date_range(dates: object) -> dict[str, str]:
    return {
        "start": dates.iloc[0].isoformat(),
        "end": dates.iloc[-1].isoformat(),
    }


def _package_versions() -> dict[str, str]:
    versions = {"python": platform.python_version()}
    for package_name in _PACKAGE_NAMES:
        try:
            versions[package_name] = version(package_name)
        except PackageNotFoundError:
            continue
    return versions


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    _write_text_atomic(
        path,
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
    )


def _write_text_atomic(path: Path, text: str) -> None:
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(text)
            temporary_file.flush()
            fsync(temporary_file.fileno())
        replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _parse_args() -> DeploymentBuildConfig:
    parser = argparse.ArgumentParser(
        description="Build the trusted HeatIQ D+1 air-temperature artifact.",
    )
    parser.add_argument(
        "--era5-file",
        action="append",
        required=True,
        type=Path,
        dest="era5_paths",
    )
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--latitude", required=True, type=float)
    parser.add_argument("--longitude", required=True, type=float)
    parser.add_argument(
        "--radiation-accumulation-seconds",
        required=True,
        type=float,
    )
    parser.add_argument("--model-version", default=DEFAULT_MODEL_VERSION)
    parser.add_argument("--timezone", default="Asia/Kolkata", dest="timezone_name")
    parser.add_argument("--max-distance-degrees", type=float)
    arguments = parser.parse_args()
    return DeploymentBuildConfig(
        era5_paths=tuple(arguments.era5_paths),
        output_root=arguments.output_root,
        latitude=arguments.latitude,
        longitude=arguments.longitude,
        radiation_accumulation_seconds=arguments.radiation_accumulation_seconds,
        model_version=arguments.model_version,
        timezone_name=arguments.timezone_name,
        max_distance_degrees=arguments.max_distance_degrees,
    )


def main() -> None:
    """Run the explicit command-line deployment build."""

    outputs = build_d1_max_air_temperature_artifact(_parse_args())
    print(outputs.artifact_path)
    print(outputs.manifest_path)
    print(outputs.checksum_path)


if __name__ == "__main__":
    main()
