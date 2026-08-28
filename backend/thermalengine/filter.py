from backend.data_acquisition.schemas import CanonicalAcquiredData
from backend.thermalengine.schemas import ThermalInput, ThermalInputValidationError

class ThermalFilter:
    """
    Extracts only Thermal-required fields from CanonicalAcquiredData
    and maps them to ThermalInput without mutating the source object.
    """
    @staticmethod
    def filter(canonical: CanonicalAcquiredData, area_id: str = "GLOBAL") -> ThermalInput:
        if canonical.temperature_c is None or canonical.relative_humidity_pct is None:
            # Passing None to temperature_c will cause ThermalInput.validate() to raise ThermalInputValidationError
            pass
            
        return ThermalInput(
            area_id=area_id,
            timestamp=canonical.timestamp,
            temperature_c=canonical.temperature_c,
            relative_humidity_pct=canonical.relative_humidity_pct,
            wind_speed_ms=canonical.wind_speed_ms,
            solar_radiation_wm2=canonical.solar_radiation_wm2,
            dew_point_c=canonical.dew_point_c,
            latitude=canonical.latitude,
            longitude=canonical.longitude
        )
