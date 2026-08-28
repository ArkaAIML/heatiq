"""Reusable regression evaluation utilities for ML model experiments."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


@dataclass(frozen=True)
class RegressionMetrics:
    """Standard regression metrics for one evaluated partition."""

    mae: float
    rmse: float
    r2: float


@dataclass(frozen=True)
class EvaluatedPredictions:
    """Predictions and metrics for one supervised partition."""

    predictions: pd.Series
    metrics: RegressionMetrics


@dataclass(frozen=True)
class BaselineEvaluation:
    """Separate validation and test results for one baseline."""

    name: str
    validation: EvaluatedPredictions
    test: EvaluatedPredictions


def calculate_regression_metrics(
    y_true: pd.Series | np.ndarray,
    y_pred: pd.Series | np.ndarray,
) -> RegressionMetrics:
    """Calculate MAE, RMSE, and R-squared for finite 1D numeric values."""

    actual = _validated_vector(y_true, "y_true")
    predicted = _validated_vector(y_pred, "y_pred")
    if len(actual) != len(predicted):
        raise ValueError("y_true and y_pred must have equal lengths")
    if len(actual) < 2:
        raise ValueError("at least two observations are required for R-squared")

    return RegressionMetrics(
        mae=float(mean_absolute_error(actual, predicted)),
        rmse=float(np.sqrt(mean_squared_error(actual, predicted))),
        r2=float(r2_score(actual, predicted)),
    )


def evaluate_predictions(
    y_true: pd.Series | np.ndarray,
    y_pred: pd.Series | np.ndarray,
) -> EvaluatedPredictions:
    """Return normalized predictions together with regression metrics."""

    predicted = _validated_vector(y_pred, "y_pred")
    metrics = calculate_regression_metrics(y_true, predicted)
    return EvaluatedPredictions(
        predictions=pd.Series(predicted.copy(), name="prediction"),
        metrics=metrics,
    )


def _validated_vector(
    values: pd.Series | np.ndarray,
    name: str,
) -> np.ndarray:
    array = np.asarray(values)
    if array.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    if not np.issubdtype(array.dtype, np.number) or np.issubdtype(
        array.dtype,
        np.bool_,
    ):
        raise ValueError(f"{name} must be numeric")
    if not bool(np.isfinite(array).all()):
        raise ValueError(f"{name} must contain only finite values")
    return array
