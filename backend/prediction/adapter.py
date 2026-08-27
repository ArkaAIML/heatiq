from typing import List
from datetime import datetime, timezone
from backend.thermalengine.schemas import ThermalOutput
from backend.prediction.schemas import PredictionOutput
from dummyml.service import dummy_prediction_and_recommendation_batch

class PredictionAdapter:
    """
    Adapter boundary insulating HeatIQ from the ML Prediction implementation.
    Translates canonical ThermalOutput into the ML Engine, and maps the proprietary
    or placeholder ML output into the canonical PredictionOutput schema.
    """
    
    @staticmethod
    def predict_batch(thermal_outputs: List[ThermalOutput]) -> List[PredictionOutput]:
        """
        Executes the prediction engine for a batch of ThermalOutputs.
        Preserves the multi-ward concurrency boundary.
        """
        # Call the external/placeholder ML engine
        dummy_results = dummy_prediction_and_recommendation_batch(thermal_outputs)
        
        predictions = []
        for t_out, d_res in zip(thermal_outputs, dummy_results):
            # Assert area_id alignment to prevent cross-ward contamination
            if t_out.area_id != d_res.prediction.area_id:
                raise ValueError(f"Adapter error: area_id mismatch between Thermal ({t_out.area_id}) and ML ({d_res.prediction.area_id})")
                
            now_iso = datetime.now(timezone.utc).isoformat()
            
            # Map dummy proprietary output into canonical data contract schema (§20)
            pred = PredictionOutput(
                area_id=t_out.area_id,
                prediction_generated_at=now_iso,
                forecast_for=t_out.timestamp, # Simplified assumption for prototype
                forecast_horizon_days=1,
                thermal_hazard_score=0.0, # Dummy values to satisfy schema
                predicted_max_utci_c=0.0,
                thermal_stress_level="DUMMY",
                model_name="dummyml",
                model_version="v0.1"
            )
            predictions.append(pred)
            
        return predictions
