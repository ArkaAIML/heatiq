from typing import Dict, Any, List

class MockAtmosphericProvider:
    """
    Mock atmospheric data provider for testing architecture wiring.
    Returns deterministic, safe values instead of real live data.
    """
    def fetch_current_conditions(self, area_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Returns raw atmospheric mock data for the requested area IDs.
        """
        results = []
        for area_id in area_ids:
            results.append({
                "source_area_id": area_id,
                "source_timestamp": "2026-05-20T14:00:00Z",
                "source_temperature": 38.5,
                "source_humidity": 45.0,
                "source_wind": 2.5,
                "source_solar": 800.0
            })
        return results
