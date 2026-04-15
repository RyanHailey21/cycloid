from __future__ import annotations

import math
from pathlib import Path

from .assembly_validation import validate_candidate_geometry
from .models import Candidate
from .profile import generate_envelope_profile_points


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
    # FEA-oriented shaft geometry: functional drive features without bearing-seat detail.
    shaft_core_d = max(candidate.estimated_required_shaft_diameter_mm, 8.0)
    drive_shank_d = max(0.78 * shaft_core_d, 6.0)
    shoulder_d = max(1.12 * drive_shank_d, drive_shank_d + 1.0)
    journal_clearance = 0.15
    journal_d = max(2.0, bore_diameter_mm - journal_clearance)
    web_d = max(shoulder_d, journal_d + 2.0 * abs(eccentricity_mm) + 4.0)

    shoulder_len = max(3.5, 0.12 * candidate.disc_thickness_mm)
    overhang_len = max(24.0, 0.9 * candidate.disc_thickness_mm)
    web_len = max(5.0, 0.22 * candidate.disc_thickness_mm)
    journal_len = disc_thickness_mm
    center_spacer_len = 0.0 if not dual_discs else disc_gap_mm
    center_module_len = journal_len if not dual_discs else (2.0 * journal_len + center_spacer_len)
    total_len = 2.0 * (overhang_len + shoulder_len + web_len) + center_module_len
    half_total = 0.5 * total_len

    z = -half_total

    def take(length: float):
        nonlocal z
        z0 = z
        z += length
        return z0 + 0.5 * length

    # Left to right segment centers.
    z_left_overhang = take(overhang_len)
    z_left_shoulder = take(shoulder_len)
    z_left_web = take(web_len)
    z_journal = take(center_module_len)
    z_right_web = take(web_len)
    z_right_shoulder = take(shoulder_len)
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
            diameter_mm=drive_shank_d,
            length_mm=overhang_len,
            x_offset_mm=0.0,
            z_center_mm=z_right_overhang,
        )
    )

    return shaft


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

    local_profile = generate_envelope_profile_points(
        candidate=candidate,
        phase_rad=phase_rad,
    )
    profile_pts = [(disc_center_x + x, y) for x, y in local_profile]
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


def _segments_intersect(
    a1: tuple[float, float],
    a2: tuple[float, float],
    b1: tuple[float, float],
    b2: tuple[float, float],
) -> bool:
    def orient(p, q, r) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    o1 = orient(a1, a2, b1)
    o2 = orient(a1, a2, b2)
    o3 = orient(b1, b2, a1)
    o4 = orient(b1, b2, a2)
    return (o1 * o2 < 0.0) and (o3 * o4 < 0.0)


def _check_profile_feasibility(
    *,
    candidate: Candidate,
    phase_rad: float,
    radial_clearance_mm: float = 0.02,
    check_contact: bool = False,
    min_profile_radius_mm: float = 0.05,
) -> None:
    points = generate_envelope_profile_points(
        candidate=candidate,
        phase_rad=phase_rad,
        radial_clearance_mm=radial_clearance_mm,
        theta_samples=1600,
    )
    if len(points) < 8:
        raise RuntimeError("Cycloidal profile generation returned too few points.")

    n = len(points)
    for i in range(n):
        a1 = points[i]
        a2 = points[(i + 1) % n]
        for j in range(i + 2, n):
            if j == i or (j + 1) % n == i:
                continue
            if i == 0 and j == n - 1:
                continue
            b1 = points[j]
            b2 = points[(j + 1) % n]
            if _segments_intersect(a1, a2, b1, b2):
                raise RuntimeError(
                    f"Cycloidal profile self-intersection detected (phase={phase_rad:.3f} rad)."
                )

    # Guard against degenerate tiny edges that can create bad STEP faces.
    min_seg = float("inf")
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        seg = math.hypot(x2 - x1, y2 - y1)
        if seg < min_seg:
            min_seg = seg
    if min_seg < 1e-4:
        raise RuntimeError(
            f"Cycloidal profile has degenerate edge segments (min segment {min_seg:.6g} mm)."
        )

    # Undercut/manufacturability guard: reject edges with near-cusp curvature.
    # Discrete osculating radius from triples of adjacent points.
    min_radius = float("inf")
    for i in range(n):
        p0 = points[(i - 1) % n]
        p1 = points[i]
        p2 = points[(i + 1) % n]
        a = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        b = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        c = math.hypot(p2[0] - p0[0], p2[1] - p0[1])
        if a < 1e-12 or b < 1e-12 or c < 1e-12:
            continue
        area2 = abs((p1[0] - p0[0]) * (p2[1] - p0[1]) - (p1[1] - p0[1]) * (p2[0] - p0[0]))
        if area2 < 1e-12:
            continue
        kappa = 2.0 * area2 / (a * b * c)
        if kappa > 1e-12:
            rho = 1.0 / kappa
            if rho < min_radius:
                min_radius = rho

    if min_radius < min_profile_radius_mm:
        raise RuntimeError(
            "Cycloidal profile undercut risk: "
            f"minimum local radius {min_radius:.4f} mm < required {min_profile_radius_mm:.4f} mm."
        )


def export_cycloidal_disc_step(
    candidate: Candidate,
    path: Path,
    *,
    eccentric_shaft_hole_diameter_mm: float | None = None,
    phase_rad: float = 0.0,
    validate_profile: bool = True,
    min_profile_radius_mm: float = 0.05,
) -> Path:
    try:
        import cadquery as cq  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "CadQuery import failed. Use Python 3.11 or 3.12 in a venv and install: pip install cadquery. "
            f"Original error: {type(exc).__name__}: {exc}"
        ) from exc

    if validate_profile:
        _check_profile_feasibility(
            candidate=candidate,
            phase_rad=phase_rad,
            check_contact=True,
            min_profile_radius_mm=min_profile_radius_mm,
        )

    bore_diameter = (
        eccentric_shaft_hole_diameter_mm
        if eccentric_shaft_hole_diameter_mm is not None
        else candidate.eccentric_shaft_hole_diameter_mm
    )
    disc = _disc_solid(
        cq=cq,
        candidate=candidate,
        disc_center_x=0.0,
        z_center=0.0,
        phase_rad=phase_rad,
        bore_diameter_mm=bore_diameter,
    )
    assembly = cq.Assembly(name="cycloidal_disc_only")
    assembly.add(disc, name="cycloidal_disc", color=cq.Color("teal"))
    assembly.save(str(path), exportType="STEP")
    return path


def export_candidate_step(
    candidate: Candidate,
    path: Path,
    eccentric_shaft_hole_diameter_mm: float | None = None,
    dual_discs: bool = True,
    validate_profile: bool = True,
    min_profile_radius_mm: float = 0.05,
) -> Path:
    try:
        import cadquery as cq  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "CadQuery import failed. Use Python 3.11 or 3.12 in a venv and install: pip install cadquery. "
            f"Original error: {type(exc).__name__}: {exc}"
        ) from exc

    validation = validate_candidate_geometry(candidate, dual_discs=dual_discs)
    if not validation.passed:
        raise RuntimeError(f"Assembly validation failed: {validation.message}")
    if validate_profile:
        _check_profile_feasibility(
            candidate=candidate,
            phase_rad=0.0,
            check_contact=True,
            min_profile_radius_mm=min_profile_radius_mm,
        )
        if dual_discs:
            _check_profile_feasibility(
                candidate=candidate,
                phase_rad=math.pi,
                check_contact=True,
                min_profile_radius_mm=min_profile_radius_mm,
            )

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
            # Build Disc B with same native phase/offset as Disc A, then rotate
            # the full solid by 180 deg about global Z for guaranteed pin phasing.
            disc_center_x=disc_a_x,
            z_center=z_disc_b,
            phase_rad=0.0,
            bore_diameter_mm=bore_diameter,
        )
        disc_b = disc_b.rotate((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), 180.0)
        assembly.add(disc_b, name="disc_b", color=cq.Color("seagreen"))

    # Housing with integrated ring rollers/pins.
    housing_radial_wall = max(6.0, 4.0 * ring_roller_r)
    housing_outer_r = ring_pitch_r + ring_roller_r + housing_radial_wall
    # Expose most of each ring roller into the working cavity.
    # exposed_fraction = fraction of roller diameter visible to disc side.
    exposed_fraction = 0.92
    target_inner_r = (
        (ring_pitch_r - ring_roller_r) + exposed_fraction * (2.0 * ring_roller_r)
    )
    housing_inner_r = max(
        candidate.estimated_disc_outer_diameter_mm / 2.0 + 0.8,
        target_inner_r,
    )
    if housing_inner_r >= housing_outer_r - 1.0:
        housing_inner_r = housing_outer_r - 1.0

    housing = (
        cq.Workplane("XY")
        .circle(housing_outer_r)
        .circle(housing_inner_r)
        .extrude(stack_length)
        .translate((0.0, 0.0, -half_stack))
    )
    for i in range(candidate.ring_pin_count):
        theta = 2.0 * math.pi * i / candidate.ring_pin_count
        x = ring_pitch_r * math.cos(theta)
        y = ring_pitch_r * math.sin(theta)
        roller_pin = (
            cq.Workplane("XY")
            .center(x, y)
            .circle(ring_roller_r)
            .extrude(stack_length)
            .translate((0.0, 0.0, -half_stack))
        )
        housing = housing.union(roller_pin)
    assembly.add(housing, name="housing_with_ring_pins", color=cq.Color(0.20, 0.33, 0.65))

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
    # Output pins from carrier through disc stack (drive interface).
    # Pins are unioned into the carrier so output torque is carried by one solid part.
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
        output_carrier = output_carrier.union(output_pin)

    assembly.add(output_carrier, name="output_carrier_with_pins", color=cq.Color(0.35, 0.60, 0.35))

    output_shaft = (
        cq.Workplane("XY")
        .circle(output_shaft_d / 2.0)
        .extrude(output_shaft_len)
        .translate((0.0, 0.0, output_carrier_top_z))
    )
    assembly.add(output_shaft, name="output_shaft", color=cq.Color(0.40, 0.40, 0.40))

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
