import logging
from datetime import datetime, timedelta, timezone

from backend.prediction.weather_history.schemas import CanonicalHourlyWeather
from backend.prediction.weather_history.storage import WeatherHistoryStore
from backend.prediction.weather_history.api import NasaPowerHistoryAPI
from backend.prediction.weather_history.parser import WeatherHistoryManager

logging.basicConfig(level=logging.INFO)

def run_smoke_test():
    store = WeatherHistoryStore("smoke_weather_history.db")
    api = NasaPowerHistoryAPI()
    manager = WeatherHistoryManager(store, api)
    
    # Bhubaneswar
    location = "Bhubaneswar"
    latitude = 20.296
    longitude = 85.824
    
    # Request past 3 days up to today
    end_dt = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start_dt = end_dt - timedelta(days=3)
    
    start_str = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_str = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    print(f"--- SMOKE TEST ---")
    print(f"Location: {location}")
    print(f"Requested start: {start_str}")
    print(f"Requested end: {end_str}")
    
    records = manager.get_history(location, latitude, longitude, start_str, end_str)
    
    print(f"Returned rows: {len(records)}")
    if records:
        print(f"Returned start: {records[0].timestamp}")
        print(f"Returned end: {records[-1].timestamp}")
        print(f"Canonical fields parsed successfully.")
        print(f"Sample Record:")
        print(records[0])
    else:
        print("No records returned.")
        
    store.close()

if __name__ == "__main__":
    run_smoke_test()
