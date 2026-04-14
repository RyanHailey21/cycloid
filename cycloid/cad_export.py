from __future__ import annotations

import math
from pathlib import Path

from .models import Candidate


def _solid_cylinder_segment(*, cq, diameter_mm: float, length_mm: float, x_offset_mm: float, z_center_mm: float):
    return (
        cq.Workplane("XY")
        .center(x_offset_mm, 0.0)
        .circle(max(diameter_mm / 2.0, 1e-6))
        .extrude(max(length_mm, 1e-6))
        .translate((0.0, 0.0, z_center_mm - 0.5 * max(length_mm, 1e-6)))
    )


def _build_stepped_eccentric_shaft(
    *,
    cq,
    candidate: Candidate,
    stack_length_mm: float,
    bore_diameter_mm: float,
    eccentricity_mm: float,
    dual_discs: bool,
    disc_thickness_mm: float,
    disc_gap_mm: float,
):
    # Shaft sizing for a manufacturable-looking first-pass model.
    shaft_core_d = max(candidate.estimated_required_shaft_diameter_mm, 8.0)
    drive_shank_d = max(0.78 * shaft_core_d, 6.0)
    bearing_seat_d = max(0.88 * shaft_core_d, drive_shank_d + 2.0)
    shoulder_d = max(1.05 * bearing_seat_d, bearing_seat_d + 1.0)
    journal_clearance = 0.15
    journal_d = max(2.0, bore_diameter_mm - journal_clearance)
    web_d = max(shoulder_d, journal_d + 2.0 * abs(eccentricity_mm) + 4.0)

    shoulder_len = max(3.5, 0.12 * candidate.disc_thickness_mm)
    bearing_seat_len = max(12.0, 0.45 * candidate.disc_thickness_mm)
    overhang_len = max(24.0, 0.9 * candidate.disc_thickness_mm)
    web_len = max(5.0, 0.22 * candidate.disc_thickness_mm)
    journal_len = disc_thickness_mm
    center_spacer_len = 0.0 if not dual_discs else disc_gap_mm
    center_module_len = journal_len if not dual_discs else (2.0 * journal_len + center_spacer_len)
    total_len = 2.0 * (overhang_len + bearing_seat_len + shoulder_len + web_len) + center_module_len
    half_total = 0.5 * total_len

    z = -half_total

    def take(length: float):
        nonlocal z
        z0 = z
        z += length
        return z0 + 0.5 * length

    # Left to right segment centers.
    z_left_overhang = take(overhang_len)
    z_left_bearing = take(bearing_seat_len)
    z_left_shoulder = take(shoulder_len)
    z_left_web = take(web_len)
    z_journal = take(center_module_len)
    z_right_web = take(web_len)
    z_right_shoulder = take(shoulder_len)
    z_right_bearing = take(bearing_seat_len)
    z_right_overhang = take(overhang_len)

    shaft = _solid_cylinder_segment(
        cq=cq,
        diameter_mm=drive_shank_d,
        length_mm=overhang_len,
        x_offset_mm=0.0,
        z_center_mm=z_left_overhang,
    )
    shaft = shaft.union(
        _solid_cylinder_segment(
            cq=cq,
            diameter_mm=bearing_seat_d,
            length_mm=bearing_seat_len,
            x_offset_mm=0.0,
            z_center_mm=z_left_bearing,
        )
    )
    shaft = shaft.union(
        _solid_cylinder_segment(
            cq=cq,
            diameter_mm=shoulder_d,
            length_mm=shoulder_len,
            x_offset_mm=0.0,
            z_center_mm=z_left_shoulder,
        )
    )
    shaft = shaft.union(
        _solid_cylinder_segment(
            cq=cq,
            diameter_mm=web_d,
            length_mm=web_len,
            x_offset_mm=0.0,
            z_center_mm=z_left_web,
        )
    )
    # Eccentric journal section(s). For dual-disc: two separate eccentric journals
    # with opposite offset directions connected by a concentric spacer.
    if dual_discs:
        z_journal_a = z_journal - 0.5 * (center_spacer_len + journal_len)
        z_journal_b = z_journal + 0.5 * (center_spacer_len + journal_len)
        shaft = shaft.union(
            _solid_cylinder_segment(
                cq=cq,
                diameter_mm=journal_d,
                length_mm=journal_len,
                x_offset_mm=+eccentricity_mm,
                z_center_mm=z_journal_a,
            )
        )
        shaft = shaft.union(
            _solid_cylinder_segment(
                cq=cq,
                diameter_mm=web_d,
                length_mm=center_spacer_len,
                x_offset_mm=0.0,
                z_center_mm=z_journal,
            )
        )
        shaft = shaft.union(
            _solid_cylinder_segment(
                cq=cq,
                diameter_mm=journal_d,
                length_mm=journal_len,
                x_offset_mm=-eccentricity_mm,
                z_center_mm=z_journal_b,
            )
        )
    else:
        shaft = shaft.union(
            _solid_cylinder_segment(
                cq=cq,
                diameter_mm=journal_d,
                length_mm=journal_len,
                x_offset_mm=eccentricity_mm,
                z_center_mm=z_journal,
            )
        )
    shaft = shaft.union(
        _solid_cylinder_segment(
            cq=cq,
            diameter_mm=web_d,
            length_mm=web_len,
            x_offset_mm=0.0,
            z_center_mm=z_right_web,
        )
    )
    shaft = shaft.union(
        _solid_cylinder_segment(
            cq=cq,
            diameter_mm=shoulder_d,
            length_mm=shoulder_len,
            x_offset_mm=0.0,
            z_center_mm=z_right_shoulder,
        )
    )
    shaft = shaft.union(
        _solid_cylinder_segment(
            cq=cq,
            diameter_mm=bearing_seat_d,
            length_mm=bearing_seat_len,
            x_offset_mm=0.0,
            z_center_mm=z_right_bearing,
        )
    )
    shaft = shaft.union(
        _solid_cylinder_segment(
            cq=cq,
            diameter_mm=drive_shank_d,
            length_mm=overhang_len,
            x_offset_mm=0.0,
            z_center_mm=z_right_overhang,
        )
    )

    return shaft


def _build_lobed_profile_points(
    *,
    center_x: float,
    center_y: float,
    outer_radius_mm: float,
    lobe_count: int,
    ring_roller_radius_mm: float,
    eccentricity_mm: float,
    phase_rad: float = 0.0,
):
    if lobe_count < 3:
        lobe_count = 3

    tooth_depth = max(0.6 * ring_roller_radius_mm, 0.35 * eccentricity_mm)
    tooth_depth = min(tooth_depth, outer_radius_mm * 0.08)
    root_radius = max(outer_radius_mm - tooth_depth, outer_radius_mm * 0.55)

    points_per_lobe = 18
    samples = lobe_count * points_per_lobe
    points = []
    for i in range(samples):
        theta = (2.0 * math.pi * i) / samples
        lobe_phase = lobe_count * theta + phase_rad
        radial = root_radius + tooth_depth * 0.5 * (1.0 + math.cos(lobe_phase))
        x = center_x + radial * math.cos(theta)
        y = center_y + radial * math.sin(theta)
        points.append((x, y))
    return points


def _disc_solid(
    *,
    cq,
    candidate: Candidate,
    disc_center_x: float,
    z_center: float,
    phase_rad: float,
    bore_diameter_mm: float,
):
    thickness = candidate.disc_thickness_mm
    half_t = 0.5 * thickness

    profile_pts = _build_lobed_profile_points(
        center_x=disc_center_x,
        center_y=0.0,
        outer_radius_mm=candidate.estimated_disc_outer_diameter_mm / 2.0,
        lobe_count=candidate.lobe_count,
        ring_roller_radius_mm=candidate.ring_roller_radius_mm,
        eccentricity_mm=candidate.eccentricity_mm,
        phase_rad=phase_rad,
    )
    disc = (
        cq.Workplane("XY")
        .polyline(profile_pts)
        .close()
        .extrude(thickness)
        .translate((0.0, 0.0, z_center - half_t))
    )

    hole_pts = []
    for i in range(candidate.output_pin_count):
        theta = 2.0 * math.pi * i / candidate.output_pin_count
        hole_pts.append(
            (
                disc_center_x + candidate.output_pin_circle_radius_mm * math.cos(theta),
                candidate.output_pin_circle_radius_mm * math.sin(theta),
            )
        )

    disc = (
        disc.faces(">Z")
        .workplane()
        .pushPoints(hole_pts)
        .hole(candidate.output_hole_diameter_mm, depth=thickness)
    )

    disc = (
        disc.faces(">Z")
        .workplane()
        .center(disc_center_x, 0.0)
        .hole(bore_diameter_mm, depth=thickness)
    )

    return disc


def export_candidate_step(
    candidate: Candidate,
    path: Path,
    eccentric_shaft_hole_diameter_mm: float | None = None,
    dual_discs: bool = True,
) -> Path:
    try:
        import cadquery as cq  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "CadQuery import failed. Use Python 3.11 or 3.12 in a venv and install: pip install cadquery. "
            f"Original error: {type(exc).__name__}: {exc}"
        ) from exc

    thickness = candidate.disc_thickness_mm
    disc_gap = max(6.0, 0.2 * thickness)
    stack_length = (2.0 * thickness + disc_gap) if dual_discs else thickness
    half_stack = 0.5 * stack_length

    ring_pitch_r = candidate.ring_pitch_radius_mm
    ring_roller_r = candidate.ring_roller_radius_mm
    output_circle_r = candidate.output_pin_circle_radius_mm
    output_pin_r = candidate.output_roller_diameter_mm / 2.0

    eccentricity = candidate.eccentricity_mm
    bore_diameter = (
        eccentric_shaft_hole_diameter_mm
        if eccentric_shaft_hole_diameter_mm is not None
        else candidate.eccentric_shaft_hole_diameter_mm
    )

    z_disc_a = -0.5 * (thickness + disc_gap) if dual_discs else 0.0
    z_disc_b = 0.5 * (thickness + disc_gap)

    disc_a_x = eccentricity
    disc_b_x = -eccentricity if dual_discs else eccentricity

    disc_a = _disc_solid(
        cq=cq,
        candidate=candidate,
        disc_center_x=disc_a_x,
        z_center=z_disc_a,
        phase_rad=0.0,
        bore_diameter_mm=bore_diameter,
    )
    assembly = cq.Assembly(name="cycloidal_stage_dual")
    assembly.add(disc_a, name="disc_a", color=cq.Color("teal"))
    if dual_discs:
        disc_b = _disc_solid(
            cq=cq,
            candidate=candidate,
            disc_center_x=disc_b_x,
            z_center=z_disc_b,
            phase_rad=math.pi,
            bore_diameter_mm=bore_diameter,
        )
        assembly.add(disc_b, name="disc_b", color=cq.Color("seagreen"))

    # Ring rollers span both discs.
    for i in range(candidate.ring_pin_count):
        theta = 2.0 * math.pi * i / candidate.ring_pin_count
        x = ring_pitch_r * math.cos(theta)
        y = ring_pitch_r * math.sin(theta)
        roller = (
            cq.Workplane("XY")
            .center(x, y)
            .circle(ring_roller_r)
            .extrude(stack_length)
            .translate((0.0, 0.0, -half_stack))
        )
        assembly.add(roller, name=f"ring_roller_{i}", color=cq.Color("royalblue"))

    # Build output carrier and output shaft (typical cycloidal output path).
    output_carrier_gap = max(2.0, 0.08 * thickness)
    output_carrier_thickness = max(10.0, 0.55 * thickness)
    output_carrier_radius = max(
        output_circle_r + output_pin_r + 4.0,
        0.22 * candidate.ring_pitch_diameter_mm,
    )
    output_carrier_bottom_z = half_stack + output_carrier_gap
    output_carrier_center_z = output_carrier_bottom_z + 0.5 * output_carrier_thickness
    output_carrier_top_z = output_carrier_bottom_z + output_carrier_thickness

    # Use solver-selected standard output shaft size.
    output_shaft_d = max(10.0, candidate.selected_output_shaft_diameter_mm)
    output_shaft_len = max(32.0, 1.4 * thickness)

    output_carrier = (
        cq.Workplane("XY")
        .circle(output_carrier_radius)
        .extrude(output_carrier_thickness)
        .translate((0.0, 0.0, output_carrier_center_z - 0.5 * output_carrier_thickness))
    )
    output_carrier = (
        output_carrier.faces(">Z")
        .workplane()
        .center(0.0, 0.0)
        .hole(output_shaft_d)
    )
    assembly.add(output_carrier, name="output_carrier", color=cq.Color(0.35, 0.60, 0.35))

    output_shaft = (
        cq.Workplane("XY")
        .circle(output_shaft_d / 2.0)
        .extrude(output_shaft_len)
        .translate((0.0, 0.0, output_carrier_top_z))
    )
    assembly.add(output_shaft, name="output_shaft", color=cq.Color(0.40, 0.40, 0.40))

    # Output pins from carrier through disc stack (drive interface).
    output_pin_bottom_z = -half_stack
    output_pin_top_z = output_carrier_top_z
    output_pin_len = output_pin_top_z - output_pin_bottom_z
    output_pin_center_z = 0.5 * (output_pin_top_z + output_pin_bottom_z)
    for i in range(candidate.output_pin_count):
        theta = 2.0 * math.pi * i / candidate.output_pin_count
        x = output_circle_r * math.cos(theta)
        y = output_circle_r * math.sin(theta)
        output_pin = (
            cq.Workplane("XY")
            .center(x, y)
            .circle(output_pin_r)
            .extrude(output_pin_len)
            .translate((0.0, 0.0, output_pin_center_z - 0.5 * output_pin_len))
        )
        assembly.add(output_pin, name=f"output_pin_{i}", color=cq.Color("orange"))

    # Eccentric input shaft with stepped seats/shoulders, crank webs, and offset journal.
    stepped_shaft = _build_stepped_eccentric_shaft(
        cq=cq,
        candidate=candidate,
        stack_length_mm=stack_length,
        bore_diameter_mm=bore_diameter,
        eccentricity_mm=eccentricity,
        dual_discs=dual_discs,
        disc_thickness_mm=thickness,
        disc_gap_mm=disc_gap,
    )
    assembly.add(stepped_shaft, name="input_shaft", color=cq.Color(0.50, 0.50, 0.50))

    assembly.save(str(path), exportType="STEP")
    return path
