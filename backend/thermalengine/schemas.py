"""
HeatIQ Thermal Engine — Public Data Contract Schemas and Validation Layer
Data Contract: v0.1  |  Component: Data / Backend / Thermal Engine (§4.1, §7, §8, §9, §25, §26, §27)

This module defines the public contract boundary for the Thermal Calculation Engine.
It isolates other backend modules from the internal calculation engine data structures.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, Any, Literal, Union, List


class ThermalInputValidationError(ValueError):
    """Raised when structured input violates the canonical data contract (§27)."""
    pass


@dataclass
class ThermalInput:
    """
    Canonical Environmental Input Record conforming to Data Contract §5, §7, §8, §26.
    Represents one geographic area observation/forecast at one timestamp.
    """
    # Identification Schema (§7)
    area_id: str
    timestamp: str  # ISO-8601 string (e.g., "2026-05-20T14:00:00+05:30" or UTC "2026-05-20T14:00:00Z")

    # Environmental Input Schema — Required (§8)
    temperature_c: float
    relative_humidity_pct: float

    # Environmental Input Schema — Provisional / Optional (§8)
    wind_speed_ms: Optional[float] = None
    solar_radiation_wm2: Optional[float] = None
    dew_point_c: Optional[float] = None
    cloud_cover_pct: Optional[float] = None
    precipitation_mm: Optional[float] = None

    # Identification Schema — Provisional / Optional (§7)
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Contextual metadata (§10-12)
    population: Optional[int] = None
    elderly_fraction: Optional[float] = None

    def validate(self) -> None:
        """
        Validate the record against the HeatIQ Canonical Data Contract (§27).
        Raises ThermalInputValidationError if constraints are violated.
        """
        # 1. Identification validation (§7)
        if not isinstance(self.area_id, str) or not self.area_id.strip():
            raise ThermalInputValidationError("REQUIRED: 'area_id' must be a non-empty string (§7)")

        if not isinstance(self.timestamp, str) or not self.timestamp.strip():
            raise ThermalInputValidationError("REQUIRED: 'timestamp' must be a non-empty ISO-8601 string (§7)")

        # Validate ISO-8601 timestamp parsing (§7, §27)
        try:
            # Handles trailing Z or offset formats
            ts_str = self.timestamp.replace("Z", "+00:00")
            datetime.fromisoformat(ts_str)
        except Exception as err:
            raise ThermalInputValidationError(
                f"INVALID: 'timestamp' '{self.timestamp}' is not a valid ISO-8601 timestamp: {err} (§7, §27)"
            )

        # 2. Required Environmental Fields (§8)
        for req_field in ("temperature_c", "relative_humidity_pct"):
            val = getattr(self, req_field, None)
            if val is None:
                raise ThermalInputValidationError(f"REQUIRED: '{req_field}' is missing or None (§8)")
            if not isinstance(val, (int, float)) or (isinstance(val, float) and math.isnan(val)):
                raise ThermalInputValidationError(f"REQUIRED: '{req_field}' must be a valid number (§8)")
            if math.isinf(val):
                raise ThermalInputValidationError(f"INVALID: '{req_field}' cannot be infinite (§27)")

        # 3. Plausible Physical Ranges & Unit Checks (§26, §27)
        if not (-50.0 <= self.temperature_c <= 60.0):
            raise ThermalInputValidationError(
                f"OUT_OF_RANGE: 'temperature_c' ({self.temperature_c}°C) must be in range [-50.0, 60.0] (§26, §27)"
            )

        if not (0.0 <= self.relative_humidity_pct <= 100.0):
            raise ThermalInputValidationError(
                f"OUT_OF_RANGE: 'relative_humidity_pct' ({self.relative_humidity_pct}%) must be in range [0.0, 100.0] (§8, §27)"
            )

        # 4. Optional Environmental Fields Validation (§8, §27)
        if self.wind_speed_ms is not None:
            if not isinstance(self.wind_speed_ms, (int, float)) or math.isnan(self.wind_speed_ms):
                raise ThermalInputValidationError("INVALID: 'wind_speed_ms' must be a valid number if provided (§8)")
            if not (0.0 <= self.wind_speed_ms <= 50.0):
                raise ThermalInputValidationError(
                    f"OUT_OF_RANGE: 'wind_speed_ms' ({self.wind_speed_ms} m/s) must be in range [0.0, 50.0] (§27)"
                )

        if self.solar_radiation_wm2 is not None:
            if not isinstance(self.solar_radiation_wm2, (int, float)) or math.isnan(self.solar_radiation_wm2):
                raise ThermalInputValidationError("INVALID: 'solar_radiation_wm2' must be a valid number if provided (§8)")
            if not (0.0 <= self.solar_radiation_wm2 <= 1500.0):
                raise ThermalInputValidationError(
                    f"OUT_OF_RANGE: 'solar_radiation_wm2' ({self.solar_radiation_wm2} W/m²) must be in range [0.0, 1500.0] (§27)"
                )

        if self.latitude is not None:
            if not (-90.0 <= self.latitude <= 90.0):
                raise ThermalInputValidationError(f"OUT_OF_RANGE: 'latitude' ({self.latitude}) must be in range [-90.0, 90.0] (§7)")

        if self.longitude is not None:
            if not (-180.0 <= self.longitude <= 180.0):
                raise ThermalInputValidationError(f"OUT_OF_RANGE: 'longitude' ({self.longitude}) must be in range [-180.0, 180.0] (§7)")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ThermalInput:
        """Construct and validate a ThermalInput instance from a dictionary."""
        if not isinstance(data, dict):
            raise ThermalInputValidationError(f"Input data must be a dictionary, got {type(data).__name__}")
        
        valid_keys = set(cls.__dataclass_fields__.keys())
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        
        try:
            instance = cls(**filtered)
        except TypeError as exc:
            raise ThermalInputValidationError(f"Failed to instantiate ThermalInput: {exc}")
        
        instance.validate()
        return instance

    @classmethod
    def from_json(cls, json_str: str) -> ThermalInput:
        """Construct and validate a ThermalInput instance from a JSON string."""
        try:
            parsed = json.loads(json_str)
        except Exception as exc:
            raise ThermalInputValidationError(f"Malformed JSON input: {exc}")
        return cls.from_dict(parsed)

    @classmethod
    def from_json_list(cls, json_str: str) -> List[ThermalInput]:
        """Construct and validate a list of ThermalInput instances from a JSON string."""
        try:
            parsed = json.loads(json_str)
        except Exception as exc:
            raise ThermalInputValidationError(f"Malformed JSON input: {exc}")
        if not isinstance(parsed, list):
            raise ThermalInputValidationError(f"Expected a JSON list of objects, got {type(parsed).__name__}")
        return [cls.from_dict(item) for item in parsed]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a standard dictionary representation."""
        return asdict(self)

    def to_json(self) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.to_dict())


@dataclass
class ThermalOutput:
    """
    Canonical Thermal Calculation Output conforming to Data Contract §9, §20, §25, §28.
    Exposes physical thermal indices, composite HTSI score, component subscores, and traceability metadata.
    """
    # Identification (§7)
    area_id: str
    timestamp: str

    # Derived Physical Thermal Indices (§9)
    heat_index_c: Optional[float]           # Apparent temperature (°C, NOAA NWS Rothfusz 1990)
    utci_c: Optional[float]                 # Universal Thermal Climate Index (°C, COST Action 730)
    wbgt_c: Optional[float]                 # Wet Bulb Globe Temperature (°C, ISO 7243:2017)

    # Composite Thermal Stress Index (§9, §20, §33)
    htsi: Optional[float]                   # Dimensionless composite score 0–100 (0=safe, 100=extreme)
    htsi_category: Optional[str]            # Risk level: LOW / MODERATE / HIGH / VERY_HIGH / EXTREME

    # Component Normalized Scores (0–100 before weighting)
    hi_score: Optional[float] = None
    wbgt_score: Optional[float] = None
    utci_score: Optional[float] = None

    # Traceability & Metadata (§25, §29, §30)
    calculation_status: Literal["COMPUTED", "PARTIAL", "INSUFFICIENT_DATA"] = "COMPUTED"
    weights_used: Dict[str, float] = field(default_factory=dict)
    indices_computed: List[str] = field(default_factory=list)
    indices_skipped: List[str] = field(default_factory=list)
    method_version: str = "HTSI-v1"

    def to_dict(self) -> Dict[str, Any]:
        """Convert output to a clean JSON-serializable dictionary."""
        return asdict(self)

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serialize output to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def to_json_list(cls, outputs: List[ThermalOutput], indent: Optional[int] = None) -> str:
        """Serialize a collection of ThermalOutput instances to a JSON string."""
        return json.dumps([o.to_dict() for o in outputs], indent=indent)
