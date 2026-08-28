import requests
from typing import Dict, Any, Tuple, Optional

BASE_URL = "http://127.0.0.1:8000/api"

class HeatIQClient:
    def __init__(self):
        self.session = requests.Session()
        
    def check_health(self) -> bool:
        """Pings the backend to see if it's reachable."""
        try:
            resp = self.session.get(f"{BASE_URL}/health", timeout=3)
            return resp.status_code == 200
        except requests.RequestException:
            return False
            
    def set_api_key(self, api_key: str):
        """Sets the API key for future requests."""
        self.session.headers.update({"X-API-Key": api_key})
        
    def process_location(self, location: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """Sends a PLACE NAME to Wire 1."""
        try:
            resp = self.session.post(
                f"{BASE_URL}/process", 
                json={"location": location},
                timeout=30 # Wire 1 can take a while for a whole city
            )
            
            if resp.status_code == 200:
                return True, resp.json(), "Success"
            elif resp.status_code == 401 or resp.status_code == 403:
                return False, None, "Invalid or revoked API key"
            else:
                try:
                    err = resp.json().get("detail", resp.text)
                except:
                    err = resp.text
                return False, None, f"HTTP {resp.status_code}: {err}"
                
        except requests.Timeout:
            return False, None, "Request timed out waiting for backend."
        except requests.ConnectionError:
            return False, None, "Connection failed. Is the backend running?"
        except Exception as e:
            return False, None, f"Error: {str(e)}"
            
    def process_area_id(self, area_id: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """Sends an AREA ID to Wire 2 / Recommendation Engine."""
        try:
            resp = self.session.post(
                f"{BASE_URL}/process", 
                json={"area_id": area_id},
                timeout=15
            )
            
            if resp.status_code == 200:
                return True, resp.json(), "Success"
            elif resp.status_code == 422:
                try:
                    detail = resp.json().get("detail", "")
                    if "ward_context_not_available" in detail:
                        return False, None, "ward_context_not_available"
                except:
                    pass
                return False, None, "Unprocessable Entity (422)"
            elif resp.status_code == 401 or resp.status_code == 403:
                return False, None, "Invalid or revoked API key"
            else:
                try:
                    err = resp.json().get("detail", resp.text)
                except:
                    err = resp.text
                return False, None, f"HTTP {resp.status_code}: {err}"
                
        except requests.Timeout:
            return False, None, "Request timed out waiting for backend."
        except requests.ConnectionError:
            return False, None, "Connection failed. Is the backend running?"
        except Exception as e:
            return False, None, f"Error: {str(e)}"

client = HeatIQClient()
