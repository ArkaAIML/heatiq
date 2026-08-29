import pytest
import json
from backend.recommendation.adapter import RecommendationAdapter
from backend.recommendation.filter import RecommendationFilter
from backend.recommendation.gemini_provider import FakeGeminiProvider
from backend.wardfilter.schemas import WardFilterResult, WardContext
from backend.thermalengine.schemas import ThermalOutput
from backend.prediction.schemas import PredictionOutput
from backend.mortality.schemas import MortalityOutput, InfoPoolRecord, ResourcePoolRecord
from backend.recommendation.schemas import RecommendationOutput, FailedRecommendationOutput

def _create_mock_ward_result(area_id: str) -> WardFilterResult:
    thermal = ThermalOutput(area_id, "2026-08-29", 40.0, 35.0, 32.0, 20.0, "HIGH")
    mortality = MortalityOutput(area_id, "2026-08-29", 0.5, 0.8, 1.2, 0.9, "HIGH")
    info = InfoPoolRecord(area_id=area_id, population=1000, vulnerability_score=0.1)
    resource = ResourcePoolRecord(area_id, 2, 100.0, 3, 2.5, 50.0)
    
    ctx = WardContext(area_id, "2026-08-29", thermal, mortality, info, resource)
    return WardFilterResult(
        area_id=area_id,
        timestamp="2026-08-29",
        severity="HIGH",
        recommended_actions=["Cooling"],
        context=ctx
    )

def test_valid_ward_context_gemini_request():
    result = _create_mock_ward_result("WARD_059")
    filtered = RecommendationFilter.filter(result)
    
    provider = FakeGeminiProvider()
    adapter = RecommendationAdapter(provider=provider)
    
    output = adapter.generate_recommendation(filtered)
    assert isinstance(output, RecommendationOutput)
    assert output.area_id == "WARD_059"
    assert output.status == "COMPUTED"
    assert output.severity == "HIGH" # Extracted from FakeGeminiProvider default response

def test_gemini_receives_correct_data():
    result = _create_mock_ward_result("WARD_060")
    filtered = RecommendationFilter.filter(result)
    
    class InspectingProvider(FakeGeminiProvider):
        def generate(self, prompt: str, context: str):
            self.received_context = context
            return super().generate(prompt, context)
            
    provider = InspectingProvider()
    adapter = RecommendationAdapter(provider=provider)
    adapter.generate_recommendation(filtered)
    
    context_data = json.loads(provider.received_context)
    assert context_data["area_id"] == "WARD_060"
    assert "deterministic_result" in context_data
    assert context_data["resource_pool"]["hospital_count"] == 2

def test_gemini_failure_honest_state():
    result = _create_mock_ward_result("WARD_059")
    filtered = RecommendationFilter.filter(result)
    
    provider = FakeGeminiProvider(should_fail=True)
    adapter = RecommendationAdapter(provider=provider)
    
    output = adapter.generate_recommendation(filtered)
    assert isinstance(output, FailedRecommendationOutput)
    assert output.area_id == "WARD_059"
    assert output.status == "ERROR"
    assert "forced failure" in output.message
