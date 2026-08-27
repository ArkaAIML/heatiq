"""
HeatIQ Ward Filter — InfoSmasher Component
"""
from typing import Optional, Any, Dict
from backend.thermalengine import ThermalOutput
from backend.mortality import MortalityOutput, InfoPoolRecord, ResourcePoolRecord
from backend.prediction.schemas import PredictionOutput
from .schemas import WardContext, WardFilterInputValidationError

class InfoSmasher:
    """
    Assembles the four already-structured inputs belonging to one ward into a complete WardContext.
    Does NOT calculate risk or severity.
    """
    
    @staticmethod
    def smash(
        thermal: ThermalOutput,
        prediction: Optional[PredictionOutput],
        mortality: MortalityOutput,
        info: InfoPoolRecord,
        resource: ResourcePoolRecord
    ) -> WardContext:
        """
        Validates, normalizes, and matches records by area_id to create a single WardContext.
        """
        if not isinstance(thermal, ThermalOutput):
            raise WardFilterInputValidationError(f"Expected ThermalOutput, got {type(thermal)}")
        if prediction is not None and not isinstance(prediction, PredictionOutput):
            raise WardFilterInputValidationError(f"Expected PredictionOutput, got {type(prediction)}")
        if not isinstance(mortality, MortalityOutput):
            raise WardFilterInputValidationError(f"Expected MortalityOutput, got {type(mortality)}")
        if not isinstance(info, InfoPoolRecord):
            raise WardFilterInputValidationError(f"Expected InfoPoolRecord, got {type(info)}")
        if not isinstance(resource, ResourcePoolRecord):
            raise WardFilterInputValidationError(f"Expected ResourcePoolRecord, got {type(resource)}")

        # Enforce area_id matching to prevent cross-ward contamination
        area_id = thermal.area_id
        if prediction is not None and prediction.area_id != area_id:
            raise WardFilterInputValidationError(f"Prediction area_id ({prediction.area_id}) does not match Thermal area_id ({area_id})")
        if mortality.area_id != area_id:
            raise WardFilterInputValidationError(f"Mortality area_id ({mortality.area_id}) does not match Thermal area_id ({area_id})")
        if info.area_id != area_id:
            raise WardFilterInputValidationError(f"Info area_id ({info.area_id}) does not match Thermal area_id ({area_id})")
        if resource.area_id != area_id:
            raise WardFilterInputValidationError(f"Resource area_id ({resource.area_id}) does not match Thermal area_id ({area_id})")

        # Preserve the primary timestamp (usually from Thermal hazard observation)
        timestamp = thermal.timestamp or mortality.timestamp

        context = WardContext(
            area_id=area_id,
            timestamp=timestamp,
            thermal=thermal,
            prediction=prediction,
            mortality=mortality,
            info_pool=info,
            resource_pool=resource
        )
        context.validate()
        return context
