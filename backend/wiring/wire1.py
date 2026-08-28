"""
HeatIQ Wiring Layer - Wire 1 (Full System Flow)
"""
from typing import List
import logging
import copy

from backend.data_acquisition.adapter import GlobalDataAcquisitionAdapter
from backend.thermalengine.filter import ThermalFilter
from backend.thermalengine import calculate_thermal_indices
from backend.mortality.service import calculate_mortality_risk_batch
from backend.wardfilter.service import filter_wards
from backend.wardfilter.schemas import WardFilterResult
from backend.prediction.filter import PredictionFilter
from backend.prediction.adapter import PredictionAdapter
from datalake.core.cache_manager import get_canonical_info_pool, get_canonical_resource_pool
from backend.wiring.ward_context_store.store import WardContextStore

logger = logging.getLogger(__name__)

def process_location(location: str, allow_partial_failures: bool = True) -> List[WardFilterResult]:
    """
    Executes the full system flow for a given location (e.g., 'Bhubaneswar').
    
    Orchestrates global data acquisition, distributes the canonical superset, 
    applies consumer-specific filters, routes to Gates (Thermal, Prediction), 
    calculates mortality risk, and applies ward filtering.
    """
    
    # 1. Global Atmospheric Data Acquisition
    # Produces exactly ONE Canonical Data Superset payload for the location.
    adapter = GlobalDataAcquisitionAdapter()
    global_canonical = adapter.acquire_for_location(location)
    if global_canonical.provider == "failed":
        return []

    # 2. Thermal Filter & Engine Gateway (Global)
    try:
        thermal_input = ThermalFilter.filter(global_canonical, area_id=location)
        global_thermal_output = calculate_thermal_indices(thermal_input)
    except Exception as e:
        logger.error(f"stage=ThermalFilter location={location} reason=FILTER_FAILURE details='{str(e)}'")
        # Return a failed computation indicator
        from backend.thermalengine.schemas import ThermalOutput
        global_thermal_output = ThermalOutput(
            area_id=location, timestamp=global_canonical.timestamp,
            heat_index_c=None, utci_c=None, wbgt_c=None, htsi=None, htsi_category=None,
            calculation_status="INSUFFICIENT_DATA"
        )

    # 3. Prediction Filter & Engine Gateway (ML Boundary) (Global)
    try:
        pred_input = PredictionFilter.filter(global_canonical, location)
        global_prediction_output = PredictionAdapter.predict(pred_input)
    except Exception as e:
        logger.error(f"stage=Prediction location={location} reason=ML_ENGINE_FAILURE details='{str(e)}'")
        global_prediction_output = None

    # 4. Retrieve Data Lake Context (Info Pool & Resource Pool) for ward discovery
    try:
        info_df = get_canonical_info_pool(location)
        info_records = info_df.to_dict(orient="records") if not info_df.empty else []
    except Exception as e:
        logger.error(f"stage=DataLake location={location} source=InfoPool reason=SOURCE_UNAVAILABLE details='{str(e)}'")
        info_records = []
        
    try:
        resource_df = get_canonical_resource_pool(location)
        resource_records = resource_df.to_dict(orient="records") if not resource_df.empty else []
    except Exception as e:
        logger.error(f"stage=DataLake location={location} source=ResourcePool reason=SOURCE_UNAVAILABLE details='{str(e)}'")
        resource_records = []

    # 5. Ward Fan-out
    # We duplicate the global outputs to match the downstream systems that expect per-ward mappings.
    ward_thermal_outputs = []
    ward_prediction_outputs = []
    
    for info in info_records:
        area_id = info.get("area_id")
        if not area_id:
            continue
            
        w_thermal = copy.deepcopy(global_thermal_output)
        w_thermal.area_id = area_id
        ward_thermal_outputs.append(w_thermal)
        
        if global_prediction_output:
            w_pred = copy.deepcopy(global_prediction_output)
            w_pred.area_id = area_id
            ward_prediction_outputs.append(w_pred)
        else:
            ward_prediction_outputs.append(None)

    if not ward_thermal_outputs:
        return []

    # 6. Mortality Risk Gateway
    mortality_outputs = calculate_mortality_risk_batch(
        thermal_outputs=ward_thermal_outputs,
        info_records=info_records,
        resource_records=resource_records,
        allow_partial_failures=allow_partial_failures
    )

    # 7. Ward Filter Gateway
    ward_filter_results = filter_wards(
        thermal_outputs=ward_thermal_outputs,
        prediction_outputs=ward_prediction_outputs,
        mortality_outputs=mortality_outputs,
        info_records=info_records,
        resource_records=resource_records,
        allow_partial_failures=allow_partial_failures
    )
    
    # 8. Store Complete Ward Contexts
    store = WardContextStore()
    from backend.wiring.wire2_store.context_store import Wire2ContextStore
    wire2_context_store = Wire2ContextStore()
    
    for result in ward_filter_results:
        try:
            store.put(result.area_id, result)
        except Exception as e:
            logger.error(f"stage=Store area_id={result.area_id} reason=WRITE_FAILURE details='{str(e)}'")
            
        try:
            # Wire 1 -> Wire 2 Handoff
            if result.context:
                wire2_context_store.put_ward_filter_result(result.area_id, result)
        except Exception as e:
            logger.error(f"stage=Wire2Handoff area_id={result.area_id} reason=WRITE_FAILURE details='{str(e)}'")
    
    return ward_filter_results
