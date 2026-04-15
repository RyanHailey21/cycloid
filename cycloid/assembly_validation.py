from __future__ import annotations

from dataclasses import dataclass

from .models import Candidate


@dataclass(frozen=True)
class AssemblyValidation:
    passed: bool
    message: str


def validate_candidate_geometry(candidate: Candidate, *, dual_discs: bool) -> AssemblyValidation:
    issues: list[str] = []

    if candidate.radial_margin_to_ring_mm <= 0.0:
        issues.append("radial margin to ring is non-positive")

    if candidate.output_hole_diameter_mm <= candidate.output_roller_diameter_mm:
        issues.append("output hole diameter must exceed output pin/roller diameter")

    if candidate.ring_pin_center_spacing_mm <= candidate.ring_roller_diameter_mm:
        issues.append("ring rollers overlap (center spacing <= diameter)")

    if candidate.output_pin_center_spacing_mm <= candidate.output_roller_diameter_mm:
        issues.append("output pins overlap (center spacing <= diameter)")

    if candidate.eccentric_shaft_hole_diameter_mm <= 0.0:
        issues.append("eccentric bore diameter must be positive")

    if candidate.sf_eccentric_bore < 1.0:
        issues.append("eccentric bore bearing SF < 1.0")

    if candidate.output_shaft_torsional_sf < 1.0:
        issues.append("output shaft torsional SF < 1.0")

    if dual_discs and candidate.eccentricity_mm <= 0.0:
        issues.append("dual-disc assembly requires non-zero eccentricity")

    if issues:
        return AssemblyValidation(False, "; ".join(issues))
    return AssemblyValidation(True, "assembly geometry validation passed")
