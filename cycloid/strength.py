from __future__ import annotations

import math

from .models import SafetyFactors, StrengthReport


def compute_allowables(yield_strength_mpa: float, safety: SafetyFactors):
    # Static allowables based on common ductile-metal approximations.
    allowable_bearing = 0.9 * yield_strength_mpa / max(safety.bearing, 1e-9)
    allowable_shear = 0.58 * yield_strength_mpa / max(safety.shear, 1e-9)
    allowable_bending = yield_strength_mpa / max(safety.bending, 1e-9)
    return allowable_bearing, allowable_shear, allowable_bending


def evaluate_strength(
    *,
    force_per_output_pin_n: float,
    force_per_lobe_n: float,
    output_roller_diameter_mm: float,
    disc_thickness_mm: float,
    eccentricity_mm: float,
    output_hole_diameter_mm: float,
    output_pin_center_spacing_mm: float,
    yield_strength_mpa: float,
    safety: SafetyFactors,
) -> StrengthReport:
    allowable_bearing, allowable_shear, allowable_bending = compute_allowables(
        yield_strength_mpa, safety
    )

    bearing_stress = force_per_output_pin_n / max(
        output_roller_diameter_mm * disc_thickness_mm, 1e-9
    )

    output_pin_area = math.pi * (output_roller_diameter_mm ** 2) / 4.0
    output_pin_shear = force_per_output_pin_n / max(output_pin_area, 1e-9)

    lobe_shear_area = disc_thickness_mm * max(2.0 * eccentricity_mm, 1e-6)
    lobe_shear = force_per_lobe_n / lobe_shear_area

    ligament_width = max((output_pin_center_spacing_mm - output_hole_diameter_mm) / 2.0, 1e-6)
    ligament_bending = (6.0 * force_per_output_pin_n) / max(
        disc_thickness_mm * ligament_width ** 2, 1e-9
    )

    sf_bearing = allowable_bearing / max(bearing_stress, 1e-9)
    sf_pin_shear = allowable_shear / max(output_pin_shear, 1e-9)
    sf_lobe_shear = allowable_shear / max(lobe_shear, 1e-9)
    sf_ligament_bending = allowable_bending / max(ligament_bending, 1e-9)

    return StrengthReport(
        allowable_bearing_mpa=allowable_bearing,
        allowable_shear_mpa=allowable_shear,
        allowable_bending_mpa=allowable_bending,
        bearing_stress_mpa=bearing_stress,
        output_pin_shear_stress_mpa=output_pin_shear,
        lobe_shear_stress_mpa=lobe_shear,
        output_hole_ligament_bending_stress_mpa=ligament_bending,
        sf_bearing=sf_bearing,
        sf_output_pin_shear=sf_pin_shear,
        sf_lobe_shear=sf_lobe_shear,
        sf_ligament_bending=sf_ligament_bending,
    )


def is_strength_acceptable(report: StrengthReport) -> bool:
    return (
        report.sf_bearing >= 1.0
        and report.sf_output_pin_shear >= 1.0
        and report.sf_lobe_shear >= 1.0
        and report.sf_ligament_bending >= 1.0
    )


def minimum_strength_sf(report: StrengthReport) -> float:
    return min(
        report.sf_bearing,
        report.sf_output_pin_shear,
        report.sf_lobe_shear,
        report.sf_ligament_bending,
    )
