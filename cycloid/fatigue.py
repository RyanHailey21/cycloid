from __future__ import annotations

import math

from .models import FatigueConfig, FatigueReport, Material, StrengthReport


def corrected_endurance_limit(material: Material, fatigue: FatigueConfig) -> float:
    modifiers = (
        fatigue.surface_factor
        * fatigue.size_factor
        * fatigue.reliability_factor
        * fatigue.load_factor
        * fatigue.temperature_factor
        * fatigue.miscellaneous_factor
    )
    return material.endurance_limit_mpa * max(modifiers, 1e-9)


def goodman_sf(
    *,
    stress_amplitude_mpa: float,
    stress_mean_mpa: float,
    endurance_limit_mpa: float,
    ultimate_strength_mpa: float,
) -> float:
    denominator = (stress_amplitude_mpa / max(endurance_limit_mpa, 1e-9)) + (
        stress_mean_mpa / max(ultimate_strength_mpa, 1e-9)
    )
    if denominator <= 0:
        return math.inf
    return 1.0 / denominator


def equivalent_normal_from_shear(shear_stress_mpa: float) -> float:
    return math.sqrt(3.0) * shear_stress_mpa


def split_mean_and_alternating(max_stress_mpa: float, torque_min_ratio: float):
    ratio = max(min(torque_min_ratio, 1.0), 0.0)
    min_stress = ratio * max_stress_mpa
    stress_mean = 0.5 * (max_stress_mpa + min_stress)
    stress_alt = 0.5 * (max_stress_mpa - min_stress)
    return stress_mean, stress_alt


def evaluate_fatigue(
    *,
    material: Material,
    fatigue: FatigueConfig,
    strength: StrengthReport,
) -> FatigueReport:
    se = corrected_endurance_limit(material, fatigue)
    sut = material.ultimate_strength_mpa

    dynamic = max(fatigue.dynamic_amplification, 1e-9)
    bearing_peak = dynamic * strength.bearing_stress_mpa
    pin_shear_peak = dynamic * strength.output_pin_shear_stress_mpa
    lobe_shear_peak = dynamic * strength.lobe_shear_stress_mpa
    ligament_peak = dynamic * strength.output_hole_ligament_bending_stress_mpa

    bearing_mean, bearing_alt = split_mean_and_alternating(
        bearing_peak, fatigue.torque_min_ratio
    )
    pin_mean_shear, pin_alt_shear = split_mean_and_alternating(
        pin_shear_peak, fatigue.torque_min_ratio
    )
    lobe_mean_shear, lobe_alt_shear = split_mean_and_alternating(
        lobe_shear_peak, fatigue.torque_min_ratio
    )
    ligament_mean, ligament_alt = split_mean_and_alternating(
        ligament_peak, fatigue.torque_min_ratio
    )

    pin_mean_eq = equivalent_normal_from_shear(pin_mean_shear)
    pin_alt_eq = equivalent_normal_from_shear(pin_alt_shear)
    lobe_mean_eq = equivalent_normal_from_shear(lobe_mean_shear)
    lobe_alt_eq = equivalent_normal_from_shear(lobe_alt_shear)

    bearing_sf = goodman_sf(
        stress_amplitude_mpa=bearing_alt,
        stress_mean_mpa=bearing_mean,
        endurance_limit_mpa=se,
        ultimate_strength_mpa=sut,
    )
    pin_sf = goodman_sf(
        stress_amplitude_mpa=pin_alt_eq,
        stress_mean_mpa=pin_mean_eq,
        endurance_limit_mpa=se,
        ultimate_strength_mpa=sut,
    )
    lobe_sf = goodman_sf(
        stress_amplitude_mpa=lobe_alt_eq,
        stress_mean_mpa=lobe_mean_eq,
        endurance_limit_mpa=se,
        ultimate_strength_mpa=sut,
    )
    ligament_sf = goodman_sf(
        stress_amplitude_mpa=ligament_alt,
        stress_mean_mpa=ligament_mean,
        endurance_limit_mpa=se,
        ultimate_strength_mpa=sut,
    )

    return FatigueReport(
        corrected_endurance_limit_mpa=se,
        ultimate_strength_mpa=sut,
        bearing_goodman_sf=bearing_sf,
        output_pin_shear_goodman_sf=pin_sf,
        lobe_shear_goodman_sf=lobe_sf,
        ligament_bending_goodman_sf=ligament_sf,
        minimum_fatigue_sf=min(bearing_sf, pin_sf, lobe_sf, ligament_sf),
    )


def is_fatigue_acceptable(report: FatigueReport, fatigue: FatigueConfig) -> bool:
    return report.minimum_fatigue_sf >= fatigue.minimum_fatigue_sf
