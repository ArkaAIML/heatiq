"""ML-internal prediction and model artifact interfaces."""

from ml.inference.artifact import (
    AIR_TEMPERATURE_TARGET,
    AIR_TEMPERATURE_UNIT,
    ARTIFACT_FORMAT_VERSION,
    D1_MAX_AIR_TEMPERATURE_CONTRACT,
    ArtifactContract,
    ModelArtifact,
    load_model_artifact,
    save_model_artifact,
    validate_artifact_contract,
)
from ml.inference.predict import ModelMetadata, PredictionResult, predict_one

__all__ = [
    "AIR_TEMPERATURE_TARGET",
    "AIR_TEMPERATURE_UNIT",
    "ARTIFACT_FORMAT_VERSION",
    "D1_MAX_AIR_TEMPERATURE_CONTRACT",
    "ArtifactContract",
    "ModelArtifact",
    "ModelMetadata",
    "PredictionResult",
    "load_model_artifact",
    "predict_one",
    "save_model_artifact",
    "validate_artifact_contract",
]
