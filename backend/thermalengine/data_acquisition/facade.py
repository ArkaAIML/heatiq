from typing import List
from backend.thermalengine.schemas import ThermalOutput
from backend.thermalengine.service import calculate_thermal_indices_batch
from .adapter import AtmosphericDataAcquisitionAdapter

def thermal_engine_for_location(location: str, adapter: AtmosphericDataAcquisitionAdapter = None) -> List[ThermalOutput]:
    """
    Acquire atmospheric data for a geographic location,
    resolve it to wards, and compute thermal indices.
    """
    if adapter is None:
        adapter = AtmosphericDataAcquisitionAdapter()
        
    thermal_inputs = adapter.acquire_for_location(location)
    if not thermal_inputs:
        return []
        
    return calculate_thermal_indices_batch(thermal_inputs, allow_partial_failures=True)
