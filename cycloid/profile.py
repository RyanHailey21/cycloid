from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

from .models import Candidate


@dataclass(frozen=True)
class ProfileValidation:
    passed: bool
    min_gap_mm: float
    max_gap_mm: float
    contact_fraction: float
    message: str


def _pin_centers_in_disc_frame(
    *,
    candidate: Candidate,
    alpha: float,
    phase_rad: float,
) -> List[Tuple[float, float]]:
    n = candidate.ring_pin_count
    rp = candidate.ring_pitch_radius_mm
    e = candidate.eccentricity_mm
    z = max(candidate.stage_ratio, 1)

    beta = -alpha / z + phase_rad
    cos_mbeta = math.cos(-beta)
    sin_mbeta = math.sin(-beta)

    cxw = e * math.cos(alpha)
    cyw = e * math.sin(alpha)

    centers: List[Tuple[float, float]] = []
    for i in range(n):
        phi = 2.0 * math.pi * i / n
        px = rp * math.cos(phi) - cxw
        py = rp * math.sin(phi) - cyw
        dx = cos_mbeta * px - sin_mbeta * py
        dy = sin_mbeta * px + cos_mbeta * py
        centers.append((dx, dy))
    return centers


def _fmt_num(x: float) -> str:
    return format(float(x), ".12g")


def make_sw_equations(R_p: float, e: float, r: float, N: int) -> Tuple[str, str]:
    n_int = int(N)
    n_minus = 1 - n_int
    r_p_over_e_n = R_p / (e * n_int)

    rp = _fmt_num(R_p)
    ee = _fmt_num(e)
    rr = _fmt_num(r)
    nn = str(n_int)
    n_minus_s = _fmt_num(n_minus)
    r_over_e_n_s = _fmt_num(r_p_over_e_n)

    x_expr = (
        f"({rp}*cos(t)) - "
        f"({rr}*cos(t+atn(sin({n_minus_s}*t)/({r_over_e_n_s}-cos({n_minus_s}*t))))) - "
        f"({ee}*cos({nn}*t))"
    )
    y_expr = (
        f"(-{rp}*sin(t)) + "
        f"({rr}*sin(t+atn(sin({n_minus_s}*t)/({r_over_e_n_s}-cos({n_minus_s}*t))))) + "
        f"({ee}*sin({nn}*t))"
    )
    return x_expr, y_expr


def validate_inputs(R_p: float, e: float, r: float, N: int) -> Tuple[bool, List[str]]:
    msgs: List[str] = []
    ok = True
    if not (isinstance(N, int) and N >= 2):
        ok = False
        msgs.append("Number of pins must be an integer >= 2.")
    if R_p <= 0.0 or e <= 0.0 or r <= 0.0:
        ok = False
        msgs.append("All geometry parameters must be positive.")
    if e * N == 0:
        ok = False
        msgs.append("Eccentricity * Pin Count must be non-zero.")
    else:
        r_p_over_e_n = R_p / (e * N)
        if -1.0 <= r_p_over_e_n <= 1.0:
            msgs.append(
                f"Warning: R_p/(e*N) = {r_p_over_e_n:.6g} in [-1, 1]. "
                "Profile has genuine geometric cusps (lobe tips). "
                "The Python sampler uses atan2 so the profile is still correct, "
                "but the SolidWorks atn() formula will produce incorrect geometry "
                "at the denominator sign-change points."
            )
    return ok, msgs


def sample_curve(
    R_p: float,
    e: float,
    r: float,
    N: int,
    t1: float = 0.0,
    t2: float = 2.0 * math.pi,
    samples: int = 1000,
) -> Tuple[List[float], List[float], List[float], dict]:
    n_int = int(N)
    n_minus = 1 - n_int
    r_p_over_e_n = R_p / (e * n_int)
    eps = 1e-9

    if samples < 2:
        samples = 2
    dt = (t2 - t1) / (samples - 1)
    t = [t1 + i * dt for i in range(samples)]

    x_vals: List[float] = []
    y_vals: List[float] = []
    has_singularity = False
    for tt in t:
        sin_term = math.sin(n_minus * tt)
        denom = r_p_over_e_n - math.cos(n_minus * tt)
        if abs(denom) <= eps:
            # Near-zero denominator marks a cusp location (occurs when R_p/(e*N) <= 1).
            # atan2 handles this correctly without division; flag for diagnostics.
            has_singularity = True
        # Use atan2 so the correct quadrant is preserved when denom is negative.
        # Plain atan(sin/denom) flips the sign of phi whenever denom < 0, which
        # happens throughout the sweep when R_p/(e*N) < 1, corrupting the profile.
        phi = math.atan2(sin_term, denom)
        x_vals.append(
            R_p * math.cos(tt) - r * math.cos(tt + phi) - e * math.cos(n_int * tt)
        )
        y_vals.append(
            -R_p * math.sin(tt) + r * math.sin(tt + phi) + e * math.sin(n_int * tt)
        )

    diagnostics = {
        "has_singularity": has_singularity,
        "R_p_over_eN": r_p_over_e_n,
        "R_p_over_eN_in_unit_interval": (-1.0 <= r_p_over_e_n <= 1.0),
    }
    return x_vals, y_vals, t, diagnostics


def generate_envelope_profile_points(
    *,
    candidate: Candidate,
    phase_rad: float = 0.0,
    radial_clearance_mm: float = 0.02,
    alpha_samples: int = 0,
    theta_samples: int = 4000,
) -> List[Tuple[float, float]]:
    # Standard cycloidal-drive envelope using the closed-form atan2(sin(), denom)
    # parameterization.  atan2 is required when R_p/(e*N) < 1 (denominator goes
    # negative), which is common for high-ratio stages.
    n = candidate.ring_pin_count
    r_pitch = candidate.ring_pitch_radius_mm
    r_pin = candidate.ring_roller_radius_mm + radial_clearance_mm
    e = candidate.eccentricity_mm

    ok, msgs = validate_inputs(r_pitch, e, r_pin, n)
    if not ok:
        raise RuntimeError(f"Invalid cycloidal profile inputs: {'; '.join(msgs)}")
    x_vals, y_vals, _, _ = sample_curve(
        r_pitch,
        e,
        r_pin,
        n,
        t1=phase_rad,
        t2=phase_rad + 2.0 * math.pi,
        samples=theta_samples,
    )
    points = list(zip(x_vals, y_vals))
    if len(points) >= 2:
        x0, y0 = points[0]
        x1, y1 = points[-1]
        if math.hypot(x1 - x0, y1 - y0) <= 1e-9:
            points = points[:-1]

    if len(points) < 32:
        raise RuntimeError("Failed to generate exact cycloidal profile")

    return points


def minimum_local_profile_radius_mm(
    *,
    candidate: Candidate,
    phase_rad: float = 0.0,
    radial_clearance_mm: float = 0.02,
    theta_samples: int = 1200,
) -> float:
    points = generate_envelope_profile_points(
        candidate=candidate,
        phase_rad=phase_rad,
        radial_clearance_mm=radial_clearance_mm,
        theta_samples=theta_samples,
    )
    n = len(points)
    if n < 3:
        return float("inf")

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
    return min_radius


def validate_profile_contact(
    *,
    candidate: Candidate,
    profile_points: List[Tuple[float, float]],
    phase_rad: float = 0.0,
    radial_clearance_mm: float = 0.02,
    alpha_samples: int = 120,
) -> ProfileValidation:
    pin_r = candidate.ring_roller_radius_mm + radial_clearance_mm
    min_gap = float("inf")
    max_gap = float("-inf")
    sample_count = 0
    contact_count = 0

    reduced_points = profile_points[:: max(1, len(profile_points) // 600)]

    for j in range(alpha_samples):
        alpha = 2.0 * math.pi * j / alpha_samples
        centers = _pin_centers_in_disc_frame(candidate=candidate, alpha=alpha, phase_rad=phase_rad)
        for px, py in reduced_points:
            d_min = min(math.hypot(px - cx, py - cy) for cx, cy in centers)
            gap = d_min - pin_r
            sample_count += 1
            if gap <= 0.10:
                contact_count += 1
            if gap < min_gap:
                min_gap = gap
            if gap > max_gap:
                max_gap = gap

    contact_fraction = (contact_count / sample_count) if sample_count > 0 else 0.0
    passed = min_gap >= -0.08 and contact_fraction >= 0.01
    message = (
        "profile contact validation passed"
        if passed
        else (
            "profile validation failed "
            f"(min_gap={min_gap:.4f} mm, max_gap={max_gap:.4f} mm, "
            f"contact_fraction={contact_fraction:.3f})"
        )
    )
    return ProfileValidation(
        passed=passed,
        min_gap_mm=min_gap,
        max_gap_mm=max_gap,
        contact_fraction=contact_fraction,
        message=message,
    )
