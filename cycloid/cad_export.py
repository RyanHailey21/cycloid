from __future__ import annotations

import math
from pathlib import Path

from .models import Candidate


def _build_lobed_profile_points(
    *,
    center_x: float,
    center_y: float,
    outer_radius_mm: float,
    lobe_count: int,
    ring_roller_radius_mm: float,
    eccentricity_mm: float,
):
    if lobe_count < 3:
        lobe_count = 3

    # Visual tooth depth for CAD preview; bounded to avoid self-intersections.
    tooth_depth = max(0.6 * ring_roller_radius_mm, 0.35 * eccentricity_mm)
    tooth_depth = min(tooth_depth, outer_radius_mm * 0.08)
    root_radius = max(outer_radius_mm - tooth_depth, outer_radius_mm * 0.55)

    points_per_lobe = 16
    samples = lobe_count * points_per_lobe
    points = []
    for i in range(samples):
        theta = (2.0 * math.pi * i) / samples
        lobe_phase = lobe_count * theta
        # Rounded lobe waveform from root_radius to outer_radius.
        radial = root_radius + tooth_depth * 0.5 * (1.0 + math.cos(lobe_phase))
        x = center_x + radial * math.cos(theta)
        y = center_y + radial * math.sin(theta)
        points.append((x, y))
    return points


def estimate_eccentric_shaft_hole_diameter_mm(candidate: Candidate) -> float:
    # First-pass heuristic: scale with eccentricity and keep a practical minimum.
    return max(8.0, 2.0 * candidate.eccentricity_mm + 6.0)


def export_candidate_step(
    candidate: Candidate,
    path: Path,
    eccentric_shaft_hole_diameter_mm: float | None = None,
) -> Path:
    try:
        import cadquery as cq  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "CadQuery import failed. Use Python 3.11 or 3.12 in a venv and install: pip install cadquery. "
            f"Original error: {type(exc).__name__}: {exc}"
        ) from exc

    thickness = candidate.disc_thickness_mm
    half_thickness = 0.5 * thickness

    ring_pitch_r = candidate.ring_pitch_radius_mm
    ring_roller_r = candidate.ring_roller_radius_mm

    disc_center_x = candidate.eccentricity_mm
    disc_outer_r = candidate.estimated_disc_outer_diameter_mm / 2.0

    output_circle_r = candidate.output_pin_circle_radius_mm
    output_pin_r = candidate.output_roller_diameter_mm / 2.0
    output_hole_r = candidate.output_hole_diameter_mm / 2.0
    shaft_hole_diameter = (
        eccentric_shaft_hole_diameter_mm
        if eccentric_shaft_hole_diameter_mm is not None
        else estimate_eccentric_shaft_hole_diameter_mm(candidate)
    )

    # Toothed cycloidal-style disc profile at eccentric center.
    profile_pts = _build_lobed_profile_points(
        center_x=disc_center_x,
        center_y=0.0,
        outer_radius_mm=disc_outer_r,
        lobe_count=candidate.lobe_count,
        ring_roller_radius_mm=ring_roller_r,
        eccentricity_mm=candidate.eccentricity_mm,
    )
    disc = (
        cq.Workplane("XY")
        .polyline(profile_pts)
        .close()
        .extrude(thickness)
        .translate((0.0, 0.0, -half_thickness))
    )

    # Output holes cut through disc.
    hole_pts = []
    for i in range(candidate.output_pin_count):
        theta = 2.0 * math.pi * i / candidate.output_pin_count
        hole_pts.append(
            (
                disc_center_x + output_circle_r * math.cos(theta),
                output_circle_r * math.sin(theta),
            )
        )

    disc = (
        disc.faces(">Z")
        .workplane()
        .pushPoints(hole_pts)
        .hole(2.0 * output_hole_r, depth=thickness)
    )
    # Eccentric shaft bore at cycloid disc center (eccentric center in global frame).
    disc = (
        disc.faces(">Z")
        .workplane()
        .center(disc_center_x, 0.0)
        .hole(shaft_hole_diameter, depth=thickness)
    )

    assembly = cq.Assembly(name="cycloidal_stage")
    assembly.add(disc, name="disc", color=cq.Color("teal"))

    # Ring rollers as individual cylinders.
    for i in range(candidate.ring_pin_count):
        theta = 2.0 * math.pi * i / candidate.ring_pin_count
        x = ring_pitch_r * math.cos(theta)
        y = ring_pitch_r * math.sin(theta)
        roller = (
            cq.Workplane("XY")
            .center(x, y)
            .circle(ring_roller_r)
            .extrude(thickness)
            .translate((0.0, 0.0, -half_thickness))
        )
        assembly.add(roller, name=f"ring_roller_{i}", color=cq.Color("royalblue"))

    # Output rollers as individual cylinders.
    for i in range(candidate.output_pin_count):
        theta = 2.0 * math.pi * i / candidate.output_pin_count
        x = output_circle_r * math.cos(theta)
        y = output_circle_r * math.sin(theta)
        output_roller = (
            cq.Workplane("XY")
            .center(x, y)
            .circle(output_pin_r)
            .extrude(thickness)
            .translate((0.0, 0.0, -half_thickness))
        )
        assembly.add(output_roller, name=f"output_roller_{i}", color=cq.Color("orange"))

    assembly.save(str(path), exportType="STEP")
    return path
