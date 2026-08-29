"""
HeatIQ Data Lake

Maintains the system's own canonical, locally stored representation of 
external government information and resource datasets.
"""

from .core.cache_manager import get_canonical_info_pool, get_canonical_resource_pool

__all__ = [
    "get_canonical_info_pool",
    "get_canonical_resource_pool"
]
