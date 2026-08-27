from typing import List
import logging
from backend.thermalengine.schemas import ThermalInput
from datalake.core.cache_manager import get_canonical_info_pool
import os
from .mock_provider import MockAtmosphericProvider
from .open_meteo_provider import OpenMeteoProvider

logger = logging.getLogger(__name__)

class AtmosphericDataAcquisitionAdapter:
    def __init__(self, provider=None):
        if provider is not None:
            self.provider = provider
        else:
            provider_type = os.environ.get("HEATIQ_WEATHER_PROVIDER", "open-meteo").lower()
            if provider_type == "mock":
                self.provider = MockAtmosphericProvider()
            else:
                self.provider = OpenMeteoProvider()

    def _resolve_wards(self, location: str) -> List[str]:
        """
        Resolve the given location to a list of ward IDs (area_id).
        Relies on the existing Data Lake info pool cache.
        If live ward resolution is unavailable, it returns a fallback list for testing.
        """
        try:
            df = get_canonical_info_pool(location)
            if "area_id" in df.columns:
                return df["area_id"].tolist()
        except Exception:
            pass
        return []

    def _normalize_to_thermal_input(self, raw_data: dict) -> ThermalInput:
        """
        Map raw provider data to canonical ThermalInput schema.
        """
        temp = raw_data.get("source_temperature")
        if temp is None:
            raise ValueError("Missing required source_temperature")
            
        rh = raw_data.get("source_humidity")
        if rh is None:
            raise ValueError("Missing required source_humidity")

        return ThermalInput(
            area_id=raw_data.get("source_area_id", "UNKNOWN"),
            timestamp=raw_data.get("source_timestamp", ""),
            temperature_c=float(temp),
            relative_humidity_pct=float(rh),
            wind_speed_ms=float(raw_data["source_wind"]) if "source_wind" in raw_data else None,
            solar_radiation_wm2=float(raw_data["source_solar"]) if "source_solar" in raw_data else None,
        )

    def acquire_for_location(self, location: str) -> List[ThermalInput]:
        """
        Acquire canonical thermal inputs for all wards in a location.
        """
        area_ids = self._resolve_wards(location)
        if not area_ids:
            return []

        try:
            raw_conditions = self.provider.fetch_current_conditions(area_ids)
        except Exception as e:
            logger.error(f"stage=DataAcquisition location={location} reason=PROVIDER_FAILURE details='{str(e)}'")
            # Generate a batch of failed thermal inputs preserving area_ids
            # so downstream calculation naturally identifies them as INSUFFICIENT_DATA
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            return [{"area_id": a, "timestamp": now, "source_temperature": None} for a in area_ids]
        
        thermal_inputs = []
        for raw in raw_conditions:
            try:
                thermal_input = self._normalize_to_thermal_input(raw)
                thermal_inputs.append(thermal_input)
            except Exception as e:
                logger.error(f"stage=DataAcquisition area_id={raw.get('source_area_id', 'UNKNOWN')} reason=PARSING_ERROR details='{str(e)}'")
                # Pass the partially mapped dictionary instead.
                # The existing Thermal Gateway will validate it, fail, and
                # produce the canonical INSUFFICIENT_DATA ThermalOutput schema.
                bad_dict = {
                    "area_id": raw.get("source_area_id", "UNKNOWN"),
                    "timestamp": raw.get("source_timestamp", ""),
                    "temperature_c": raw.get("source_temperature"),
                    "relative_humidity_pct": raw.get("source_humidity"),
                    "wind_speed_ms": raw.get("source_wind"),
                    "solar_radiation_wm2": raw.get("source_solar")
                }
                thermal_inputs.append(bad_dict)
                
        return thermal_inputs
