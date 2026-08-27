"""CPU-friendly XGBoost regression training on chronological splits.

The implementation is target-agnostic. It trains one fixed configuration and
uses validation only for early stopping; test data is evaluated once after the
best boosting iteration has been selected.
"""

from dataclasses import dataclass
from numbers import Integral
from time import perf_counter

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from ml.models.evaluate import EvaluatedPredictions, evaluate_predictions
from ml.preprocessing.supervised import ChronologicalSplits, SupervisedPartition


@dataclass(frozen=True)
class XGBoostEvaluation:
    """Held-out metrics and descriptive information for one XGBoost fit."""

    validation: EvaluatedPredictions
    test: EvaluatedPredictions
    best_iteration: int
    feature_importance: pd.DataFrame
    training_duration_seconds: float


def train_and_evaluate_xgboost(
    splits: ChronologicalSplits,
    *,
    random_seed: int = 42,
) -> XGBoostEvaluation:
    """Train once on train, early-stop on validation, and evaluate test once."""

    _validate_splits(splits)
    seed = _validate_random_seed(random_seed)
    model = _build_model(seed)

    training_started = perf_counter()
    model.fit(
        splits.train.features,
        splits.train.target,
        eval_set=[(splits.validation.features, splits.validation.target)],
        verbose=False,
    )
    training_duration_seconds = perf_counter() - training_started

    best_iteration = int(model.best_iteration)
    validation_predictions = model.predict(splits.validation.features)
    validation_evaluation = evaluate_predictions(
        splits.validation.target,
        validation_predictions,
    )

    feature_importance = _feature_importance_frame(
        model,
        feature_columns=list(splits.train.features.columns),
    )

    # XGBRegressor.predict() automatically uses best_iteration when the model
    # was fitted with early stopping. Test is intentionally predicted last.
    test_predictions = model.predict(splits.test.features)
    test_evaluation = evaluate_predictions(
        splits.test.target,
        test_predictions,
    )

    return XGBoostEvaluation(
        validation=validation_evaluation,
        test=test_evaluation,
        best_iteration=best_iteration,
        feature_importance=feature_importance,
        training_duration_seconds=float(training_duration_seconds),
    )


def _build_model(random_seed: int) -> XGBRegressor:
    return XGBRegressor(
        objective="reg:squarederror",
        n_estimators=500,
        learning_rate=0.05,
        max_depth=3,
        min_child_weight=5,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        reg_alpha=0.0,
        tree_method="hist",
        eval_metric="rmse",
        early_stopping_rounds=30,
        importance_type="gain",
        random_state=random_seed,
        n_jobs=1,
        verbosity=0,
    )


def _feature_importance_frame(
    model: XGBRegressor,
    *,
    feature_columns: list[str],
) -> pd.DataFrame:
    importance = np.asarray(model.feature_importances_, dtype=float)
    if importance.ndim != 1 or len(importance) != len(feature_columns):
        raise ValueError("XGBoost feature importance does not match input features")
    if not bool(np.isfinite(importance).all()) or bool((importance < 0).any()):
        raise ValueError("XGBoost feature importance must be finite and nonnegative")

    return (
        pd.DataFrame(
            {
                "feature": feature_columns,
                "importance_gain": importance,
            }
        )
        .sort_values("importance_gain", ascending=False, kind="stable")
        .reset_index(drop=True)
    )


def _validate_splits(splits: ChronologicalSplits) -> None:
    if not isinstance(splits, ChronologicalSplits):
        raise TypeError("splits must be a ChronologicalSplits instance")

    expected_columns = list(splits.train.features.columns)
    if not expected_columns:
        raise ValueError("training partition must contain model features")
    for name, partition in (
        ("train", splits.train),
        ("validation", splits.validation),
        ("test", splits.test),
    ):
        _validate_partition(partition, name)
        if list(partition.features.columns) != expected_columns:
            raise ValueError(
                f"{name} feature columns must match training columns and order"
            )


def _validate_partition(partition: SupervisedPartition, name: str) -> None:
    if not isinstance(partition, SupervisedPartition):
        raise TypeError(f"{name} must be a SupervisedPartition")
    row_count = len(partition.features)
    if row_count < 2:
        raise ValueError(f"{name} partition must contain at least two rows")
    if len(partition.target) != row_count or len(partition.dates) != row_count:
        raise ValueError(f"{name} partition components must have equal lengths")

    for column in partition.features.columns:
        if not pd.api.types.is_numeric_dtype(partition.features[column]) or pd.api.types.is_bool_dtype(
            partition.features[column]
        ):
            raise ValueError(f"{name} feature must be numeric: {column!r}")
    if partition.features.isna().any().any():
        raise ValueError(f"{name} features contain missing values")
    if not bool(np.isfinite(partition.features.to_numpy()).all()):
        raise ValueError(f"{name} features contain non-finite values")
    if not pd.api.types.is_numeric_dtype(partition.target) or pd.api.types.is_bool_dtype(
        partition.target
    ):
        raise ValueError(f"{name} target must be numeric")
    if partition.target.isna().any():
        raise ValueError(f"{name} target contains missing values")
    if not bool(np.isfinite(partition.target.to_numpy()).all()):
        raise ValueError(f"{name} target contains non-finite values")


def _validate_random_seed(random_seed: object) -> int:
    if isinstance(random_seed, bool) or not isinstance(random_seed, Integral):
        raise ValueError("random_seed must be an integer")
    return int(random_seed)
