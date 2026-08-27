import logging
from backend.wardfilter.schemas import WardContext
from backend.recommendation.schemas import RecommendationOutput, FailedRecommendationOutput
from dummyml.service import dummy_prediction_and_recommendation

logger = logging.getLogger(__name__)

class RecommendationAdapter:
    """
    Adapter boundary between the HeatIQ canonical ecosystem and the external
    Recommendation ML Model. Currently forwards to the dummyml placeholder.
    """
    def generate_recommendation(self, context: WardContext) -> RecommendationOutput | FailedRecommendationOutput:
        try:
            # 1. Transform canonical WardContext into model's expected format.
            # Currently, the dummyml model expects ThermalOutput.
            # We strictly extract this from the already-computed context without recalculating.
            if not context.thermal:
                raise ValueError("Missing thermal context")
            
            thermal_output = context.thermal
            
            # 2. Call the external ML model boundary
            result = dummy_prediction_and_recommendation(thermal_output)
            
            # 3. Transform the model output into the canonical RecommendationOutput schema
            # We know dummyml currently returns DummyRecommendationOutput
            dummy_out = result.recommendation
            
            return RecommendationOutput(
                area_id=dummy_out.area_id,
                # Defaulting forecast_for to the thermal timestamp for now
                forecast_for=thermal_output.timestamp,
                priority="UNKNOWN",
                actions=[],
                reason_codes=[],
                status=dummy_out.status,
                message=dummy_out.message
            )
        except Exception as e:
            logger.error(f"stage=Recommendation area_id={context.thermal.area_id if context.thermal else 'UNKNOWN'} reason=ADAPTER_FAILURE details='{str(e)}'")
            return FailedRecommendationOutput(
                area_id=context.thermal.area_id if context.thermal else "UNKNOWN",
                status="ERROR",
                message=f"Recommendation Engine failed: {str(e)}"
            )
