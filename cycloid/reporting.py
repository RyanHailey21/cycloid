from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

from .models import Candidate
from .profile import generate_envelope_profile_points


@dataclass(frozen=True)
class ContactPinStats:
    contact_band_mm: float
    angle_samples: int
    profile_samples: int
    min_contact_pins: int
    avg_contact_pins: float
    max_contact_pins: int


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


def _point_to_segment_distance(
    px: float,
    py: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
) -> float:
    vx = bx - ax
    vy = by - ay
    wx = px - ax
    wy = py - ay
    c1 = vx * wx + vy * wy
    if c1 <= 0.0:
        return math.hypot(px - ax, py - ay)
    c2 = vx * vx + vy * vy
    if c2 <= c1:
        return math.hypot(px - bx, py - by)
    t = c1 / c2
    qx = ax + t * vx
    qy = ay + t * vy
    return math.hypot(px - qx, py - qy)


def _min_distance_to_polyline(px: float, py: float, poly: List[Tuple[float, float]]) -> float:
    n = len(poly)
    dmin = float("inf")
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        d = _point_to_segment_distance(px, py, ax, ay, bx, by)
        if d < dmin:
            dmin = d
    return dmin


def estimate_contact_pin_stats(
    *,
    candidate: Candidate,
    disc_pin_clearance_mm: float,
    contact_band_mm: float = 0.02,
    angle_samples: int = 180,
    profile_samples: int = 4000,
    phase_rad: float = 0.0,
) -> ContactPinStats:
    profile = generate_envelope_profile_points(
        candidate=candidate,
        phase_rad=phase_rad,
        radial_clearance_mm=disc_pin_clearance_mm,
        theta_samples=max(800, profile_samples),
    )
    pin_r = candidate.ring_roller_radius_mm

    contact_counts: List[int] = []
    for k in range(max(12, angle_samples)):
        alpha = 2.0 * math.pi * k / max(12, angle_samples)
        pin_centers = _pin_centers_in_disc_frame(
            candidate=candidate,
            alpha=alpha,
            phase_rad=phase_rad,
        )
        c = 0
        for cx, cy in pin_centers:
            d = _min_distance_to_polyline(cx, cy, profile)
            if abs(d - pin_r) <= contact_band_mm:
                c += 1
        contact_counts.append(c)

    return ContactPinStats(
        contact_band_mm=contact_band_mm,
        angle_samples=max(12, angle_samples),
        profile_samples=max(800, profile_samples),
        min_contact_pins=min(contact_counts),
        avg_contact_pins=sum(contact_counts) / len(contact_counts),
        max_contact_pins=max(contact_counts),
    )


def pin_contact_distances_for_angle(
    *,
    candidate: Candidate,
    disc_pin_clearance_mm: float,
    alpha_rad: float = 0.0,
    phase_rad: float = 0.0,
    profile_samples: int = 4000,
) -> List[float]:
    profile = generate_envelope_profile_points(
        candidate=candidate,
        phase_rad=phase_rad,
        radial_clearance_mm=disc_pin_clearance_mm,
        theta_samples=max(800, profile_samples),
    )
    pin_r = candidate.ring_roller_radius_mm
    pin_centers = _pin_centers_in_disc_frame(
        candidate=candidate,
        alpha=alpha_rad,
        phase_rad=phase_rad,
    )
    return [_min_distance_to_polyline(cx, cy, profile) - pin_r for cx, cy in pin_centers]


def contact_pin_indices_for_angle(
    *,
    candidate: Candidate,
    disc_pin_clearance_mm: float,
    contact_band_mm: float = 0.02,
    alpha_rad: float = 0.0,
    phase_rad: float = 0.0,
    profile_samples: int = 4000,
) -> List[int]:
    gaps = pin_contact_distances_for_angle(
        candidate=candidate,
        disc_pin_clearance_mm=disc_pin_clearance_mm,
        alpha_rad=alpha_rad,
        phase_rad=phase_rad,
        profile_samples=profile_samples,
    )
    return [i for i, g in enumerate(gaps) if abs(g) <= contact_band_mm]
