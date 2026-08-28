"""Persistence for trusted, fitted HeatIQ regression model artifacts.

Artifacts use Python pickle and must therefore only be loaded from trusted
sources. Load-time validation protects the HeatIQ inference contract; it does
not make an untrusted pickle safe to deserialize.
"""

from dataclasses import dataclass
from datetime import datetime
from os import PathLike, fsync, replace
from pathlib import Path
import pickle
from tempfile import NamedTemporaryFile

import pandas as pd
from sklearn.exceptions import NotFittedError
from sklearn.utils.validation import check_is_fitted

from ml.inference.predict import (
    ModelMetadata,
    PredictionResult,
    _validate_estimator_schema,
    _validate_metadata,
    predict_one,
)


ARTIFACT_FORMAT_VERSION = 1
AIR_TEMPERATURE_TARGET = "target_temperature_max_c_d1"
AIR_TEMPERATURE_UNIT = "degC"


@dataclass(frozen=True)
class ArtifactContract:
    """Expected target semantics for fail-closed artifact loading and use."""

    target_name: str
    target_unit: str
    forecast_horizon_days: int

    def __post_init__(self) -> None:
        _validate_contract(self)


def _validate_contract(contract: object) -> None:
    if not isinstance(contract, ArtifactContract):
        raise TypeError("expected_contract must be an ArtifactContract instance")
    if not isinstance(contract.target_name, str) or not contract.target_name.strip():
        raise ValueError("contract target_name must be a non-empty string")
    if not isinstance(contract.target_unit, str) or not contract.target_unit.strip():
        raise ValueError("contract target_unit must be a non-empty string")
    if (
        isinstance(contract.forecast_horizon_days, bool)
        or not isinstance(contract.forecast_horizon_days, int)
        or contract.forecast_horizon_days <= 0
    ):
        raise ValueError("contract forecast_horizon_days must be a positive integer")


D1_MAX_AIR_TEMPERATURE_CONTRACT = ArtifactContract(
    target_name=AIR_TEMPERATURE_TARGET,
    target_unit=AIR_TEMPERATURE_UNIT,
    forecast_horizon_days=1,
)


@dataclass(frozen=True)
class ModelArtifact:
    """A fitted estimator and its immutable, explicit target semantics."""

    estimator: object
    metadata: ModelMetadata
    model_version: str = "1"
    format_version: int = ARTIFACT_FORMAT_VERSION

    def __post_init__(self) -> None:
        _validate_artifact(self)

    def predict_one(
        self,
        feature_row: pd.DataFrame,
        *,
        feature_date: datetime | None = None,
        expected_contract: ArtifactContract | None = None,
    ) -> PredictionResult:
        """Run strict inference, optionally requiring expected target semantics."""

        if expected_contract is not None:
            validate_artifact_contract(self, expected_contract)

        return predict_one(
            self.estimator,
            feature_row,
            self.metadata,
            feature_date=feature_date,
        )

    @property
    def target_unit(self) -> str:
        """Return the validated prediction unit stored in model metadata."""

        target_unit = self.metadata.target_unit
        if target_unit is None:  # Guard for objects bypassing normal construction.
            raise ValueError("artifact target_unit is required")
        return target_unit


def save_model_artifact(
    artifact: ModelArtifact,
    path: str | PathLike[str],
) -> Path:
    """Atomically persist one validated model artifact and return its path."""

    _validate_artifact(artifact)
    destination = _validated_path(path)
    if not destination.parent.exists():
        raise FileNotFoundError(
            f"artifact parent directory does not exist: {destination.parent}"
        )
    if destination.exists() and destination.is_dir():
        raise IsADirectoryError(f"artifact path is a directory: {destination}")

    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            pickle.dump(artifact, temporary_file, protocol=pickle.HIGHEST_PROTOCOL)
            temporary_file.flush()
            fsync(temporary_file.fileno())
        replace(temporary_path, destination)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()

    return destination


def load_model_artifact(
    path: str | PathLike[str],
    *,
    expected_contract: ArtifactContract | None = None,
) -> ModelArtifact:
    """Load and validate a model artifact from a trusted local file."""

    source = _validated_path(path)
    if not source.is_file():
        raise FileNotFoundError(f"model artifact does not exist: {source}")

    try:
        with source.open("rb") as artifact_file:
            artifact = pickle.load(artifact_file)
    except (pickle.UnpicklingError, EOFError, AttributeError, ImportError) as exc:
        raise ValueError(f"model artifact could not be loaded: {source}") from exc

    if not isinstance(artifact, ModelArtifact):
        raise ValueError("model artifact has an unsupported payload")
    _validate_artifact(artifact)
    if expected_contract is not None:
        validate_artifact_contract(artifact, expected_contract)
    return artifact


def validate_artifact_contract(
    artifact: ModelArtifact,
    expected_contract: ArtifactContract,
) -> None:
    """Fail if an artifact's explicit semantics differ from expectations."""

    _validate_artifact(artifact)
    _validate_contract(expected_contract)
    actual = ArtifactContract(
        target_name=artifact.metadata.target_name or "",
        target_unit=artifact.metadata.target_unit or "",
        forecast_horizon_days=artifact.metadata.forecast_horizon_days,
    )
    if actual != expected_contract:
        raise ValueError(
            "model artifact contract mismatch; "
            f"expected={expected_contract!r}, actual={actual!r}"
        )


def _validate_artifact(artifact: object) -> None:
    if not isinstance(artifact, ModelArtifact):
        raise TypeError("artifact must be a ModelArtifact instance")
    if (
        isinstance(artifact.format_version, bool)
        or not isinstance(artifact.format_version, int)
        or artifact.format_version != ARTIFACT_FORMAT_VERSION
    ):
        raise ValueError(
            "unsupported model artifact format version: "
            f"{artifact.format_version!r}"
        )

    _validate_metadata(artifact.metadata)
    if artifact.metadata.target_name is None:
        raise ValueError("artifact target_name is required")
    if artifact.metadata.target_unit is None:
        raise ValueError("artifact target_unit is required")
    _validate_contract(
        ArtifactContract(
            target_name=artifact.metadata.target_name,
            target_unit=artifact.metadata.target_unit,
            forecast_horizon_days=artifact.metadata.forecast_horizon_days,
        )
    )
    if not isinstance(artifact.model_version, str) or not artifact.model_version.strip():
        raise ValueError("artifact model_version must be a non-empty string")

    predict = getattr(artifact.estimator, "predict", None)
    if not callable(predict):
        raise TypeError("artifact estimator must expose a callable predict method")
    try:
        check_is_fitted(artifact.estimator)
    except (NotFittedError, TypeError) as exc:
        raise ValueError("artifact estimator must be fitted") from exc
    _validate_estimator_schema(
        artifact.estimator,
        artifact.metadata.feature_names,
    )


def _validated_path(path: str | PathLike[str]) -> Path:
    if not isinstance(path, (str, PathLike)):
        raise TypeError("artifact path must be a string or path-like object")
    if isinstance(path, str) and not path.strip():
        raise ValueError("artifact path must not be empty")
    return Path(path)
