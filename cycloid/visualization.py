from __future__ import annotations

import math
from pathlib import Path

from .models import Candidate


def _svg_circle(cx: float, cy: float, r: float, stroke: str, fill: str = "none", stroke_width: float = 1.5, dash: str | None = None):
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<circle cx="{cx:.3f}" cy="{cy:.3f}" r="{r:.3f}" '
        f'stroke="{stroke}" fill="{fill}" stroke-width="{stroke_width:.3f}"{dash_attr}/>'
    )


def _svg_line(x1: float, y1: float, x2: float, y2: float, color: str, stroke_width: float = 1.0, dash: str | None = None):
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<line x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}" '
        f'stroke="{color}" stroke-width="{stroke_width:.3f}"{dash_attr}/>'
    )


def _svg_text(x: float, y: float, text: str, size: int = 14, color: str = "#1f2937"):
    safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<text x="{x:.3f}" y="{y:.3f}" fill="{color}" font-size="{size}" font-family="Segoe UI, Arial, sans-serif">{safe}</text>'


def write_candidate_svg(candidate: Candidate, path: Path) -> Path:
    ring_r = candidate.ring_pitch_radius_mm
    ring_roller_r = candidate.ring_roller_radius_mm
    output_r = candidate.output_pin_circle_radius_mm
    output_pin_r = candidate.output_roller_diameter_mm / 2.0
    output_hole_r = candidate.output_hole_diameter_mm / 2.0
    disc_r = candidate.estimated_disc_outer_diameter_mm / 2.0
    e = candidate.eccentricity_mm

    extent = max(
        ring_r + ring_roller_r,
        output_r + output_pin_r,
        e + output_r + output_hole_r,
        e + disc_r,
    )

    canvas = 1100.0
    margin = 120.0
    drawable = canvas - 2.0 * margin
    scale = drawable / max(2.0 * extent, 1e-9)

    def to_xy(x_mm: float, y_mm: float):
        return canvas / 2.0 + x_mm * scale, canvas / 2.0 - y_mm * scale

    elems: list[str] = []
    elems.append(f'<rect x="0" y="0" width="{canvas}" height="{canvas}" fill="#f8fafc"/>')

    cx0, cy0 = to_xy(0.0, 0.0)
    cxd, cyd = to_xy(e, 0.0)

    elems.append(_svg_line(cx0, cy0, cxd, cyd, color="#6b7280", stroke_width=1.2, dash="5 4"))

    elems.append(_svg_circle(cx0, cy0, ring_r * scale, stroke="#64748b", dash="6 4"))
    elems.append(_svg_circle(cxd, cyd, disc_r * scale, stroke="#0f766e", stroke_width=2.0))

    for i in range(candidate.ring_pin_count):
        theta = 2.0 * math.pi * i / candidate.ring_pin_count
        x = ring_r * math.cos(theta)
        y = ring_r * math.sin(theta)
        cx, cy = to_xy(x, y)
        elems.append(_svg_circle(cx, cy, ring_roller_r * scale, stroke="#1d4ed8", fill="#bfdbfe", stroke_width=1.1))

    for i in range(candidate.output_pin_count):
        theta = 2.0 * math.pi * i / candidate.output_pin_count

        x_pin = output_r * math.cos(theta)
        y_pin = output_r * math.sin(theta)
        cxp, cyp = to_xy(x_pin, y_pin)
        elems.append(_svg_circle(cxp, cyp, output_pin_r * scale, stroke="#b45309", fill="#fde68a", stroke_width=1.2))

        x_hole = e + output_r * math.cos(theta)
        y_hole = output_r * math.sin(theta)
        cxh, cyh = to_xy(x_hole, y_hole)
        elems.append(_svg_circle(cxh, cyh, output_hole_r * scale, stroke="#7c3aed", stroke_width=1.2, dash="4 3"))

    elems.append(_svg_circle(cx0, cy0, 2.5, stroke="#111827", fill="#111827"))
    elems.append(_svg_circle(cxd, cyd, 2.5, stroke="#0f766e", fill="#0f766e"))

    text_x = 24
    text_y = 32
    line = 22
    elems.append(_svg_text(text_x, text_y, "Cycloidal Geometry Preview", size=22, color="#111827"))
    elems.append(_svg_text(text_x, text_y + 1 * line, f"Stage ratio: {candidate.stage_ratio}:1"))
    elems.append(_svg_text(text_x, text_y + 2 * line, f"Ring pitch dia: {candidate.ring_pitch_diameter_mm:.3f} mm"))
    elems.append(_svg_text(text_x, text_y + 3 * line, f"Ring roller dia: {candidate.ring_roller_diameter_mm:.3f} mm"))
    elems.append(_svg_text(text_x, text_y + 4 * line, f"Eccentricity: {candidate.eccentricity_mm:.3f} mm"))
    elems.append(_svg_text(text_x, text_y + 5 * line, f"Output roller dia: {candidate.output_roller_diameter_mm:.3f} mm"))
    elems.append(_svg_text(text_x, text_y + 6 * line, f"Output hole dia: {candidate.output_hole_diameter_mm:.3f} mm"))
    elems.append(_svg_text(text_x, text_y + 7 * line, f"Min static SF: {candidate.minimum_strength_sf:.3f}"))
    elems.append(_svg_text(text_x, text_y + 8 * line, f"Min fatigue SF: {candidate.minimum_fatigue_sf:.3f}"))

    legend_y = canvas - 140
    elems.append(_svg_text(text_x, legend_y, "Legend:", size=15, color="#111827"))
    elems.append(_svg_text(text_x, legend_y + line, "Blue = ring rollers, Amber = output rollers, Purple dashed = output holes"))
    elems.append(_svg_text(text_x, legend_y + 2 * line, "Teal = estimated disc OD, Gray dashed = ring pitch circle"))

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{int(canvas)}" height="{int(canvas)}" '
        f'viewBox="0 0 {int(canvas)} {int(canvas)}">' + "".join(elems) + "</svg>"
    )

    path.write_text(svg, encoding="utf-8")
    return path
