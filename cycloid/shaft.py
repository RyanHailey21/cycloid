from __future__ import annotations

import math


STANDARD_SHAFT_DIAMETERS_MM = (
    8.0,
    10.0,
    12.0,
    15.0,
    16.0,
    18.0,
    20.0,
    22.0,
    25.0,
    28.0,
    30.0,
    32.0,
    35.0,
    38.0,
    40.0,
    42.0,
    45.0,
    48.0,
    50.0,
    55.0,
    60.0,
)


def estimate_eccentric_bore_diameter_mm(eccentricity_mm: float, output_roller_diameter_mm: float) -> float:
    # Practical first-pass sizing heuristic for the disc bore that rides on eccentric bearing.
    return max(8.0, 4.0 * eccentricity_mm + 4.0, 0.35 * output_roller_diameter_mm)


def evaluate_eccentric_bore_safety(
    *,
    force_on_disc_n: float,
    bore_diameter_mm: float,
    disc_thickness_mm: float,
    allowable_bearing_mpa: float,
):
    bearing_stress = force_on_disc_n / max(bore_diameter_mm * disc_thickness_mm, 1e-9)
    sf = allowable_bearing_mpa / max(bearing_stress, 1e-9)
    return bearing_stress, sf


def required_shaft_diameter_mm_from_torque(
    *,
    torque_nmm: float,
    allowable_shear_mpa: float,
) -> float:
    # Solid round shaft torsion: tau_max = 16T/(pi*d^3)
    return ((16.0 * torque_nmm) / max(math.pi * allowable_shear_mpa, 1e-9)) ** (1.0 / 3.0)


def select_standard_shaft_diameter_mm(required_diameter_mm: float) -> float:
    for d in STANDARD_SHAFT_DIAMETERS_MM:
        if d >= required_diameter_mm:
            return d
    return required_diameter_mm


def torsional_sf_for_shaft(
    *,
    diameter_mm: float,
    torque_nmm: float,
    allowable_shear_mpa: float,
) -> float:
    applied_shear = (16.0 * torque_nmm) / max(math.pi * diameter_mm ** 3, 1e-9)
    return allowable_shear_mpa / max(applied_shear, 1e-9)


def select_standard_shaft_for_min_sf(
    *,
    required_diameter_mm: float,
    minimum_sf: float,
    torque_nmm: float,
    allowable_shear_mpa: float,
) -> float:
    start = select_standard_shaft_diameter_mm(required_diameter_mm)
    for d in STANDARD_SHAFT_DIAMETERS_MM:
        if d < start:
            continue
        sf = torsional_sf_for_shaft(
            diameter_mm=d,
            torque_nmm=torque_nmm,
            allowable_shear_mpa=allowable_shear_mpa,
        )
        if sf >= minimum_sf:
            return d
    # Fallback if list is exhausted.
    return start
