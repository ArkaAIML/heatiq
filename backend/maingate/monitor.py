from typing import Dict, Any, List
from datetime import datetime, timezone
import collections

# A simple in-memory store holding the last N requests for the dashboard
MAX_REQUESTS = 100
request_log = collections.deque(maxlen=MAX_REQUESTS)

def add_request_trace(trace: Dict[str, Any]):
    """Appends a trace event to the live monitor."""
    trace["timestamp"] = datetime.now(timezone.utc).isoformat()
    request_log.appendleft(trace)

def get_recent_traces() -> List[Dict[str, Any]]:
    """Returns the recent traces."""
    return list(request_log)
