from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass(frozen=True)
class Material:
    name: str
    density_kg_m3: float
    elastic_modulus_gpa: float
    poisson_ratio: float
    yield_strength_mpa: float
    ultimate_strength_mpa: float
    endurance_limit_mpa: float


@dataclass(frozen=True)
class SafetyFactors:
    bearing: float = 1.8
    shear: float = 1.8
    bending: float = 2.0


@dataclass(frozen=True)
class FatigueConfig:
    enabled: bool = True
    minimum_fatigue_sf: float = 1.2
    torque_min_ratio: float = 0.1
    dynamic_amplification: float = 1.25
    surface_factor: float = 0.85
    size_factor: float = 0.90
    reliability_factor: float = 0.868
    load_factor: float = 1.0
    temperature_factor: float = 1.0
    miscellaneous_factor: float = 1.0


@dataclass(frozen=True)
class SolverConfig:
    stage_ratio: int
    motor_speed_rpm: float
    target_output_torque_nm: float
    material: Material
    safety_factors: SafetyFactors
    fatigue: FatigueConfig = field(default_factory=FatigueConfig)
    min_ring_pitch_radius_mm: float = 80.0
    max_ring_pitch_radius_mm: float = 500.0
    ring_pitch_radius_step_mm: float = 5.0
    # Ratio relative to ring pitch radius, not pin-to-pin spacing.
    ring_roller_radius_ratio_min: float = 0.005
    ring_roller_radius_ratio_max: float = 0.150
    ring_roller_radius_ratio_step: float = 0.005
    eccentricity_ratio_min: float = 0.005
    eccentricity_ratio_max: float = 0.050
    eccentricity_ratio_step: float = 0.005
    disc_thickness_min_mm: float = 12.0
    disc_thickness_max_mm: float = 60.0
    disc_thickness_step_mm: float = 1.0
    output_pin_counts: Tuple[int, ...] = (4, 6, 8)
    output_pin_circle_ratios: Tuple[float, ...] = (0.40, 0.45, 0.50, 0.55, 0.60)
    output_roller_fraction_choices: Tuple[float, ...] = (0.28, 0.32, 0.36, 0.40, 0.44)
    # Diametral clearance term used directly in output hole sizing.
    clearance_mm: float = 0.5
    loaded_lobes: int = 3
    loaded_output_pins: int = 3
    dual_disc_count: int = 2
    eccentric_bore_diameter_mm: float | None = None
    min_eccentric_bore_sf: float = 1.2
    min_output_shaft_sf: float = 1.2
    min_profile_radius_mm: float = 0.05


@dataclass
class StrengthReport:
    allowable_bearing_mpa: float
    allowable_shear_mpa: float
    allowable_bending_mpa: float
    bearing_stress_mpa: float
    output_pin_shear_stress_mpa: float
    lobe_shear_stress_mpa: float
    output_hole_ligament_bending_stress_mpa: float
    sf_bearing: float
    sf_output_pin_shear: float
    sf_lobe_shear: float
    sf_ligament_bending: float


@dataclass
class FatigueReport:
    corrected_endurance_limit_mpa: float
    ultimate_strength_mpa: float
    bearing_goodman_sf: float
    output_pin_shear_goodman_sf: float
    lobe_shear_goodman_sf: float
    ligament_bending_goodman_sf: float
    minimum_fatigue_sf: float


@dataclass
class Candidate:
    stage_ratio: int
    ring_pin_count: int
    lobe_count: int
    material_name: str
    ring_pitch_radius_mm: float
    ring_pitch_diameter_mm: float
    ring_roller_radius_mm: float
    ring_roller_diameter_mm: float
    eccentricity_mm: float
    eccentricity_ratio: float
    disc_thickness_mm: float
    estimated_disc_outer_diameter_mm: float
    output_pin_count: int
    output_pin_circle_radius_mm: float
    output_pin_circle_diameter_mm: float
    output_roller_diameter_mm: float
    output_hole_diameter_mm: float
    ring_pin_center_spacing_mm: float
    output_pin_center_spacing_mm: float
    radial_margin_to_ring_mm: float
    total_tangential_force_N: float
    force_per_loaded_lobe_N: float
    force_per_loaded_output_pin_N: float
    estimated_output_speed_rpm: float
    allowable_bearing_mpa: float
    allowable_shear_mpa: float
    allowable_bending_mpa: float
    bearing_stress_mpa: float
    output_pin_shear_stress_mpa: float
    lobe_shear_stress_mpa: float
    output_hole_ligament_bending_stress_mpa: float
    sf_bearing: float
    sf_output_pin_shear: float
    sf_lobe_shear: float
    sf_ligament_bending: float
    minimum_strength_sf: float
    corrected_endurance_limit_mpa: float
    bearing_goodman_sf: float
    output_pin_shear_goodman_sf: float
    lobe_shear_goodman_sf: float
    ligament_bending_goodman_sf: float
    minimum_fatigue_sf: float
    eccentric_shaft_hole_diameter_mm: float
    eccentric_bore_bearing_stress_mpa: float
    sf_eccentric_bore: float
    estimated_required_shaft_diameter_mm: float
    selected_output_shaft_diameter_mm: float
    output_shaft_torsional_sf: float
    minimum_profile_radius_mm: float
    estimated_total_volume_mm3: float
    estimated_total_mass_kg: float
    score: float
    notes: str


@dataclass(frozen=True)
class RatioSelection:
    representative_stage_ratio: int
    source_combo: Optional[Tuple[int, ...]]
