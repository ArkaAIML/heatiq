import argparse
import json
import sys
import os

# Ensure the root is in PYTHONPATH so this script can be run easily
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.wiring.wire1 import process_location
from backend.wiring.wire2 import get_recommendation

def main():
    parser = argparse.ArgumentParser(description="Live End-to-End HeatIQ Backend Test")
    parser.add_argument("--location", type=str, default="Bhubaneswar", help="Location to process")
    parser.add_argument("--ward", type=str, required=True, help="Specific ward to fetch recommendation for (e.g., WARD_002)")
    
    args = parser.parse_args()
    
    print(f"============================================================")
    print(f"Executing Wire 1 (Data Acquisition -> Store) for: {args.location}")
    print(f"Provider: {os.environ.get('HEATIQ_WEATHER_PROVIDER', 'open-meteo')}")
    print(f"============================================================")
    
    results = process_location(args.location)
    
    if not results:
        print(f"Warning: No wards were processed. Is there data for {args.location}?")
    else:
        print(f"Successfully processed {len(results)} wards.")
        print("Final Ward Filter Outputs:")
        for res in results:
            print(f"  - {res.area_id}: {res.calculation_status} ({res.severity})")
            
    print(f"\n============================================================")
    print(f"Executing Wire 2 (Store -> Recommendation) for: {args.ward}")
    print(f"============================================================")
    
    rec_result = get_recommendation(args.ward)
    
    print(json.dumps(rec_result, indent=2))
    print(f"============================================================")

if __name__ == "__main__":
    main()
