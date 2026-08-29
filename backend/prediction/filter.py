import math
from typing import Dict, Any
from backend.data_acquisition.schemas import CanonicalAcquiredData

class PredictionFilter:
    """
    Routes regular atmospheric data and location/history information to the Prediction Gate.
    Separates the concerns so the Gate can invoke the weather_history subsystem.
    """
    
    @staticmethod
    def filter(canonical: CanonicalAcquiredData, location: str) -> Dict[str, Any]:
        """
        Takes the global canonical data and location.
        Returns a dictionary that the PredictionAdapter (Gate) will process.
        """
        # Return the regular atmospheric data and location info to the Gate
        return {
            "location": location,
            "regular": canonical
        }
