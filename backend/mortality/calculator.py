"""
HeatIQ Mortality Risk Index — Calculation Logic Boundary
Data Contract: v0.1

Provides the MVP deterministic heuristic for Mortality Risk and establishes
the BaseMortalityRiskCalculator boundary for future ML model replacement.

This is an explainable, rule-based relative mortality-risk prioritization heuristic for the MVP.
It is not a calibrated epidemiological mortality model and does not produce a probability of death.
"""

from abc import ABC, abstractmethod
from typing import Optional

from backend.thermalengine import ThermalOutput
from .schemas import InfoPoolRecord, ResourcePoolRecord, MortalityOutput


class BaseMortalityRiskCalculator(ABC):
    """
    Abstract interface for Mortality Risk computation.
    Both the current MVP heuristic and the future ML model must implement this.
    """

    @abstractmethod
    def calculate(
        self,
        thermal: ThermalOutput,
        info: Optional[InfoPoolRecord] = None,
        resource: Optional[ResourcePoolRecord] = None
    ) -> MortalityOutput:
        """
        Compute mortality risk based on thermal hazard, exposure/vulnerability, and resources.
        """
        pass


class RuleBasedMortalityRiskCalculator(BaseMortalityRiskCalculator):
    """
    Explainable Rule-Based Relative Mortality-Risk Prioritization heuristic for the MVP.
    
    This is NOT a calibrated epidemiological mortality model.
    It produces a relative mortality-risk prioritization index, NOT a probability of death.
    
    Logic Principle:
    Heat-related mortality priority depends on:
    THERMAL HAZARD × POPULATION VULNERABILITY × POPULATION EXPOSURE × LIMITED RESPONSE CAPACITY
    """

    # --- MVP Configuration Constants (Engineering Assumptions) ---
    
    # Vulnerability Reference Assumptions
    ELDERLY_REFERENCE_FRACTION = 0.20  # 20% elderly is considered maximum reference vulnerability
    CHILD_REFERENCE_FRACTION = 0.20    # 20% child is considered maximum reference vulnerability
    
    # Exposure Reference Assumptions
    POPULATION_DENSITY_REFERENCE = 20000.0  # 20,000 persons/km2 is considered maximum reference density
    OUTDOOR_WORKER_REFERENCE_FRACTION = 0.50 # 50% outdoor workers is considered maximum reference exposure
    
    # Adaptive Capacity Reference Assumptions (per 10,000 population)
    HOSPITAL_COVERAGE_REFERENCE = 1.0  # 1 hospital per 10k population is considered maximum reference capacity
    COOLING_COVERAGE_REFERENCE = 2.0   # 2 cooling centres per 10k population is considered maximum reference capacity

    def calculate(
        self,
        thermal: ThermalOutput,
        info: Optional[InfoPoolRecord] = None,
        resource: Optional[ResourcePoolRecord] = None
    ) -> MortalityOutput:
        
        # 1. Missing Critical Data Check
        if thermal.htsi is None or thermal.calculation_status == "INSUFFICIENT_DATA":
            return MortalityOutput(
                area_id=thermal.area_id,
                timestamp=thermal.timestamp,
                calculation_status="INSUFFICIENT_DATA",
                method_version="RULE_BASED_MVP: MISSING_THERMAL_DATA"
            )

        reason_codes = []

        # --- HAZARD (H) ---
        H = thermal.htsi / 100.0
        H = max(0.0, min(H, 1.0))
        hazard_score = H * 100.0
        
        if hazard_score >= 75.0:
            reason_codes.append("SEVERE_THERMAL_STRESS")

        # --- EXPOSURE (E) ---
        E = 0.0
        if info:
            pop_dens = info.population_density or 0.0
            worker_frac = info.outdoor_worker_fraction or 0.0
            
            e_density = max(0.0, min(pop_dens / self.POPULATION_DENSITY_REFERENCE, 1.0))
            e_workers = max(0.0, min(worker_frac / self.OUTDOOR_WORKER_REFERENCE_FRACTION, 1.0))
            
            E = (0.60 * e_density) + (0.40 * e_workers)
            if E >= 0.75:
                reason_codes.append("HIGH_POPULATION_EXPOSURE")
                
        exposure_score = E * 100.0

        # --- VULNERABILITY (V) ---
        V = 0.0
        if info:
            elderly = info.elderly_fraction or 0.0
            child = info.child_fraction or 0.0
            
            v_elderly = max(0.0, min(elderly / self.ELDERLY_REFERENCE_FRACTION, 1.0))
            v_child = max(0.0, min(child / self.CHILD_REFERENCE_FRACTION, 1.0))
            
            V = (0.70 * v_elderly) + (0.30 * v_child)
            if V >= 0.75:
                reason_codes.append("HIGH_POPULATION_VULNERABILITY")
                
        vulnerability_score = V * 100.0

        # --- ADAPTIVE CAPACITY (A) ---
        A = 0.0
        if resource and info and info.population and info.population > 0:
            population = info.population
            hosp_count = resource.hospital_count or 0
            cool_count = resource.cooling_centre_count or 0
            
            hosp_per_10k = (hosp_count / population) * 10000.0
            cool_per_10k = (cool_count / population) * 10000.0
            
            a_hospital = max(0.0, min(hosp_per_10k / self.HOSPITAL_COVERAGE_REFERENCE, 1.0))
            a_cooling = max(0.0, min(cool_per_10k / self.COOLING_COVERAGE_REFERENCE, 1.0))
            
            A = (0.70 * a_hospital) + (0.30 * a_cooling)
            if A < 0.25:
                reason_codes.append("LOW_ADAPTIVE_CAPACITY")
        elif resource:
            # Resource capacity cannot be reliably computed without population.
            reason_codes.append("UNKNOWN_ADAPTIVE_CAPACITY")
            
        adaptive_capacity_score = A * 100.0

        # --- MULTIPLICATIVE RISK COMPOSITION ---
        
        # Hazard is the primary driver. Vulnerability and Exposure act as bounded amplifiers.
        vulnerability_factor = 1.00 + 0.30 * V  # [1.00, 1.30]
        exposure_factor = 1.00 + 0.30 * E       # [1.00, 1.30]
        
        base_risk = 100.0 * H * vulnerability_factor * exposure_factor
        
        # Adaptive capacity acts as a bounded mitigation factor.
        resource_factor = 1.00 - 0.20 * A       # [0.80, 1.00]
        
        final_risk = base_risk * resource_factor
        risk_score = max(0.0, min(final_risk, 100.0))

        # --- CATEGORIZATION ---
        if risk_score >= 75.0:
            risk_level = "EXTREME"
        elif risk_score >= 50.0:
            risk_level = "HIGH"
        elif risk_score >= 25.0:
            risk_level = "MODERATE"
        else:
            risk_level = "LOW"

        return MortalityOutput(
            area_id=thermal.area_id,
            timestamp=thermal.timestamp,
            hazard_score=round(hazard_score, 2),
            exposure_score=round(exposure_score, 2),
            vulnerability_score=round(vulnerability_score, 2),
            adaptive_capacity_score=round(adaptive_capacity_score, 2),
            risk_score=round(risk_score, 2),
            risk_level=risk_level,
            calculation_status="COMPUTED",
            reason_codes=reason_codes,
            method_version="RULE_BASED_MVP_v2"
        )
