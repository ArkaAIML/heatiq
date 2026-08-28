"""Strict single-row inference for fitted regression estimators."""

from dataclasses import dataclass
from datetime import datetime
from numbers import Integral

import numpy as np
import pandas as pd
from sklearn.exceptions import NotFittedError


@dataclass(frozen=True)
class ModelMetadata:
    """ML-internal metadata required to validate an inference request."""

    model_name: str
    feature_names: tuple[str, ...]
    forecast_horizon_days: int
    target_name: str | None = None


@dataclass(frozen=True)
class PredictionResult:
    """One regression prediction with model and forecast context."""

    prediction: float
    model_name: str
    forecast_horizon_days: int
    feature_date: datetime | None
    target_name: str | None


def predict_one(
    estimator: object,
    feature_row: pd.DataFrame,
    metadata: ModelMetadata,
    *,
    feature_date: datetime | None = None,
) -> PredictionResult:
    """Predict one row with an already-fitted estimator without mutating input."""

    _validate_metadata(metadata)
    _validate_feature_date(feature_date)
    validated_row = _validated_feature_row(feature_row, metadata)
    _validate_estimator_schema(estimator, metadata.feature_names)

    predict = getattr(estimator, "predict", None)
    if not callable(predict):
        raise TypeError("estimator must expose a callable predict method")

    try:
        raw_prediction = predict(validated_row)
    except NotFittedError as exc:
        raise RuntimeError("estimator must be fitted before inference") from exc

    prediction = _validated_prediction(raw_prediction)
    return PredictionResult(
        prediction=prediction,
        model_name=metadata.model_name,
        forecast_horizon_days=metadata.forecast_horizon_days,
        feature_date=feature_date,
        target_name=metadata.target_name,
    )


def _validate_metadata(metadata: ModelMetadata) -> None:
    if not isinstance(metadata, ModelMetadata):
        raise TypeError("metadata must be a ModelMetadata instance")
    if not isinstance(metadata.model_name, str) or not metadata.model_name.strip():
        raise ValueError("model_name must be a non-empty string")
    if not isinstance(metadata.feature_names, tuple) or not metadata.feature_names:
        raise ValueError("feature_names must be a non-empty tuple")
    if any(not isinstance(name, str) or not name.strip() for name in metadata.feature_names):
        raise ValueError("feature_names must contain non-empty strings")
    if len(set(metadata.feature_names)) != len(metadata.feature_names):
        raise ValueError("feature_names must not contain duplicates")
    if "date" in metadata.feature_names:
        raise ValueError("date cannot be a model feature")
    if isinstance(metadata.forecast_horizon_days, bool) or not isinstance(
        metadata.forecast_horizon_days,
        Integral,
    ):
        raise ValueError("forecast_horizon_days must be a positive integer")
    if metadata.forecast_horizon_days <= 0:
        raise ValueError("forecast_horizon_days must be a positive integer")
    if metadata.target_name is not None:
        if not isinstance(metadata.target_name, str) or not metadata.target_name.strip():
            raise ValueError("target_name must be a non-empty string or None")
        if metadata.target_name in metadata.feature_names:
            raise ValueError("target_name cannot be a model feature")


def _validate_feature_date(feature_date: datetime | None) -> None:
    if feature_date is not None and not isinstance(feature_date, datetime):
        raise TypeError("feature_date must be a datetime or None")


def _validated_feature_row(
    feature_row: pd.DataFrame,
    metadata: ModelMetadata,
) -> pd.DataFrame:
    if not isinstance(feature_row, pd.DataFrame):
        raise TypeError("feature_row must be a pandas DataFrame")
    if len(feature_row) != 1:
        raise ValueError("feature_row must contain exactly one row")

    actual_columns = tuple(feature_row.columns)
    if actual_columns != metadata.feature_names:
        missing = [name for name in metadata.feature_names if name not in actual_columns]
        extra = [name for name in actual_columns if name not in metadata.feature_names]
        if missing or extra:
            raise ValueError(
                "feature columns must match metadata exactly; "
                f"missing={missing}, extra={extra}"
            )
        raise ValueError("feature columns must match metadata order")

    nonnumeric = [
        column
        for column in feature_row.columns
        if not pd.api.types.is_numeric_dtype(feature_row[column])
        or pd.api.types.is_bool_dtype(feature_row[column])
    ]
    if nonnumeric:
        raise ValueError(f"feature_row contains nonnumeric columns: {nonnumeric}")
    if feature_row.isna().any().any():
        raise ValueError("feature_row contains missing values")
    if not bool(np.isfinite(feature_row.to_numpy()).all()):
        raise ValueError("feature_row contains non-finite values")

    return feature_row.copy(deep=True)


def _validate_estimator_schema(
    estimator: object,
    expected_feature_names: tuple[str, ...],
) -> None:
    estimator_feature_names = getattr(estimator, "feature_names_in_", None)
    if estimator_feature_names is not None:
        if tuple(estimator_feature_names) != expected_feature_names:
            raise ValueError("model metadata feature names do not match estimator schema")

    estimator_feature_count = getattr(estimator, "n_features_in_", None)
    if estimator_feature_count is not None:
        if isinstance(estimator_feature_count, bool) or not isinstance(
            estimator_feature_count,
            Integral,
        ):
            raise ValueError("estimator feature count is invalid")
        if int(estimator_feature_count) != len(expected_feature_names):
            raise ValueError("model metadata feature count does not match estimator schema")


def _validated_prediction(raw_prediction: object) -> float:
    prediction = np.asarray(raw_prediction)
    if prediction.ndim != 1 or len(prediction) != 1:
        raise ValueError("estimator must return exactly one prediction")
    if not np.issubdtype(prediction.dtype, np.number) or np.issubdtype(
        prediction.dtype,
        np.bool_,
    ):
        raise ValueError("estimator prediction must be numeric")
    if not bool(np.isfinite(prediction).all()):
        raise ValueError("estimator prediction must be finite")
    return float(prediction[0])
