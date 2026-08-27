"""
Unit tests for WBGT module
Branch: feature/wbgt-calculation
Contract: §4.1, §8, §9, §25, §27, §26
"""

import os
import sys
import pytest
import math

_htsi_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _htsi_root not in sys.path:
    sys.path.insert(0, _htsi_root)

from thermal.wbgt import (
    WBGTEngine,
    CanonicalThermalInput,
    WBGTValidationError,
    WBGTDerived,
    compute_wbgt_outdoor,
    compute_wbgt_indoor,
)


class TestWBGTContract:
    """Test contract compliance (§4.1, §8, §9, §25, §27)"""
    
    def test_canonical_record_identification(self):
        """§7 identification schema required."""
        rec = CanonicalThermalInput(
            area_id="WARD_001",
            timestamp="2026-05-20T10:00:00Z",
            temperature_c=30.0,
            relative_humidity_pct=50.0
        )
        assert rec.area_id == "WARD_001"
        assert "2026" in rec.timestamp
    
    def test_required_environmental_fields(self):
        """§8 required: temperature_c, relative_humidity_pct."""
        rec = CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T10:00:00Z",
            temperature_c=32.0,
            relative_humidity_pct=55.0
        )
        assert rec.temperature_c is not None
        assert rec.relative_humidity_pct is not None
    
    def test_outdoor_requires_wind_and_solar(self):
        """§8 outdoor WBGT requires wind_speed_ms and solar_radiation_wm2."""
        rec = CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T10:00:00Z",
            temperature_c=35.0,
            relative_humidity_pct=60.0,
            wind_speed_ms=2.5,
            solar_radiation_wm2=800.0
        )
        assert rec.wind_speed_ms is not None
        assert rec.solar_radiation_wm2 is not None
    
    def test_missing_temperature_no_fabrication(self):
        """§25: missing values never fabricated."""
        engine = WBGTEngine()
        bad = CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T10:00:00Z",
            temperature_c=None,  # Missing
            relative_humidity_pct=60.0
        )
        result = engine.calculate(bad)
        assert result.calculation_status == "INSUFFICIENT_DATA"
        assert result.wbgt_c is None
    
    def test_output_is_derived_wbgt_c(self):
        """§9 thermal index schema."""
        engine = WBGTEngine()
        rec = CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T10:00:00Z",
            temperature_c=35.0,
            relative_humidity_pct=60.0,
            wind_speed_ms=2.0,
            solar_radiation_wm2=700.0
        )
        out = engine.calculate(rec)
        assert hasattr(out, "wbgt_c")
        assert isinstance(out.wbgt_c, float) or out.wbgt_c is None
        assert out.method_version.startswith("Liljegren")
    
    def test_internal_units_celsius(self):
        """§26: internal temperature must be °C."""
        engine = WBGTEngine()
        out = engine.calculate(CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T10:00:00Z",
            temperature_c=35.0,
            relative_humidity_pct=60.0,
            wind_speed_ms=2.0,
            solar_radiation_wm2=700.0
        ))
        assert 25.0 < out.wbgt_c < 45.0  # Plausible WBGT range in °C
    
    def test_validation_rejects_impossible_rh(self):
        """§27: impossible environmental values rejected."""
        engine = WBGTEngine()
        rec = CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T10:00:00Z",
            temperature_c=30.0,
            relative_humidity_pct=150.0  # Invalid
        )
        with pytest.raises(WBGTValidationError):
            engine.validate_input(rec)
    
    def test_validation_rejects_impossible_wind(self):
        """§27: impossible wind speed rejected."""
        engine = WBGTEngine()
        rec = CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T10:00:00Z",
            temperature_c=30.0,
            relative_humidity_pct=50.0,
            wind_speed_ms=100.0  # Impossible
        )
        with pytest.raises(WBGTValidationError):
            engine.validate_input(rec, require_outdoor=True)
    
    def test_validation_rejects_impossible_solar(self):
        """§27: impossible solar radiation rejected."""
        engine = WBGTEngine()
        rec = CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T10:00:00Z",
            temperature_c=30.0,
            relative_humidity_pct=50.0,
            wind_speed_ms=2.0,
            solar_radiation_wm2=2000.0  # Too high
        )
        with pytest.raises(WBGTValidationError):
            engine.validate_input(rec, require_outdoor=True)
    
    def test_documentation_contains_formula(self):
        """§4.1 / §9: must document formula and assumptions."""
        meta = WBGTEngine().documentation()
        assert "formula_library" in meta
        assert "assumptions" in meta
        assert "fallback_behaviour" in meta
        assert "ISO 7243" in meta["formula_library"]


class TestWBGTCalculationMethods:
    """Test different calculation methods work correctly."""
    
    def test_outdoor_full_method(self):
        """OUTDOOR_FULL with all inputs available."""
        engine = WBGTEngine(prefer_outdoor=True)
        rec = CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T14:00:00Z",
            temperature_c=38.0,
            relative_humidity_pct=50.0,
            wind_speed_ms=2.0,
            solar_radiation_wm2=800.0
        )
        result = engine.calculate(rec)
        assert result.calculation_method == "OUTDOOR_FULL"
        assert result.calculation_status == "COMPUTED"
        assert result.wbgt_c > 30.0  # Should be high for these conditions
    
    def test_outdoor_simplified_method(self):
        """OUTDOOR_SIMPLIFIED when solar missing but wind available."""
        engine = WBGTEngine(prefer_outdoor=True)
        rec = CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T14:00:00Z",
            temperature_c=35.0,
            relative_humidity_pct=60.0,
            wind_speed_ms=2.5,
            solar_radiation_wm2=None  # Missing
        )
        result = engine.calculate(rec)
        assert result.calculation_method == "OUTDOOR_SIMPLIFIED"
        assert result.calculation_status == "COMPUTED"
        assert result.wbgt_c is not None
    
    def test_indoor_method(self):
        """INDOOR when no wind/solar available."""
        engine = WBGTEngine(prefer_outdoor=True)
        rec = CanonicalThermalInput(
            area_id="W1",
            timestamp="2026-05-20T14:00:00Z",
            temperature_c=32.0,
            relative_humidity_pct=70.0,
            wind_speed_ms=None,
            solar_radiation_wm2=None
        )
        result = engine.calculate(rec)
        assert result.calculation_method == "INDOOR"
        assert result.calculation_status == "COMPUTED"
        assert result.wbgt_c is not None
    
    def test_wbgt_increases_with_temperature(self):
        """WBGT should increase with temperature."""
        engine = WBGTEngine()
        temps = [25.0, 30.0, 35.0, 40.0]
        wbgts = []
        
        for temp in temps:
            rec = CanonicalThermalInput(
                area_id="TEST",
                timestamp="2026-05-20T14:00:00Z",
                temperature_c=temp,
                relative_humidity_pct=60.0,
                wind_speed_ms=2.0,
                solar_radiation_wm2=700.0
            )
            result = engine.calculate(rec)
            wbgts.append(result.wbgt_c)
        
        # WBGT should be monotonically increasing
        for i in range(len(wbgts) - 1):
            assert wbgts[i] < wbgts[i + 1]
    
    def test_wbgt_increases_with_humidity(self):
        """WBGT should increase with humidity."""
        engine = WBGTEngine()
        humidities = [30.0, 50.0, 70.0, 90.0]
        wbgts = []
        
        for rh in humidities:
            rec = CanonicalThermalInput(
                area_id="TEST",
                timestamp="2026-05-20T14:00:00Z",
                temperature_c=35.0,
                relative_humidity_pct=rh,
                wind_speed_ms=2.0,
                solar_radiation_wm2=700.0
            )
            result = engine.calculate(rec)
            wbgts.append(result.wbgt_c)
        
        # WBGT should be monotonically increasing
        for i in range(len(wbgts) - 1):
            assert wbgts[i] < wbgts[i + 1]
    
    def test_wbgt_increases_with_solar(self):
        """WBGT should increase with solar radiation."""
        engine = WBGTEngine()
        solars = [0.0, 400.0, 800.0, 1200.0]
        wbgts = []
        
        for solar in solars:
            rec = CanonicalThermalInput(
                area_id="TEST",
                timestamp="2026-05-20T14:00:00Z",
                temperature_c=35.0,
                relative_humidity_pct=60.0,
                wind_speed_ms=2.0,
                solar_radiation_wm2=solar
            )
            result = engine.calculate(rec)
            wbgts.append(result.wbgt_c)
        
        # WBGT should be monotonically increasing
        for i in range(len(wbgts) - 1):
            assert wbgts[i] < wbgts[i + 1]


class TestWBGTRiskCategories:
    """Test ISO 7243 risk categorization."""
    
    def test_risk_categories_ordered(self):
        """Risk categories should be properly ordered."""
        engine = WBGTEngine()
        
        assert engine.get_risk_category(25.0) == "MINIMAL_RISK"
        assert engine.get_risk_category(29.0) == "LOW_RISK"
        assert engine.get_risk_category(31.5) == "MODERATE_RISK"
        assert engine.get_risk_category(33.0) == "HIGH_RISK"
        assert engine.get_risk_category(36.0) == "EXTREME_RISK"


class TestConvenienceFunctions:
    """Test module-level convenience functions."""
    
    def test_compute_wbgt_outdoor(self):
        """Test outdoor convenience function."""
        result = compute_wbgt_outdoor(
            temperature_c=35.0,
            relative_humidity_pct=60.0,
            wind_speed_ms=2.0,
            solar_radiation_wm2=700.0
        )
        assert result.calculation_method == "OUTDOOR_FULL"
        assert result.wbgt_c is not None
    
    def test_compute_wbgt_indoor(self):
        """Test indoor convenience function."""
        result = compute_wbgt_indoor(
            temperature_c=32.0,
            relative_humidity_pct=70.0
        )
        assert result.calculation_method == "INDOOR"
        assert result.wbgt_c is not None


class TestBatchProcessing:
    """Test batch calculation."""
    
    def test_batch_calculation(self):
        """Calculate WBGT for multiple records."""
        engine = WBGTEngine()
        
        records = [
            CanonicalThermalInput(
                area_id=f"WARD_{i:03d}",
                timestamp="2026-05-20T14:00:00Z",
                temperature_c=30.0 + i * 2,
                relative_humidity_pct=50.0 + i * 5,
                wind_speed_ms=2.0,
                solar_radiation_wm2=700.0
            )
            for i in range(5)
        ]
        
        results = engine.calculate_batch(records)
        
        assert len(results) == 5
        for res in results:
            assert res.calculation_status == "COMPUTED"
            assert res.wbgt_c is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])