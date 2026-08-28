from typing import List
from backend.thermalengine.schemas import ThermalOutput
from .schemas import DummyPredictionOutput, DummyRecommendationOutput, DummyMLResult


def dummy_prediction_and_recommendation(thermal_output: ThermalOutput) -> DummyMLResult:
    """
    Process a single ThermalOutput.
    ABSOLUTELY NO ML OR PROCESSING IS DONE HERE.
    This purely generates dummy structures for architectural wiring.
    The output is entirely independent of the thermal values provided.
    """
    prediction = DummyPredictionOutput(area_id=thermal_output.area_id)
    recommendation = DummyRecommendationOutput(area_id=thermal_output.area_id)
    
    return DummyMLResult(
        prediction=prediction,
        recommendation=recommendation
    )


def dummy_prediction_and_recommendation_batch(thermal_outputs: List[ThermalOutput]) -> List[DummyMLResult]:
    """
    Process a batch of ThermalOutputs.
    Preserves input order, mapping, and area_id.
    """
    return [dummy_prediction_and_recommendation(output) for output in thermal_outputs]
