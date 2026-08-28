"""ML-owned weather preprocessing interfaces."""

from ml.preprocessing.clean import (
    derive_canonical_weather,
    load_era5_files,
    select_nearest_point,
    validate_canonical_weather,
    validate_era5_inputs,
)
from ml.preprocessing.features import (
    add_daily_temporal_features,
    aggregate_daily_weather,
    build_daily_feature_frame,
)
from ml.preprocessing.supervised import (
    ChronologicalSplits,
    SupervisedPartition,
    add_future_target,
    chronological_split,
)

__all__ = [
    "ChronologicalSplits",
    "SupervisedPartition",
    "add_daily_temporal_features",
    "add_future_target",
    "aggregate_daily_weather",
    "build_daily_feature_frame",
    "chronological_split",
    "derive_canonical_weather",
    "load_era5_files",
    "select_nearest_point",
    "validate_canonical_weather",
    "validate_era5_inputs",
]
