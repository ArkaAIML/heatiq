import pytest
import os
from datetime import datetime, timedelta, timezone
from backend.prediction.weather_history.schemas import CanonicalHourlyWeather
from backend.prediction.weather_history.storage import WeatherHistoryStore
from backend.prediction.weather_history.api import NasaPowerHistoryAPI
from backend.prediction.weather_history.parser import WeatherHistoryManager

class MockAPI(NasaPowerHistoryAPI):
    def __init__(self):
        self.call_count = 0
        self.requested_ranges = []
        self.mock_data = []
        self.fail_next = False

    def fetch_history(self, location, latitude, longitude, start_date, end_date):
        self.call_count += 1
        self.requested_ranges.append((start_date, end_date))
        
        if self.fail_next:
            self.fail_next = False
            raise Exception("Mock API failure")
            
        return self.mock_data

@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_history.db"
    store = WeatherHistoryStore(str(db_file))
    yield store
    store.close()
    if db_file.exists():
        db_file.unlink()

@pytest.fixture
def mock_api():
    return MockAPI()

@pytest.fixture
def manager(temp_db, mock_api):
    return WeatherHistoryManager(temp_db, mock_api)

def _generate_mock_data(location, start_dt, num_hours, skip_hours=None):
    if skip_hours is None:
        skip_hours = []
    data = []
    for i in range(num_hours):
        if i in skip_hours:
            continue
        dt = start_dt + timedelta(hours=i)
        data.append(CanonicalHourlyWeather(
            location=location,
            timestamp=dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            latitude=20.0,
            longitude=85.0,
            temperature_c=25.0,
            dewpoint_c=20.0,
            relative_humidity_pct=75.0,
            wind_speed_ms=5.0,
            surface_pressure_pa=101000.0,
            solar_radiation_wm2=500.0,
            thermal_radiation_wm2=None
        ))
    return data

def test_empty_database_and_complete_history(manager, mock_api):
    # A. Empty database fetches data
    start_dt = datetime(2026, 8, 1, tzinfo=timezone.utc)
    end_dt = start_dt + timedelta(hours=23)
    
    mock_api.mock_data = _generate_mock_data("LocA", start_dt, 24)
    
    records = manager.get_history("LocA", 20.0, 85.0, "2026-08-01T00:00:00Z", "2026-08-01T23:00:00Z")
    
    assert mock_api.call_count == 1
    assert len(records) == 24
    
    # B. Existing complete history does not fetch
    records_again = manager.get_history("LocA", 20.0, 85.0, "2026-08-01T00:00:00Z", "2026-08-01T23:00:00Z")
    assert mock_api.call_count == 1  # Still 1
    assert len(records_again) == 24

def test_partial_missing_history(manager, mock_api):
    # Setup initial 12 hours
    start_dt = datetime(2026, 8, 1, tzinfo=timezone.utc)
    manager.store.insert_records(_generate_mock_data("LocA", start_dt, 12))
    
    # C. Partially missing history (requests 24 hours, last 12 missing)
    mock_api.mock_data = _generate_mock_data("LocA", start_dt + timedelta(hours=12), 12)
    records = manager.get_history("LocA", 20.0, 85.0, "2026-08-01T00:00:00Z", "2026-08-01T23:00:00Z")
    
    assert mock_api.call_count == 1
    assert mock_api.requested_ranges[0] == ("2026-08-01", "2026-08-01") # Only the missing day fetched
    assert len(records) == 24

def test_one_hour_extension(manager, mock_api):
    start_dt = datetime(2026, 8, 1, tzinfo=timezone.utc)
    manager.store.insert_records(_generate_mock_data("LocA", start_dt, 24))
    
    # D. One hour extension
    mock_api.mock_data = _generate_mock_data("LocA", start_dt + timedelta(hours=24), 1)
    records = manager.get_history("LocA", 20.0, 85.0, "2026-08-01T00:00:00Z", "2026-08-02T00:00:00Z")
    
    assert mock_api.call_count == 1
    assert len(records) == 25

def test_duplicate_records(manager):
    # F. Duplicate provider records
    start_dt = datetime(2026, 8, 1, tzinfo=timezone.utc)
    data = _generate_mock_data("LocA", start_dt, 2)
    # Insert twice
    manager.store.insert_records(data)
    manager.store.insert_records(data) # Should IGNORE
    
    records = manager.store.get_records("LocA", "2026-08-01T00:00:00Z", "2026-08-01T01:00:00Z")
    assert len(records) == 2

def test_missing_hourly_timestamp_gap_detection(manager, mock_api):
    # G. Missing hourly timestamp
    start_dt = datetime(2026, 8, 1, tzinfo=timezone.utc)
    
    # Provide data with a gap (skip hour 2)
    mock_api.mock_data = _generate_mock_data("LocA", start_dt, 5, skip_hours=[2])
    
    records = manager.get_history("LocA", 20.0, 85.0, "2026-08-01T00:00:00Z", "2026-08-01T04:00:00Z")
    assert len(records) == 4 # Returns what it has, logs gap
    
def test_rolling_retention(manager):
    # J. Rolling retention
    # Insert data 61 days ago
    old_dt = datetime.now(timezone.utc) - timedelta(days=61)
    data = _generate_mock_data("LocA", old_dt, 2)
    manager.store.insert_records(data)
    
    cutoff = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
    manager.store.trim_old_records("LocA", cutoff)
    
    records = manager.store.get_records("LocA", old_dt.strftime("%Y-%m-%dT%H:%M:%SZ"), (old_dt + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    assert len(records) == 0

def test_multiple_locations(manager, mock_api):
    # K. Multiple locations
    start_dt = datetime(2026, 8, 1, tzinfo=timezone.utc)
    manager.store.insert_records(_generate_mock_data("LocA", start_dt, 5))
    manager.store.insert_records(_generate_mock_data("LocB", start_dt, 5))
    
    records_a = manager.store.get_records("LocA", "2026-08-01T00:00:00Z", "2026-08-01T04:00:00Z")
    assert all(r.location == "LocA" for r in records_a)

def test_failed_api_call(manager, mock_api):
    # M. Failed API call
    start_dt = datetime(2026, 8, 1, tzinfo=timezone.utc)
    manager.store.insert_records(_generate_mock_data("LocA", start_dt, 5))
    
    mock_api.fail_next = True
    
    try:
        manager.get_history("LocA", 20.0, 85.0, "2026-08-01T00:00:00Z", "2026-08-01T10:00:00Z")
    except Exception:
        pass # Expected
        
    # Existing data remains
    records = manager.store.get_records("LocA", "2026-08-01T00:00:00Z", "2026-08-01T10:00:00Z")
    assert len(records) == 5
