"""
HeatIQ Wiring Layer - Wire 1 (Full System Flow)
"""
from typing import List

import logging
from backend.thermalengine.data_acquisition.adapter import AtmosphericDataAcquisitionAdapter
from backend.thermalengine import calculate_thermal_indices_batch
from backend.mortality.service import calculate_mortality_risk_batch
from backend.wardfilter.service import filter_wards
from backend.wardfilter.schemas import WardFilterResult
from backend.prediction.adapter import PredictionAdapter
from datalake.core.cache_manager import get_canonical_info_pool, get_canonical_resource_pool
from backend.wiring.ward_context_store.store import WardContextStore

logger = logging.getLogger(__name__)

def process_location(location: str, allow_partial_failures: bool = True) -> List[WardFilterResult]:
    """
    Executes the full system flow for a given location (e.g., 'Bhubaneswar').
    
    Orchestrates data acquisition, thermal calculation, prediction (mock), mortality risk, 
    and ward filtering without rewriting internal boundaries or recalculating logic.
    """
    
    # 1. Atmospheric Data Acquisition
    adapter = AtmosphericDataAcquisitionAdapter()
    thermal_inputs = adapter.acquire_for_location(location)
    if not thermal_inputs:
        return []

    # 2. Retrieve Data Lake Context (Info Pool & Resource Pool)
    try:
        info_df = get_canonical_info_pool(location)
        info_records = info_df.to_dict(orient="records") if not info_df.empty else []
    except Exception as e:
        logger.error(f"stage=DataLake location={location} source=InfoPool reason=SOURCE_UNAVAILABLE details='{str(e)}'")
        info_records = None
        
    try:
        resource_df = get_canonical_resource_pool(location)
        resource_records = resource_df.to_dict(orient="records") if not resource_df.empty else []
    except Exception as e:
        logger.error(f"stage=DataLake location={location} source=ResourcePool reason=SOURCE_UNAVAILABLE details='{str(e)}'")
        resource_records = None

    # 3. Thermal Engine Gateway
    thermal_outputs = calculate_thermal_indices_batch(thermal_inputs, allow_partial_failures=allow_partial_failures)

    # 4. Thermal Prediction Engine Gateway (ML Boundary)
    try:
        prediction_outputs = PredictionAdapter.predict_batch(thermal_outputs)
    except Exception as e:
        logger.error(f"stage=Prediction location={location} reason=ML_ENGINE_FAILURE details='{str(e)}'")
        prediction_outputs = [None] * len(thermal_outputs)

    # 5. Mortality Risk Gateway
    mortality_outputs = calculate_mortality_risk_batch(
        thermal_outputs=thermal_outputs,
        info_records=info_records,
        resource_records=resource_records,
        allow_partial_failures=allow_partial_failures
    )

    # 6. Ward Filter Gateway
    ward_filter_results = filter_wards(
        thermal_outputs=thermal_outputs,
        prediction_outputs=prediction_outputs,
        mortality_outputs=mortality_outputs,
        info_records=info_records,
        resource_records=resource_records,
        allow_partial_failures=allow_partial_failures
    )
    
    # 7. Store Complete Ward Contexts
    store = WardContextStore()
    for result in ward_filter_results:
        try:
            store.put(result.area_id, result)
        except Exception as e:
            logger.error(f"stage=Store area_id={result.area_id} reason=WRITE_FAILURE details='{str(e)}'")
    
    return ward_filter_results
