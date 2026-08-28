"""Generic supervised-target construction and chronological data splitting.

This module is independent of any specific thermal metric. The target source
is supplied by the caller so an agreed hazard metric can be substituted later
without redesigning the pipeline.
"""

from dataclasses import dataclass
import math
from numbers import Integral, Real

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SupervisedPartition:
    """Dates, model features, and target for one chronological partition."""

    dates: pd.Series
    features: pd.DataFrame
    target: pd.Series


@dataclass(frozen=True)
class ChronologicalSplits:
    """Leakage-safe train, validation, and test partitions."""

    train: SupervisedPartition
    validation: SupervisedPartition
    test: SupervisedPartition
    target_column: str
    horizon_days: int
    purged_boundary_rows: int


def add_future_target(
    feature_frame: pd.DataFrame,
    *,
    source_column: str,
    horizon_days: int = 1,
    target_name: str | None = None,
) -> pd.DataFrame:
    """Add a generic future target aligned by chronological daily rows.

    For a row dated D, the target is the source value at D +
    ``horizon_days``. Dates must therefore be unique, chronological, and
    consecutive. The final horizon rows, whose future labels are unavailable,
    are explicitly removed and the loss is recorded in ``DataFrame.attrs``.
    """

    _validate_frame_type(feature_frame)
    _validate_daily_dates(feature_frame, date_column="date")
    horizon = _validate_horizon(horizon_days)

    if not isinstance(source_column, str) or not source_column.strip():
        raise ValueError("source_column must be a non-empty string")
    if source_column not in feature_frame.columns:
        raise ValueError(f"source column does not exist: {source_column!r}")
    _validate_numeric_series(feature_frame[source_column], source_column)

    if target_name is None:
        resolved_target_name = f"target_{source_column}_d{horizon}"
    elif isinstance(target_name, str) and target_name.strip():
        resolved_target_name = target_name
    else:
        raise ValueError("target_name must be a non-empty string or None")

    if resolved_target_name in feature_frame.columns:
        raise ValueError(
            f"target column already exists and will not be overwritten: "
            f"{resolved_target_name!r}"
        )
    if len(feature_frame) <= horizon:
        raise ValueError(
            "feature frame must contain more rows than the requested horizon"
        )

    source_attrs = feature_frame.attrs.copy()
    labeled = feature_frame.copy(deep=True)
    labeled[resolved_target_name] = labeled[source_column].shift(-horizon)
    labeled = labeled.iloc[:-horizon].reset_index(drop=True)
    if labeled[resolved_target_name].isna().any():
        raise ValueError("future target contains unexpected missing values")

    labeled.attrs = source_attrs | {
        "target_source_column": source_column,
        "target_column": resolved_target_name,
        "target_horizon_days": horizon,
        "rows_dropped_without_future_target": horizon,
    }
    return labeled


def chronological_split(
    frame: pd.DataFrame,
    *,
    target_column: str,
    train_fraction: float = 0.70,
    validation_fraction: float = 0.15,
    date_column: str = "date",
    horizon_days: int | None = None,
) -> ChronologicalSplits:
    """Create ordered train/validation/test data with horizon-sized purges.

    A purge of ``horizon_days`` rows is removed from the end of the nominal
    training and validation regions. This ensures that neither region uses a
    label observed on or after the first feature date of the following
    partition. No rows are shuffled.
    """

    _validate_frame_type(frame)
    _validate_daily_dates(frame, date_column=date_column)
    if not isinstance(target_column, str) or not target_column.strip():
        raise ValueError("target_column must be a non-empty string")
    if target_column not in frame.columns:
        raise ValueError(f"target column does not exist: {target_column!r}")
    if target_column == date_column:
        raise ValueError("target_column and date_column must be different")

    metadata_target = frame.attrs.get("target_column")
    if metadata_target is not None and metadata_target != target_column:
        raise ValueError(
            "target_column does not match target metadata: "
            f"{target_column!r} != {metadata_target!r}"
        )

    resolved_horizon = _resolve_split_horizon(frame, horizon_days)
    train_ratio = _validate_fraction(train_fraction, "train_fraction")
    validation_ratio = _validate_fraction(
        validation_fraction,
        "validation_fraction",
    )
    if train_ratio + validation_ratio >= 1.0:
        raise ValueError("train_fraction + validation_fraction must be less than 1")

    _validate_numeric_series(frame[target_column], target_column)
    feature_columns = [
        column
        for column in frame.columns
        if column not in {date_column, target_column}
    ]
    if not feature_columns:
        raise ValueError("at least one model feature column is required")
    for column in feature_columns:
        _validate_numeric_series(frame[column], column)

    row_count = len(frame)
    train_boundary = math.floor(row_count * train_ratio)
    validation_boundary = math.floor(
        row_count * (train_ratio + validation_ratio)
    )
    train_end = train_boundary - resolved_horizon
    validation_end = validation_boundary - resolved_horizon

    if (
        train_end <= 0
        or validation_end <= train_boundary
        or validation_boundary >= row_count
    ):
        raise ValueError(
            "insufficient rows for non-empty chronological partitions after purge"
        )

    train = _build_partition(
        frame.iloc[:train_end],
        feature_columns=feature_columns,
        target_column=target_column,
        date_column=date_column,
    )
    validation = _build_partition(
        frame.iloc[train_boundary:validation_end],
        feature_columns=feature_columns,
        target_column=target_column,
        date_column=date_column,
    )
    test = _build_partition(
        frame.iloc[validation_boundary:],
        feature_columns=feature_columns,
        target_column=target_column,
        date_column=date_column,
    )

    _validate_partition_boundaries(
        train,
        validation,
        test,
        horizon_days=resolved_horizon,
    )
    return ChronologicalSplits(
        train=train,
        validation=validation,
        test=test,
        target_column=target_column,
        horizon_days=resolved_horizon,
        purged_boundary_rows=2 * resolved_horizon,
    )


def _build_partition(
    frame: pd.DataFrame,
    *,
    feature_columns: list[str],
    target_column: str,
    date_column: str,
) -> SupervisedPartition:
    return SupervisedPartition(
        dates=frame[date_column].copy(deep=True).reset_index(drop=True),
        features=frame[feature_columns].copy(deep=True).reset_index(drop=True),
        target=frame[target_column].copy(deep=True).reset_index(drop=True),
    )


def _resolve_split_horizon(
    frame: pd.DataFrame,
    horizon_days: int | None,
) -> int:
    metadata_horizon = frame.attrs.get("target_horizon_days")
    if horizon_days is None:
        if metadata_horizon is None:
            raise ValueError(
                "horizon_days is required when target metadata is unavailable"
            )
        return _validate_horizon(metadata_horizon)

    resolved = _validate_horizon(horizon_days)
    if metadata_horizon is not None:
        recorded = _validate_horizon(metadata_horizon)
        if recorded != resolved:
            raise ValueError(
                "horizon_days does not match target metadata: "
                f"{resolved} != {recorded}"
            )
    return resolved


def _validate_partition_boundaries(
    train: SupervisedPartition,
    validation: SupervisedPartition,
    test: SupervisedPartition,
    *,
    horizon_days: int,
) -> None:
    if not (
        train.dates.iloc[-1] < validation.dates.iloc[0]
        and validation.dates.iloc[-1] < test.dates.iloc[0]
    ):
        raise ValueError("chronological partition dates overlap")

    horizon = pd.Timedelta(days=horizon_days)
    if train.dates.iloc[-1] + horizon >= validation.dates.iloc[0]:
        raise ValueError("training target boundary crosses into validation")
    if validation.dates.iloc[-1] + horizon >= test.dates.iloc[0]:
        raise ValueError("validation target boundary crosses into test")


def _validate_frame_type(frame: pd.DataFrame) -> None:
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame")
    if frame.empty:
        raise ValueError("frame cannot be empty")


def _validate_daily_dates(frame: pd.DataFrame, *, date_column: str) -> None:
    if not isinstance(date_column, str) or not date_column.strip():
        raise ValueError("date_column must be a non-empty string")
    if date_column not in frame.columns:
        raise ValueError(f"date column does not exist: {date_column!r}")

    dates = frame[date_column]
    if not pd.api.types.is_datetime64_any_dtype(dates):
        raise ValueError(f"{date_column} must use a datetime64 dtype")
    if dates.isna().any():
        raise ValueError(f"{date_column} contains missing values")
    if not dates.is_unique:
        raise ValueError(f"{date_column} values must be unique")
    if not dates.is_monotonic_increasing:
        raise ValueError(f"{date_column} values must be chronological")
    if len(dates) > 1:
        differences = dates.diff().iloc[1:]
        if not bool((differences == pd.Timedelta(days=1)).all()):
            raise ValueError(f"{date_column} values must be consecutive daily dates")


def _validate_numeric_series(series: pd.Series, name: str) -> None:
    if not pd.api.types.is_numeric_dtype(series):
        raise ValueError(f"{name} must be numeric")
    if series.isna().any():
        raise ValueError(f"{name} contains missing values")
    if not bool(np.isfinite(series.to_numpy()).all()):
        raise ValueError(f"{name} contains non-finite values")


def _validate_horizon(horizon_days: object) -> int:
    if isinstance(horizon_days, bool) or not isinstance(horizon_days, Integral):
        raise ValueError("horizon_days must be an integer greater than zero")
    resolved = int(horizon_days)
    if resolved <= 0:
        raise ValueError("horizon_days must be an integer greater than zero")
    return resolved


def _validate_fraction(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a number strictly between 0 and 1")
    resolved = float(value)
    if not np.isfinite(resolved) or not 0.0 < resolved < 1.0:
        raise ValueError(f"{name} must be a number strictly between 0 and 1")
    return resolved
