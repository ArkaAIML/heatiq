import sys
import os
import pandas as pd
import xarray as xr
from datetime import datetime, timezone

# Add ml pipeline to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../ml/pipeline"))

from backend.prediction.weather_history.storage import WeatherHistoryStore
from backend.prediction.weather_history.api import NasaPowerHistoryAPI
from backend.prediction.weather_history.parser import WeatherHistoryManager

from ml.preprocessing.features import build_daily_feature_frame

def run_validation():
    print("--- STARTING ML PREPROCESSING VALIDATION ---")
    store = WeatherHistoryStore("validate_weather_history.db")
    api = NasaPowerHistoryAPI()
    manager = WeatherHistoryManager(store, api)
    
    location = "Bhubaneswar"
    latitude = 20.296
    longitude = 85.824
    
    # Use 2024 to guarantee we avoid NASA POWER's 5-7 day latency on recent data
    start_time = "2024-08-01T00:00:00Z"
    end_time = "2024-08-15T23:00:00Z"
    
    # Temporarily disable rolling retention so our 2024 data isn't deleted immediately
    manager.RETENTION_DAYS = 3650
    
    print(f"Fetching history for {location} from {start_time} to {end_time}...")
    records = manager.get_history(location, latitude, longitude, start_time, end_time)
    
    if not records:
        print("ERROR: No records returned. Validation failed.")
        return
        
    print(f"Successfully fetched {len(records)} hourly records.")
    print("Converting to xarray.Dataset...")
    
    # Convert records to DataFrame
    df = pd.DataFrame([vars(r) for r in records])
    
    # Convert timestamp string to datetime64[ns]
    df['valid_time'] = pd.to_datetime(df['timestamp']).dt.tz_localize(None)
    
    # Set index
    df = df.set_index('valid_time')
    
    # Drop columns not needed in xarray for features.py (like location, timestamp, lat, lon)
    canonical_vars = [
        "temperature_c", "dewpoint_c", "relative_humidity_pct",
        "wind_speed_ms", "surface_pressure_pa", "solar_radiation_wm2",
        "thermal_radiation_wm2"
    ]
    df_clean = df[canonical_vars]
    
    # Create xarray dataset
    ds = xr.Dataset.from_dataframe(df_clean)
    
    # Add scalar lat/lon coordinates as features.py may expect them 
    # (though _validate_single_location_hourly checks they are scalar if present)
    ds = ds.assign_coords(latitude=latitude, longitude=longitude)
    
    print("Executing build_daily_feature_frame()...")
    try:
        # We need drop_incomplete_history=True by default to drop first 5 rows
        feature_df = build_daily_feature_frame(ds, timezone="Asia/Kolkata")
        print("\n--- PREPROCESSING SUCCESSFUL ---")
        
        print("\nFeatures generated (1 row sample):")
        if not feature_df.empty:
            sample_row = feature_df.iloc[0]
            for col in feature_df.columns:
                val = sample_row[col]
                # Check for NaNs
                status = "VALID" if pd.notna(val) else "NaN"
                print(f"  {col}: {val} [{status}]")
                
            print(f"\nTotal rows generated: {len(feature_df)}")
            
            # Print list of columns exactly to verify 24 features
            print(f"Number of columns: {len(feature_df.columns)} (Includes 'date')")
            print("Feature order:")
            for i, col in enumerate(feature_df.columns):
                print(f"{i}: {col}")
        else:
            print("ERROR: feature_df is empty!")
            
    except Exception as e:
        print(f"\nERROR during preprocessing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_validation()
