"""
HeatIQ Ward Filter — Gateway Boundary
"""
from typing import Sequence, Union, Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)

from backend.thermalengine import ThermalOutput
from backend.mortality import MortalityOutput, InfoPoolRecord, ResourcePoolRecord
from backend.prediction.schemas import PredictionOutput
from .schemas import WardFilterResult, WardFilterInputValidationError
from .infosmasher import InfoSmasher
from .engine import IntelligentFilteringEngine, Rule
from .rules import DEFAULT_RULESET

class WardFilterGateway:
    """
    Coordinates matching inputs, running the InfoSmasher, and evaluating the Ward Context
    against the Intelligent Filtering Engine.
    """
    
    def __init__(self, engine: Optional[IntelligentFilteringEngine] = None):
        self.engine = engine or IntelligentFilteringEngine(rules=DEFAULT_RULESET)
        
    def _parse_mortality_records(
        self,
        records: Union[Sequence[Union[MortalityOutput, Dict[str, Any]]], None]
    ) -> Dict[str, MortalityOutput]:
        if not records:
            return {}
        res = {}
        for item in records:
            if isinstance(item, dict):
                item = MortalityOutput(**item)
            if not isinstance(item, MortalityOutput):
                raise WardFilterInputValidationError(f"Invalid mortality record type: {type(item)}")
            res[item.area_id] = item
        return res

    def _parse_info_records(
        self,
        records: Union[Sequence[Union[InfoPoolRecord, Dict[str, Any]]], None]
    ) -> Dict[str, InfoPoolRecord]:
        if not records:
            return {}
        res = {}
        for item in records:
            if isinstance(item, dict):
                item = InfoPoolRecord.from_dict(item)
            if not isinstance(item, InfoPoolRecord):
                raise WardFilterInputValidationError(f"Invalid info record type: {type(item)}")
            res[item.area_id] = item
        return res

    def _parse_resource_records(
        self,
        records: Union[Sequence[Union[ResourcePoolRecord, Dict[str, Any]]], None]
    ) -> Dict[str, ResourcePoolRecord]:
        if not records:
            return {}
        res = {}
        for item in records:
            if isinstance(item, dict):
                item = ResourcePoolRecord.from_dict(item)
            if not isinstance(item, ResourcePoolRecord):
                raise WardFilterInputValidationError(f"Invalid resource record type: {type(item)}")
            res[item.area_id] = item
        return res

    def _parse_prediction_records(
        self,
        records: Union[Sequence[Union[PredictionOutput, Dict[str, Any]]], None]
    ) -> Dict[str, PredictionOutput]:
        if not records:
            return {}
        res = {}
        for item in records:
            if item is None:
                continue
            if isinstance(item, dict):
                item = PredictionOutput.from_dict(item)
            if not isinstance(item, PredictionOutput):
                raise WardFilterInputValidationError(f"Invalid prediction record type: {type(item)}")
            res[item.area_id] = item
        return res

    def filter_ward(
        self,
        thermal: ThermalOutput,
        prediction: Optional[PredictionOutput],
        mortality: MortalityOutput,
        info: InfoPoolRecord,
        resource: ResourcePoolRecord
    ) -> WardFilterResult:
        """
        Process a single ward.
        """
        context = InfoSmasher.smash(thermal, prediction, mortality, info, resource)
        return self.engine.evaluate(context)

    def filter_wards(
        self,
        thermal_outputs: Sequence[ThermalOutput],
        mortality_outputs: Sequence[MortalityOutput],
        info_records: Optional[Sequence[InfoPoolRecord]],
        resource_records: Optional[Sequence[ResourcePoolRecord]],
        prediction_outputs: Optional[Sequence[Optional[PredictionOutput]]] = None,
        max_workers: int = 4,
        allow_partial_failures: bool = True
    ) -> List[WardFilterResult]:
        """
        Process a batch of wards concurrently.
        Matches outputs and records by area_id.
        """
        from concurrent.futures import ThreadPoolExecutor

        info_source_failed = info_records is None
        resource_source_failed = resource_records is None

        mortality_map = self._parse_mortality_records(mortality_outputs)
        info_map = self._parse_info_records(info_records if info_records is not None else [])
        res_map = self._parse_resource_records(resource_records if resource_records is not None else [])
        prediction_map = self._parse_prediction_records(prediction_outputs)

        seen_area_ids = set()
        duplicates = set()
        for t in thermal_outputs:
            if hasattr(t, "area_id"):
                if t.area_id in seen_area_ids:
                    duplicates.add(t.area_id)
                seen_area_ids.add(t.area_id)

        def _process_single(thermal: ThermalOutput) -> WardFilterResult:
            area_id = getattr(thermal, "area_id", "UNKNOWN")
            timestamp = getattr(thermal, "timestamp", "")

            if not isinstance(thermal, ThermalOutput):
                if not allow_partial_failures:
                    raise WardFilterInputValidationError(f"Expected ThermalOutput, got {type(thermal)}")
                return WardFilterResult(
                    area_id=area_id, timestamp=timestamp,
                    calculation_status="INSUFFICIENT_DATA", method_version="INVALID_INPUT_TYPE"
                )

            if area_id in duplicates:
                if not allow_partial_failures:
                    raise WardFilterInputValidationError(f"Duplicate area_id found: {area_id}")
                return WardFilterResult(
                    area_id=area_id, timestamp=timestamp,
                    calculation_status="INSUFFICIENT_DATA", method_version="DUPLICATE_AREA_ID_IN_BATCH"
                )

            try:
                mortality = mortality_map.get(area_id)
                info = info_map.get(area_id)
                resource = res_map.get(area_id)
                prediction = prediction_map.get(area_id)

                if not mortality or not info or not resource:
                    if None in [thermal, mortality, info, resource, prediction]:
                        missing = []
                        if not thermal: missing.append("thermal")
                        if not mortality: missing.append("mortality")
                        if not info: missing.append("info")
                        if not resource: missing.append("resource")
                        if not prediction: missing.append("prediction")
                        logger.error(f"Missing records for {area_id}: {missing}")
                    
                    if not allow_partial_failures:
                        raise WardFilterInputValidationError(f"Missing required records for area_id: {area_id}")
                    
                    # Distinguish between SOURCE_UNAVAILABLE and MISSING_DATA
                    missing_str = []
                    if not mortality:
                        missing_str.append("MortalityOutput")
                    if not info:
                        if info_source_failed:
                            missing_str.append("SOURCE_UNAVAILABLE: InfoPoolRecord")
                        else:
                            missing_str.append("MISSING_DATA: InfoPoolRecord")
                    if not resource:
                        if resource_source_failed:
                            missing_str.append("SOURCE_UNAVAILABLE: ResourcePoolRecord")
                        else:
                            missing_str.append("MISSING_DATA: ResourcePoolRecord")
                            
                    return WardFilterResult(
                        area_id=area_id, timestamp=timestamp,
                        calculation_status="INSUFFICIENT_DATA", method_version=" | ".join(missing_str)
                    )

                context = InfoSmasher.smash(thermal, prediction, mortality, info, resource)
                return self.engine.evaluate(context)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"stage=WardFilter area_id={area_id} reason=PROCESSING_ERROR details='{str(e)}'")
                if not allow_partial_failures:
                    raise e
                return WardFilterResult(
                    area_id=area_id, timestamp=timestamp,
                    calculation_status="INSUFFICIENT_DATA", method_version=f"PROCESSING_ERROR: {str(e)}"
                )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(_process_single, thermal_outputs))

        return results

_default_gateway = WardFilterGateway()

def filter_ward(
    thermal: ThermalOutput,
    prediction: Optional[PredictionOutput],
    mortality: MortalityOutput,
    info: InfoPoolRecord,
    resource: ResourcePoolRecord
) -> WardFilterResult:
    return _default_gateway.filter_ward(thermal, prediction, mortality, info, resource)

def filter_wards(
    thermal_outputs: Sequence[ThermalOutput],
    prediction_outputs: Optional[Sequence[Optional[PredictionOutput]]],
    mortality_outputs: Sequence[MortalityOutput],
    info_records: Optional[Sequence[InfoPoolRecord]],
    resource_records: Optional[Sequence[ResourcePoolRecord]],
    max_workers: int = 4,
    allow_partial_failures: bool = True
) -> List[WardFilterResult]:
    return _default_gateway.filter_wards(
        thermal_outputs, mortality_outputs, info_records, resource_records, prediction_outputs, max_workers, allow_partial_failures
    )
