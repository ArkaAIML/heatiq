"""Provider-neutral construction of one model-ready inference feature row."""

from datetime import date, datetime

import pandas as pd

from ml.inference.artifact import ModelArtifact
from ml.preprocessing.canonical import build_canonical_weather_dataset
from ml.preprocessing.features import build_daily_feature_frame


def build_inference_feature_row(
    weather_history: pd.DataFrame,
    *,
    artifact: ModelArtifact,
    latitude: float,
    longitude: float,
    feature_date: date | datetime | str | None = None,
    timezone: str = "Asia/Kolkata",
) -> pd.DataFrame:
    """Build exactly one feature row in the artifact's authoritative order.

    ``feature_date`` identifies a complete local calendar day in ``timezone``.
    When it is omitted, the latest complete day with sufficient prior history
    is selected. The selected date is retained as the row index and in frame
    metadata; it is never included among the model feature columns.
    """

    if not isinstance(artifact, ModelArtifact):
        raise TypeError("artifact must be a ModelArtifact instance")

    canonical = build_canonical_weather_dataset(
        weather_history,
        latitude=latitude,
        longitude=longitude,
    )
    feature_frame = build_daily_feature_frame(canonical, timezone=timezone)
    expected_features = artifact.metadata.feature_names
    engineered_features = tuple(
        column for column in feature_frame.columns if column != "date"
    )
    missing_features = [
        name for name in expected_features if name not in engineered_features
    ]
    unexpected_features = [
        name for name in engineered_features if name not in expected_features
    ]
    if missing_features or unexpected_features or len(expected_features) != len(
        engineered_features
    ):
        raise ValueError(
            "engineered features do not match artifact metadata; "
            f"missing={missing_features}, unexpected={unexpected_features}"
        )

    if feature_date is None:
        selected = feature_frame.iloc[[-1]]
    else:
        requested_date = _normalize_feature_date(feature_date, timezone)
        selected = feature_frame.loc[feature_frame["date"] == requested_date]
        if selected.empty:
            raise ValueError(
                "requested feature_date is not available as a complete feature row: "
                f"{requested_date.date().isoformat()}"
            )

    selected_date = pd.Timestamp(selected.iloc[0]["date"])
    feature_row = selected.loc[:, list(expected_features)].copy(deep=True)
    feature_row.index = pd.DatetimeIndex([selected_date], name="feature_date")
    feature_row.attrs = {
        "feature_date": selected_date,
        "timezone": timezone,
    }
    return feature_row


def _normalize_feature_date(
    value: date | datetime | str,
    timezone: str,
) -> pd.Timestamp:
    if not isinstance(value, (date, str)):
        raise TypeError("feature_date must be a date, datetime, string, or None")
    if isinstance(value, str) and not value.strip():
        raise ValueError("feature_date string cannot be empty")

    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid feature_date: {value!r}") from exc
    if pd.isna(timestamp):
        raise ValueError("feature_date cannot be missing")

    if timestamp.tzinfo is not None:
        try:
            timestamp = timestamp.tz_convert(timezone).tz_localize(None)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid timezone: {timezone!r}") from exc
    return timestamp.normalize()
