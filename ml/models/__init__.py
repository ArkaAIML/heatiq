"""ML model training and evaluation interfaces."""

from ml.models.baseline import (
    evaluate_linear_regression_baseline,
    evaluate_persistence_baseline,
    persistence_predictions,
)
from ml.models.evaluate import (
    BaselineEvaluation,
    EvaluatedPredictions,
    RegressionMetrics,
    calculate_regression_metrics,
)

__all__ = [
    "BaselineEvaluation",
    "EvaluatedPredictions",
    "RegressionMetrics",
    "calculate_regression_metrics",
    "evaluate_linear_regression_baseline",
    "evaluate_persistence_baseline",
    "persistence_predictions",
]
