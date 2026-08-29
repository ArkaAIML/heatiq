import os
import json
import logging
import httpx
from typing import Protocol, Dict, Any, Optional

logger = logging.getLogger(__name__)

class GeminiProvider(Protocol):
    def generate(self, system_prompt: str, user_context: str) -> Optional[Dict[str, Any]]:
        ...

class RealGeminiProvider:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self.model = os.environ.get("GEMINI_MODEL", "gemini-2.5-pro")
        
    def generate(self, system_prompt: str, user_context: str) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            logger.error("stage=GeminiProvider reason=MISSING_API_KEY")
            raise ValueError("GEMINI_API_KEY environment variable is missing")
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        
        payload = {
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [{
                "parts": [{"text": user_context}]
            }],
            "generationConfig": {
                "response_mime_type": "application/json"
            }
        }
        
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                
                data = response.json()
                # Parse the response text out of the standard Gemini structure
                candidates = data.get("candidates", [])
                if not candidates:
                    logger.error("stage=GeminiProvider reason=EMPTY_CANDIDATES")
                    raise ValueError("No candidates returned from Gemini")
                    
                content = candidates[0].get("content", {}).get("parts", [])[0].get("text", "")
                if not content:
                    logger.error("stage=GeminiProvider reason=EMPTY_CONTENT")
                    raise ValueError("Empty content returned from Gemini")
                
                # Because we requested application/json, the response should be valid JSON
                return json.loads(content)
        except httpx.HTTPStatusError as e:
            logger.error(f"stage=GeminiProvider reason=HTTP_ERROR status={e.response.status_code}")
            raise RuntimeError(f"Gemini API returned status {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error(f"stage=GeminiProvider reason=NETWORK_ERROR details='{str(e)}'")
            raise RuntimeError(f"Network error connecting to Gemini API: {str(e)}") from e
        except json.JSONDecodeError as e:
            logger.error(f"stage=GeminiProvider reason=INVALID_JSON details='{str(e)}'")
            raise ValueError("Gemini returned malformed JSON") from e

class FakeGeminiProvider:
    """Deterministic fake provider for unit tests."""
    def __init__(self, override_response: Optional[Dict[str, Any]] = None, should_fail: bool = False):
        self.override_response = override_response
        self.should_fail = should_fail
        
    def generate(self, system_prompt: str, user_context: str) -> Optional[Dict[str, Any]]:
        if self.should_fail:
            raise RuntimeError("Fake gemini provider forced failure")
            
        if self.override_response:
            return self.override_response
            
        # Default mock response
        return {
            "situation_summary": "The ward is currently experiencing heatwave conditions.",
            "severity": "HIGH",
            "immediate_actions": [
                {
                    "name": "Activate cooling resources",
                    "allocations": ["Allocate water trucks", "Prioritize community centers"],
                    "reason": "Immediate relief required"
                },
                {
                    "name": "Protect vulnerable populations",
                    "allocations": ["Welfare checks"],
                    "reason": "High elderly population"
                }
            ],
            "resource_allocation": {
                "cooling_centres": "2 active",
                "healthcare_capacity": "50 beds",
                "outreach_personnel": "10 teams",
                "other": ""
            },
            "population_priorities": ["Elderly residents", "Children"],
            "monitoring_instructions": ["Monitor temperature", "Re-evaluate at 15:00"],
            "rationale": "High temperature requires immediate action.",
            "escalation_conditions": "If temperature exceeds 45C"
        }
