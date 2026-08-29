import os
from backend.thermalengine.data_acquisition.adapter import AtmosphericDataAcquisitionAdapter
from backend.thermalengine.data_acquisition.open_meteo_provider import OpenMeteoProvider
from backend.thermalengine.service import calculate_thermal_indices_batch

def run_live_integration():
    print("--- Running Live Weather Integration Test ---")
    
    # Temporarily force the real provider
    os.environ["HEATIQ_WEATHER_PROVIDER"] = "open-meteo"
    
    # We will pretend the datalake returned two wards for Bhubaneswar
    # by directly overriding the resolver just for this test script, or we can just pass
    # the provider directly and call the methods.
    
    provider = OpenMeteoProvider()
    adapter = AtmosphericDataAcquisitionAdapter(provider=provider)
    
    print("Fetching live data from Open-Meteo for two mock wards...")
    try:
        # Manually resolving two wards for the sake of the test
        area_ids = ["WARD_001", "WARD_002"]
        raw_conditions = provider.fetch_current_conditions(area_ids)
        print(f"Success! Retrieved {len(raw_conditions)} raw condition payloads.")
        
        thermal_inputs = []
        for raw in raw_conditions:
            thermal_inputs.append(adapter._normalize_to_thermal_input(raw))
            
        print(f"Normalized into Canonical ThermalInput objects:")
        for t in thermal_inputs:
            print(f"  Area: {t.area_id} | Time: {t.timestamp} | Temp: {t.temperature_c}C | RH: {t.relative_humidity_pct}% | Wind: {t.wind_speed_ms}m/s | Solar: {t.solar_radiation_wm2}W/m2")
            
        print("\nPassing to Thermal Gateway...")
        thermal_outputs = calculate_thermal_indices_batch(thermal_inputs, allow_partial_failures=True)
        
        for out in thermal_outputs:
            print(f"  Area: {out.area_id} | Status: {out.calculation_status} | HTSI: {out.htsi}")
            
    except Exception as e:
        print(f"Live Integration Failed: {str(e)}")
        
if __name__ == "__main__":
    run_live_integration()
