from __future__ import annotations

import math
from dataclasses import asdict
from typing import List

from .models import Candidate, SolverConfig
from .strength import (
    compute_allowables,
    evaluate_strength,
    is_strength_acceptable,
    minimum_strength_sf,
)


def ring_center_spacing(r_mm: float, n: int) -> float:
    return 2.0 * r_mm * math.sin(math.pi / n)


def output_center_spacing(ro_mm: float, count: int) -> float:
    return 2.0 * ro_mm * math.sin(math.pi / count)


def frange(start: float, stop: float, step: float):
    x = start
    while x <= stop + 1e-9:
        yield round(x, 10)
        x += step


def round_up_to_step(value: float, step: float) -> float:
    if step <= 0:
        return value
    return math.ceil(value / step) * step


def score_candidate(
    *,
    ring_pitch_radius_mm: float,
    eccentricity_ratio: float,
    disc_thickness_mm: float,
    output_spacing_margin_mm: float,
    ring_spacing_margin_mm: float,
    min_sf: float,
    bearing_stress_mpa: float,
) -> float:
    compactness_cost = 0.08 * ring_pitch_radius_mm
    ecc_pref_cost = abs(eccentricity_ratio - 0.03) * 1000.0
    thickness_reward = -0.2 * disc_thickness_mm
    margin_reward = -0.15 * output_spacing_margin_mm - 0.08 * ring_spacing_margin_mm
    strength_reward = -12.0 * min(min_sf, 3.0)
    bearing_cost = 0.2 * bearing_stress_mpa

    return (
        compactness_cost
        + ecc_pref_cost
        + thickness_reward
        + margin_reward
        + strength_reward
        + bearing_cost
    )


def required_radius_for_constraints(
    *,
    torque_nmm: float,
    loaded_output_pins: int,
    loaded_lobes: int,
    output_pin_count: int,
    ro_ratio: float,
    output_roller_fraction: float,
    eccentricity_ratio: float,
    ring_roller_ratio: float,
    stage_ring_pin_count: int,
    disc_thickness_mm: float,
    clearance_mm: float,
    allowable_bearing_mpa: float,
    allowable_shear_mpa: float,
) -> float | None:
    sin_no = math.sin(math.pi / output_pin_count)
    sin_n = math.sin(math.pi / stage_ring_pin_count)

    output_spacing_per_radius = 2.0 * ro_ratio * sin_no
    output_roller_per_radius = output_roller_fraction * output_spacing_per_radius
    ring_roller_per_radius = ring_roller_ratio * 2.0 * sin_n

    if output_spacing_per_radius <= 0 or output_roller_per_radius <= 0:
        return None

    if eccentricity_ratio >= ring_roller_per_radius:
        return None
    if eccentricity_ratio >= 0.5 * sin_n:
        return None
    if ring_roller_ratio >= 0.45:
        return None

    spacing_den = 0.90 * output_spacing_per_radius - output_roller_per_radius - 2.0 * eccentricity_ratio
    if spacing_den <= 0:
        return None

    radial_margin_coeff = (
        1.0
        - ring_roller_per_radius
        - ro_ratio
        - 3.5 * eccentricity_ratio
        - 0.5 * output_roller_per_radius
    )
    if radial_margin_coeff <= 0:
        return None

    r_from_bearing = math.sqrt(
        torque_nmm
        / max(
            loaded_output_pins
            * output_roller_per_radius
            * disc_thickness_mm
            * allowable_bearing_mpa,
            1e-9,
        )
    )

    r_from_pin_shear = (
        (4.0 * torque_nmm)
        / max(
            loaded_output_pins
            * math.pi
            * (output_roller_per_radius ** 2)
            * allowable_shear_mpa,
            1e-9,
        )
    ) ** (1.0 / 3.0)

    r_from_lobe_shear = math.sqrt(
        torque_nmm
        / max(
            2.0
            * loaded_lobes
            * disc_thickness_mm
            * eccentricity_ratio
            * allowable_shear_mpa,
            1e-9,
        )
    )

    r_from_spacing = (2.0 * clearance_mm) / spacing_den
    r_from_radial_margin = clearance_mm / radial_margin_coeff

    return max(
        r_from_bearing,
        r_from_pin_shear,
        r_from_lobe_shear,
        r_from_spacing,
        r_from_radial_margin,
    )


def generate_candidates(config: SolverConfig) -> List[Candidate]:
    n = config.stage_ratio + 1
    lobe_count = n - 1
    torque_nmm = config.target_output_torque_nm * 1000.0

    allowable_bearing, allowable_shear, _ = compute_allowables(
        config.material.yield_strength_mpa,
        config.safety_factors,
    )

    candidates: List[Candidate] = []

    for ring_roller_ratio in frange(
        config.ring_roller_radius_ratio_min,
        config.ring_roller_radius_ratio_max,
        config.ring_roller_radius_ratio_step,
    ):
        for eccentricity_ratio in frange(
            config.eccentricity_ratio_min,
            config.eccentricity_ratio_max,
            config.eccentricity_ratio_step,
        ):
            for output_pin_count in config.output_pin_counts:
                for ro_ratio in config.output_pin_circle_ratios:
                    for output_roller_fraction in config.output_roller_fraction_choices:
                        for disc_thickness_mm in frange(
                            config.disc_thickness_min_mm,
                            config.disc_thickness_max_mm,
                            config.disc_thickness_step_mm,
                        ):
                            required_radius = required_radius_for_constraints(
                                torque_nmm=torque_nmm,
                                loaded_output_pins=config.loaded_output_pins,
                                loaded_lobes=config.loaded_lobes,
                                output_pin_count=output_pin_count,
                                ro_ratio=ro_ratio,
                                output_roller_fraction=output_roller_fraction,
                                eccentricity_ratio=eccentricity_ratio,
                                ring_roller_ratio=ring_roller_ratio,
                                stage_ring_pin_count=n,
                                disc_thickness_mm=disc_thickness_mm,
                                clearance_mm=config.clearance_mm,
                                allowable_bearing_mpa=allowable_bearing,
                                allowable_shear_mpa=allowable_shear,
                            )
                            if required_radius is None:
                                continue

                            ring_pitch_radius_mm = max(
                                config.min_ring_pitch_radius_mm,
                                round_up_to_step(
                                    required_radius,
                                    config.ring_pitch_radius_step_mm,
                                ),
                            )
                            if ring_pitch_radius_mm > config.max_ring_pitch_radius_mm:
                                continue

                            ring_spacing = ring_center_spacing(ring_pitch_radius_mm, n)
                            ring_roller_radius_mm = ring_roller_ratio * ring_spacing
                            eccentricity_mm = eccentricity_ratio * ring_pitch_radius_mm

                            output_pin_circle_radius_mm = ro_ratio * ring_pitch_radius_mm
                            output_spacing = output_center_spacing(
                                output_pin_circle_radius_mm,
                                output_pin_count,
                            )
                            output_roller_diameter_mm = output_roller_fraction * output_spacing
                            output_hole_diameter_mm = (
                                output_roller_diameter_mm
                                + 2.0 * eccentricity_mm
                                + 2.0 * config.clearance_mm
                            )

                            radial_outer_limit = (
                                ring_pitch_radius_mm
                                - ring_roller_radius_mm
                                - 2.5 * eccentricity_mm
                            )
                            radial_margin = radial_outer_limit - (
                                output_pin_circle_radius_mm + output_hole_diameter_mm / 2.0
                            )

                            if output_hole_diameter_mm >= 0.90 * output_spacing:
                                continue
                            if radial_margin <= 0:
                                continue

                            total_tangential_force_n = torque_nmm / ring_pitch_radius_mm
                            force_per_lobe_n = total_tangential_force_n / config.loaded_lobes
                            force_per_output_pin_n = (
                                total_tangential_force_n / config.loaded_output_pins
                            )

                            strength = evaluate_strength(
                                force_per_output_pin_n=force_per_output_pin_n,
                                force_per_lobe_n=force_per_lobe_n,
                                output_roller_diameter_mm=output_roller_diameter_mm,
                                disc_thickness_mm=disc_thickness_mm,
                                eccentricity_mm=eccentricity_mm,
                                output_hole_diameter_mm=output_hole_diameter_mm,
                                output_pin_center_spacing_mm=output_spacing,
                                yield_strength_mpa=config.material.yield_strength_mpa,
                                safety=config.safety_factors,
                            )
                            if not is_strength_acceptable(strength):
                                continue

                            output_spacing_margin = 0.90 * output_spacing - output_hole_diameter_mm
                            ring_spacing_margin = (
                                0.90 * ring_spacing - 2.0 * ring_roller_radius_mm
                            )
                            min_sf = minimum_strength_sf(strength)

                            score = score_candidate(
                                ring_pitch_radius_mm=ring_pitch_radius_mm,
                                eccentricity_ratio=eccentricity_ratio,
                                disc_thickness_mm=disc_thickness_mm,
                                output_spacing_margin_mm=output_spacing_margin,
                                ring_spacing_margin_mm=ring_spacing_margin,
                                min_sf=min_sf,
                                bearing_stress_mpa=strength.bearing_stress_mpa,
                            )

                            estimated_disc_outer_diameter_mm = 2.0 * (
                                ring_pitch_radius_mm - ring_roller_radius_mm - eccentricity_mm
                            )
                            estimated_output_speed_rpm = (
                                config.motor_speed_rpm / config.stage_ratio
                            )

                            candidates.append(
                                Candidate(
                                    stage_ratio=config.stage_ratio,
                                    ring_pin_count=n,
                                    lobe_count=lobe_count,
                                    material_name=config.material.name,
                                    ring_pitch_radius_mm=round(ring_pitch_radius_mm, 3),
                                    ring_pitch_diameter_mm=round(
                                        2.0 * ring_pitch_radius_mm, 3
                                    ),
                                    ring_roller_radius_mm=round(ring_roller_radius_mm, 3),
                                    ring_roller_diameter_mm=round(
                                        2.0 * ring_roller_radius_mm, 3
                                    ),
                                    eccentricity_mm=round(eccentricity_mm, 3),
                                    eccentricity_ratio=round(eccentricity_ratio, 5),
                                    disc_thickness_mm=round(disc_thickness_mm, 3),
                                    estimated_disc_outer_diameter_mm=round(
                                        estimated_disc_outer_diameter_mm, 3
                                    ),
                                    output_pin_count=output_pin_count,
                                    output_pin_circle_radius_mm=round(
                                        output_pin_circle_radius_mm, 3
                                    ),
                                    output_pin_circle_diameter_mm=round(
                                        2.0 * output_pin_circle_radius_mm, 3
                                    ),
                                    output_roller_diameter_mm=round(
                                        output_roller_diameter_mm, 3
                                    ),
                                    output_hole_diameter_mm=round(output_hole_diameter_mm, 3),
                                    ring_pin_center_spacing_mm=round(ring_spacing, 3),
                                    output_pin_center_spacing_mm=round(output_spacing, 3),
                                    radial_margin_to_ring_mm=round(radial_margin, 3),
                                    total_tangential_force_N=round(total_tangential_force_n, 3),
                                    force_per_loaded_lobe_N=round(force_per_lobe_n, 3),
                                    force_per_loaded_output_pin_N=round(
                                        force_per_output_pin_n, 3
                                    ),
                                    estimated_output_speed_rpm=round(
                                        estimated_output_speed_rpm, 6
                                    ),
                                    allowable_bearing_mpa=round(
                                        strength.allowable_bearing_mpa, 3
                                    ),
                                    allowable_shear_mpa=round(strength.allowable_shear_mpa, 3),
                                    allowable_bending_mpa=round(
                                        strength.allowable_bending_mpa, 3
                                    ),
                                    bearing_stress_mpa=round(strength.bearing_stress_mpa, 3),
                                    output_pin_shear_stress_mpa=round(
                                        strength.output_pin_shear_stress_mpa, 3
                                    ),
                                    lobe_shear_stress_mpa=round(
                                        strength.lobe_shear_stress_mpa, 3
                                    ),
                                    output_hole_ligament_bending_stress_mpa=round(
                                        strength.output_hole_ligament_bending_stress_mpa,
                                        3,
                                    ),
                                    sf_bearing=round(strength.sf_bearing, 3),
                                    sf_output_pin_shear=round(
                                        strength.sf_output_pin_shear, 3
                                    ),
                                    sf_lobe_shear=round(strength.sf_lobe_shear, 3),
                                    sf_ligament_bending=round(
                                        strength.sf_ligament_bending, 3
                                    ),
                                    minimum_strength_sf=round(min_sf, 3),
                                    score=round(score, 6),
                                    notes=(
                                        "Constraint-driven prescription using closed-form"
                                        " minimum-radius sizing plus strength verification."
                                    ),
                                )
                            )

    candidates.sort(key=lambda c: c.score)
    return candidates


def candidate_rows(candidates: List[Candidate], top_n: int):
    return [asdict(candidate) for candidate in candidates[:top_n]]
