"""
HeatIQ Ward Filter Module

Combines Thermal, Mortality, Info Pool, and Resource Pool data into a Complete Ward Context,
and evaluates it against a deterministic rule engine to determine intervention severity.
"""

from .schemas import WardContext, WardFilterResult, WardFilterInputValidationError
from .infosmasher import InfoSmasher
from .engine import IntelligentFilteringEngine, Rule
from .service import WardFilterGateway, filter_ward, filter_wards

__all__ = [
    "WardContext",
    "WardFilterResult",
    "WardFilterInputValidationError",
    "InfoSmasher",
    "IntelligentFilteringEngine",
    "Rule",
    "WardFilterGateway",
    "filter_ward",
    "filter_wards"
]
