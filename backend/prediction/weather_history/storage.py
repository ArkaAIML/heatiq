import sqlite3
import threading
from typing import List, Optional
from pathlib import Path
from datetime import datetime
from backend.prediction.weather_history.schemas import CanonicalHourlyWeather

class WeatherHistoryStore:
    def __init__(self, db_path: str = "weather_history.db"):
        self.db_path = Path(db_path)
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
                check_same_thread=False
            )
            # Optimize for concurrency and speed
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
        return self._local.conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS hourly_history (
                    location TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    temperature_c REAL NOT NULL,
                    dewpoint_c REAL NOT NULL,
                    relative_humidity_pct REAL NOT NULL,
                    wind_speed_ms REAL NOT NULL,
                    surface_pressure_pa REAL NOT NULL,
                    solar_radiation_wm2 REAL NOT NULL,
                    thermal_radiation_wm2 REAL,
                    PRIMARY KEY (location, timestamp)
                )
            ''')
            # Index for fast time-range queries per location
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_loc_time 
                ON hourly_history (location, timestamp)
            ''')

    def insert_records(self, records: List[CanonicalHourlyWeather]):
        """
        Inserts records safely. Uses INSERT OR IGNORE to prevent duplicates.
        Validation must happen before calling this.
        """
        if not records:
            return

        with self._get_conn() as conn:
            conn.executemany('''
                INSERT OR IGNORE INTO hourly_history (
                    location, timestamp, latitude, longitude,
                    temperature_c, dewpoint_c, relative_humidity_pct,
                    wind_speed_ms, surface_pressure_pa, solar_radiation_wm2,
                    thermal_radiation_wm2
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', [
                (
                    r.location, r.timestamp, r.latitude, r.longitude,
                    r.temperature_c, r.dewpoint_c, r.relative_humidity_pct,
                    r.wind_speed_ms, r.surface_pressure_pa, r.solar_radiation_wm2,
                    r.thermal_radiation_wm2
                ) for r in records
            ])

    def get_records(self, location: str, start_timestamp: str, end_timestamp: str) -> List[CanonicalHourlyWeather]:
        """
        Fetches records for a specific location within the inclusive time range.
        Timestamps should be ISO-8601 strings.
        Returns records sorted chronologically.
        """
        with self._get_conn() as conn:
            cursor = conn.execute('''
                SELECT 
                    location, timestamp, latitude, longitude,
                    temperature_c, dewpoint_c, relative_humidity_pct,
                    wind_speed_ms, surface_pressure_pa, solar_radiation_wm2,
                    thermal_radiation_wm2
                FROM hourly_history
                WHERE location = ? AND timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp ASC
            ''', (location, start_timestamp, end_timestamp))
            
            rows = cursor.fetchall()
            
        return [
            CanonicalHourlyWeather(
                location=r[0], timestamp=r[1], latitude=r[2], longitude=r[3],
                temperature_c=r[4], dewpoint_c=r[5], relative_humidity_pct=r[6],
                wind_speed_ms=r[7], surface_pressure_pa=r[8], solar_radiation_wm2=r[9],
                thermal_radiation_wm2=r[10]
            ) for r in rows
        ]
        
    def trim_old_records(self, location: str, retention_cutoff: str):
        """
        Deletes records older than the cutoff strictly for the specified location.
        """
        with self._get_conn() as conn:
            conn.execute('''
                DELETE FROM hourly_history
                WHERE location = ? AND timestamp < ?
            ''', (location, retention_cutoff))

    def get_coverage(self, location: str, start_timestamp: str, end_timestamp: str) -> List[str]:
        """
        Returns a list of timestamps that currently exist in the DB for the given range.
        """
        with self._get_conn() as conn:
            cursor = conn.execute('''
                SELECT timestamp FROM hourly_history
                WHERE location = ? AND timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp ASC
            ''', (location, start_timestamp, end_timestamp))
            return [r[0] for r in cursor.fetchall()]

    def close(self):
        if hasattr(self._local, "conn"):
            self._local.conn.close()
            del self._local.conn
