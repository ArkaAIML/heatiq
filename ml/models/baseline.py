"""Simple reusable regression baselines evaluated on chronological splits."""

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from ml.models.evaluate import (
    BaselineEvaluation,
    evaluate_predictions,
)
from ml.preprocessing.supervised import ChronologicalSplits, SupervisedPartition


def persistence_predictions(
    partition: SupervisedPartition,
    *,
    source_column: str,
) -> pd.Series:
    """Predict a future target using its current-row source feature."""

    _validate_partition(partition, "partition")
    if not isinstance(source_column, str) or not source_column.strip():
        raise ValueError("source_column must be a non-empty string")
    if source_column not in partition.features.columns:
        raise ValueError(
            f"persistence source column does not exist: {source_column!r}"
        )

    values = partition.features[source_column]
    _validate_numeric_frame(values.to_frame(), "persistence source")
    return values.copy(deep=True).reset_index(drop=True).rename("prediction")


def evaluate_persistence_baseline(
    splits: ChronologicalSplits,
    *,
    source_column: str,
) -> BaselineEvaluation:
    """Evaluate persistence independently on validation and test data."""

    _validate_splits(splits)
    validation_predictions = persistence_predictions(
        splits.validation,
        source_column=source_column,
    )
    test_predictions = persistence_predictions(
        splits.test,
        source_column=source_column,
    )
    return BaselineEvaluation(
        name="persistence",
        validation=evaluate_predictions(
            splits.validation.target,
            validation_predictions,
        ),
        test=evaluate_predictions(
            splits.test.target,
            test_predictions,
        ),
    )


def evaluate_linear_regression_baseline(
    splits: ChronologicalSplits,
) -> BaselineEvaluation:
    """Fit Linear Regression on train only, then evaluate held-out data."""

    _validate_splits(splits)
    model = LinearRegression()
    model.fit(splits.train.features, splits.train.target)

    validation_predictions = model.predict(splits.validation.features)
    test_predictions = model.predict(splits.test.features)
    return BaselineEvaluation(
        name="linear_regression",
        validation=evaluate_predictions(
            splits.validation.target,
            validation_predictions,
        ),
        test=evaluate_predictions(
            splits.test.target,
            test_predictions,
        ),
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
    if row_count == 0:
        raise ValueError(f"{name} partition cannot be empty")
    if len(partition.target) != row_count or len(partition.dates) != row_count:
        raise ValueError(f"{name} partition components must have equal lengths")
    _validate_numeric_frame(partition.features, f"{name} features")
    _validate_numeric_frame(partition.target.to_frame(), f"{name} target")


def _validate_numeric_frame(frame: pd.DataFrame, name: str) -> None:
    nonnumeric = [
        column
        for column in frame.columns
        if not pd.api.types.is_numeric_dtype(frame[column])
        or pd.api.types.is_bool_dtype(frame[column])
    ]
    if nonnumeric:
        raise ValueError(f"{name} contains nonnumeric columns: {nonnumeric}")
    if frame.isna().any().any():
        raise ValueError(f"{name} contains missing values")
    if not bool(np.isfinite(frame.to_numpy()).all()):
        raise ValueError(f"{name} contains non-finite values")
