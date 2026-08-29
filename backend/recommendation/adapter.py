import logging
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from backend.recommendation.schemas import RecommendationOutput, FailedRecommendationOutput
from backend.recommendation.gemini_provider import RealGeminiProvider, FakeGeminiProvider

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the HeatIQ Recommendation Engine.
You receive structured information describing the current situation of exactly one ward.
Analyze the supplied evidence and produce a practical, prioritized course of action for the responsible authorities or responders.
Use ONLY the supplied ward context.
Never invent measurements, population statistics, resources, facilities, predictions, government capabilities, emergency contacts, policies, or facts not present in the context.
Do not recalculate or replace HeatIQ's Thermal Engine, ML prediction, Mortality Index, or Deterministic Intelligence. Treat those outputs as authoritative inputs.

Your response must be structured JSON with exactly these keys:
- situation_summary (string): What is happening in this ward.
- severity (string): The operational severity of the situation based on the deterministic result.
- immediate_actions (list of objects): Each object must have:
    - name (string): The action name (e.g., "Activate cooling resources").
    - allocations (list of strings): Specific steps (e.g., "Allocate water trucks", "Prioritize community centers").
    - reason (string): Why this is required based on the ward data.
- resource_allocation (object): Must contain exactly these string keys (leave blank if unknown/NA). Explain what should be allocated and where, based on the actual Resource Pool data:
    - cooling_centres (string)
    - healthcare_capacity (string)
    - outreach_personnel (string)
    - other (string)
- population_priorities (list of strings): Which vulnerable/exposed groups to prioritize based on the Info Pool data.
- monitoring_instructions (list of strings): What should be monitored after deployment.
- rationale (string): Overall explanation of why these actions were chosen based on the actual data.
- escalation_conditions (string): What worsening conditions should trigger a stronger response.

If required information is unavailable, explicitly say that it is unavailable instead of inventing it.
Do not provide unsupported medical diagnoses.
Do not output generic recommendations; use the ward's actual data to make specific operational recommendations."""

class RecommendationAdapter:
    """
    Adapter boundary between the HeatIQ canonical ecosystem and the external Gemini Recommendation Engine.
    """
    def __init__(self, provider=None):
        self.provider = provider or RealGeminiProvider()

    def generate_recommendation(self, filtered_input: Dict[str, Any]) -> RecommendationOutput | FailedRecommendationOutput:
        area_id = filtered_input.get("area_id", "UNKNOWN")
        try:
            # 1. Build context
            if not filtered_input:
                raise ValueError("Missing ward context")
            
            # Use original context stringified, safely
            user_context = json.dumps(filtered_input, default=str)
            
            # 2. Call the external ML model boundary
            gemini_response = self.provider.generate(SYSTEM_PROMPT, user_context)
            
            if not gemini_response:
                raise ValueError("Gemini returned empty response")
            
            # 3. Transform the model output into the canonical RecommendationOutput schema
            # We use from_dict to handle the nested dataclass parsing safely
            gemini_response['area_id'] = area_id
            gemini_response['generated_at'] = datetime.now(timezone.utc).isoformat()
            gemini_response['status'] = "COMPUTED"
            gemini_response['message'] = "Recommendation generated successfully via Gemini."
            return RecommendationOutput.from_dict(gemini_response)
        except Exception as e:
            logger.error(f"stage=Recommendation area_id={area_id} reason=ADAPTER_FAILURE details='{str(e)}'")
            return FailedRecommendationOutput(
                area_id=area_id,
                status="ERROR",
                message=f"Recommendation Engine failed: {str(e)}"
            )
