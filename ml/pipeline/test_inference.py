import sys
from pathlib import Path
import pandas as pd
from datetime import datetime
import traceback

sys.path.append(str(Path(__file__).parent))

from ml.inference.artifact import load_model_artifact, D1_MAX_AIR_TEMPERATURE_CONTRACT

def main():
    try:
        artifact_path = Path(__file__).parent.parent / "artifacts" / "linear_regression-v1" / "linear_regression-v1.pkl"
        artifact = load_model_artifact(artifact_path, expected_contract=D1_MAX_AIR_TEMPERATURE_CONTRACT)
        print("Model loaded successfully.")
        print(f"Model version: {artifact.model_version}")
        print(f"Format version: {artifact.format_version}")
        print(f"Feature count: {len(artifact.metadata.feature_names)}")
        print(f"Features: {artifact.metadata.feature_names}")
        print(f"Target: {artifact.metadata.target_name} ({artifact.metadata.target_unit})")

        # Test case 1: Canonical 24-field
        test_case_1 = {
            "temperature_max_c": 38.5,
            "temperature_min_c": 25.2,
            "temperature_mean_c": 32.1,
            "dewpoint_mean_c": 15.4,
            "relative_humidity_mean_pct": 45.2,
            "relative_humidity_max_pct": 65.0,
            "wind_speed_mean_ms": 3.2,
            "wind_speed_max_ms": 5.1,
            "solar_radiation_max_wm2": 950.0,
            "solar_radiation_mean_wm2": 320.0,
            "thermal_radiation_mean_wm2": 380.0,
            "surface_pressure_mean_pa": 100100.0,
            "temperature_max_lag_1d": 37.8,
            "temperature_max_lag_2d": 36.5,
            "temperature_max_lag_3d": 36.0,
            "temperature_min_lag_1d": 24.5,
            "temperature_mean_prev_3d": 31.0,
            "temperature_mean_prev_5d": 30.5,
            "temperature_max_prev_3d": 37.8,
            "humidity_mean_prev_3d": 48.5,
            "month": 5,
            "day_of_year": 145,
            "day_of_year_sin": 0.587,
            "day_of_year_cos": -0.809
        }

        # create dataframe keeping exactly the required column order
        df1 = pd.DataFrame([test_case_1], columns=artifact.metadata.feature_names)
        
        # We need a float prediction
        pred1 = artifact.predict_one(df1, feature_date=datetime(2024, 5, 24))
        print(f"Prediction 1: {pred1.prediction} {pred1.target_unit}")

        # Test case 2: Cool day
        test_case_2 = test_case_1.copy()
        test_case_2.update({"temperature_max_c": 20.0, "temperature_min_c": 10.0, "temperature_mean_c": 15.0})
        df2 = pd.DataFrame([test_case_2], columns=artifact.metadata.feature_names)
        pred2 = artifact.predict_one(df2, feature_date=datetime(2024, 5, 25))
        print(f"Prediction 2 (cool): {pred2.prediction} {pred2.target_unit}")

        # Test case 3: Extreme hot day
        test_case_3 = test_case_1.copy()
        test_case_3.update({"temperature_max_c": 45.0, "temperature_min_c": 30.0, "temperature_mean_c": 38.0})
        df3 = pd.DataFrame([test_case_3], columns=artifact.metadata.feature_names)
        pred3 = artifact.predict_one(df3, feature_date=datetime(2024, 5, 26))
        print(f"Prediction 3 (extreme hot): {pred3.prediction} {pred3.target_unit}")
        
        # Test case 4: Missing feature
        test_case_4 = test_case_1.copy()
        del test_case_4["temperature_max_c"]
        try:
            df4 = pd.DataFrame([test_case_4]) # no column enforcement
            artifact.predict_one(df4)
            print("ERROR: Test case 4 (missing feature) did not raise an exception")
        except Exception as e:
            print(f"Test case 4 (missing feature) successfully failed: {e}")

    except Exception as e:
        print(f"Error during execution:")
        traceback.print_exc()

if __name__ == '__main__':
    main()
