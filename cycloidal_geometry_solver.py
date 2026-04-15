"""
Cycloidal stage geometry solver
===============================

Generates candidate single-stage cycloidal drive geometries and performs
material-based static and Goodman fatigue screening checks.

Example
-------
python cycloidal_geometry_solver.py --overall-ratio 658503 --max-stages 3 --target-torque 3000 --material 4140_qt
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from cycloid import (
    ContactPinStats,
    FatigueConfig,
    SafetyFactors,
    SolverConfig,
    available_material_keys,
    candidate_rows,
    choose_representative_stage,
    export_candidate_step,
    export_cycloidal_disc_step,
    export_disc_pins_shaft_step,
    estimate_contact_pin_stats,
    generate_candidates,
    get_material,
    validate_candidate_geometry,
    write_ansys_static_template,
    write_candidate_svg,
)


def write_csv(path: Path, rows) -> Path:
    if not rows:
        return path
    try:
        with path.open("w", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return path
    except PermissionError:
        stamped = datetime.now().strftime("%Y%m%d_%H%M%S")
        fallback = path.with_name(f"{path.stem}_{stamped}{path.suffix}")
        with fallback.open("w", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return fallback


def write_report(
    path: Path,
    *,
    args: argparse.Namespace,
    best: dict,
    contact: ContactPinStats,
) -> Path:
    lines = [
        "Cycloidal Geometry Report",
        "========================",
        "",
        "Run Settings",
        f"- overall_ratio: {args.overall_ratio}",
        f"- max_stages: {args.max_stages}",
        f"- top_n: {args.top_n}",
        f"- material: {args.material}",
        f"- min_profile_radius_mm: {args.min_profile_radius_mm}",
        f"- disc_pin_clearance_mm: {args.disc_pin_clearance_mm}",
        f"- profile_points: {args.profile_points}",
        "",
        "Estimated Ring-Pin Contact (disc A)",
        f"- contact_band_mm: {contact.contact_band_mm}",
        f"- angle_samples: {contact.angle_samples}",
        f"- profile_samples: {contact.profile_samples}",
        f"- min_contact_pins: {contact.min_contact_pins}",
        f"- avg_contact_pins: {contact.avg_contact_pins:.3f}",
        f"- max_contact_pins: {contact.max_contact_pins}",
        "",
        "Best Candidate Geometry + Strength/Fatigue",
    ]
    for k, v in best.items():
        lines.append(f"- {k}: {v}")

    try:
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
    except PermissionError:
        stamped = datetime.now().strftime("%Y%m%d_%H%M%S")
        fallback = path.with_name(f"{path.stem}_{stamped}{path.suffix}")
        fallback.write_text("\n".join(lines), encoding="utf-8")
        return fallback


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cycloidal stage geometry solver")
    parser.add_argument("--overall-ratio", type=int, default=658503)
    parser.add_argument("--stage-ratio", type=int, default=None)
    parser.add_argument("--max-stages", type=int, default=3)
    parser.add_argument("--min-stage-ratio", type=int, default=6)
    parser.add_argument("--max-stage-ratio", type=int, default=119)

    parser.add_argument("--motor-speed-rpm", type=float, default=1800.0)
    parser.add_argument("--target-torque", type=float, default=3000.0)

    parser.add_argument("--material", type=str, default="4140_qt", choices=available_material_keys())
    parser.add_argument("--sf-bearing", type=float, default=1.8)
    parser.add_argument("--sf-shear", type=float, default=1.8)
    parser.add_argument("--sf-bending", type=float, default=2.0)

    parser.add_argument("--disable-fatigue", action="store_true", default=False)
    parser.add_argument("--fatigue-min-sf", type=float, default=1.2)
    parser.add_argument("--torque-min-ratio", type=float, default=0.1)
    parser.add_argument("--dynamic-amplification", type=float, default=1.25)
    parser.add_argument("--surface-factor", type=float, default=0.85)
    parser.add_argument("--size-factor", type=float, default=0.90)
    parser.add_argument("--reliability-factor", type=float, default=0.868)
    parser.add_argument("--load-factor", type=float, default=1.0)
    parser.add_argument("--temperature-factor", type=float, default=1.0)
    parser.add_argument("--misc-factor", type=float, default=1.0)

    parser.add_argument("--top-n", type=int, default=25)
    parser.add_argument("--out-csv", type=str, default="cycloidal_geometry_candidates.csv")
    parser.add_argument("--out-report", type=str, default="cycloidal_geometry_report.txt")
    parser.add_argument("--out-ansys-model", type=str, default=None)
    parser.add_argument("--out-svg", type=str, default="cycloidal_geometry_preview.svg")
    parser.add_argument("--no-svg", action="store_true", default=False)
    parser.add_argument("--out-step", type=str, default=None)
    parser.add_argument("--out-step-disc", type=str, default=None)
    parser.add_argument("--out-step-assembly", type=str, default=None)
    parser.add_argument("--out-step-disc-pins-shaft", type=str, default=None)
    parser.add_argument("--ecc-shaft-hole-dia-mm", type=float, default=None)
    parser.add_argument("--min-bore-sf", type=float, default=1.2)
    parser.add_argument("--min-output-shaft-sf", type=float, default=1.2)
    parser.add_argument("--disable-assembly-validation", action="store_true", default=False)
    parser.add_argument("--single-disc", action="store_true", default=False)
    parser.add_argument(
        "--min-profile-radius-mm",
        type=float,
        default=0.05,
        help="Minimum allowed local curvature radius on cycloidal disc edge (undercut guard).",
    )
    parser.add_argument(
        "--disc-pin-clearance-mm",
        type=float,
        default=0.05,
        help="Radial running clearance between cycloidal disc profile and housing ring pins (for export geometry).",
    )
    parser.add_argument(
        "--profile-points",
        type=int,
        default=12000,
        help="Number of sampled points used to build exported cycloidal disc edge.",
    )
    parser.add_argument(
        "--contact-band-mm",
        type=float,
        default=0.02,
        help="Distance band around ring-pin radius used for contact-pin counting.",
    )
    parser.add_argument(
        "--contact-angle-samples",
        type=int,
        default=180,
        help="Number of input-angle samples for contact-pin counting.",
    )
    parser.add_argument(
        "--contact-profile-samples",
        type=int,
        default=4000,
        help="Profile samples used internally for contact-pin counting.",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    ratio_selection = choose_representative_stage(
        overall_ratio=args.overall_ratio,
        stage_ratio=args.stage_ratio,
        max_stages=args.max_stages,
        min_stage_ratio=args.min_stage_ratio,
        max_stage_ratio=args.max_stage_ratio,
    )

    material = get_material(args.material)
    safety_factors = SafetyFactors(
        bearing=args.sf_bearing,
        shear=args.sf_shear,
        bending=args.sf_bending,
    )
    fatigue_config = FatigueConfig(
        enabled=not args.disable_fatigue,
        minimum_fatigue_sf=args.fatigue_min_sf,
        torque_min_ratio=args.torque_min_ratio,
        dynamic_amplification=args.dynamic_amplification,
        surface_factor=args.surface_factor,
        size_factor=args.size_factor,
        reliability_factor=args.reliability_factor,
        load_factor=args.load_factor,
        temperature_factor=args.temperature_factor,
        miscellaneous_factor=args.misc_factor,
    )

    config = SolverConfig(
        stage_ratio=ratio_selection.representative_stage_ratio,
        motor_speed_rpm=args.motor_speed_rpm,
        target_output_torque_nm=args.target_torque,
        material=material,
        safety_factors=safety_factors,
        fatigue=fatigue_config,
        dual_disc_count=(1 if args.single_disc else 2),
        eccentric_bore_diameter_mm=args.ecc_shaft_hole_dia_mm,
        min_eccentric_bore_sf=args.min_bore_sf,
        min_output_shaft_sf=args.min_output_shaft_sf,
        min_profile_radius_mm=args.min_profile_radius_mm,
    )

    candidates = generate_candidates(config)

    out_csv = Path(args.out_csv)
    rows = candidate_rows(candidates, args.top_n)
    written_csv = write_csv(out_csv, rows)

    print(f"Overall ratio target: {args.overall_ratio}:1")
    if ratio_selection.source_combo is not None:
        print(f"Representative stage chosen from decomposition: {ratio_selection.source_combo}")
    print(f"Representative stage ratio: {ratio_selection.representative_stage_ratio}:1")
    print(f"Ring pin count N: {ratio_selection.representative_stage_ratio + 1}")
    print(f"Lobe count: {ratio_selection.representative_stage_ratio}")
    print(
        f"Material: {material.name} "
        f"(yield={material.yield_strength_mpa} MPa, "
        f"ultimate={material.ultimate_strength_mpa} MPa, "
        f"endurance={material.endurance_limit_mpa} MPa)"
    )
    print(
        "Static safety factors: "
        f"bearing={safety_factors.bearing}, "
        f"shear={safety_factors.shear}, "
        f"bending={safety_factors.bending}"
    )
    print(
        f"Fatigue screening: {'enabled' if fatigue_config.enabled else 'disabled'}; "
        f"min_sf={fatigue_config.minimum_fatigue_sf}, "
        f"torque_min_ratio={fatigue_config.torque_min_ratio}, "
        f"dynamic_amp={fatigue_config.dynamic_amplification}"
    )
    print(
        f"Disc configuration: {'single' if args.single_disc else 'dual'}; "
        f"minimum eccentric bore SF={args.min_bore_sf}; "
        f"minimum output shaft SF={args.min_output_shaft_sf}; "
        f"minimum profile radius={args.min_profile_radius_mm} mm; "
        f"disc-pin clearance={args.disc_pin_clearance_mm} mm; "
        f"profile points={args.profile_points}"
    )
    print(
        f"Assembly validation: {'disabled' if args.disable_assembly_validation else 'enabled'}"
    )
    print(f"Candidate count: {len(candidates)}")
    if args.top_n > len(candidates):
        print(f"Requested top_n={args.top_n}, available candidates={len(candidates)}")
    print(f"CSV written to: {written_csv.resolve()}")

    if candidates:
        best = candidates[0]
        if not args.no_svg:
            svg_path = Path(args.out_svg)
            write_candidate_svg(best, svg_path)
            print(f"SVG written to: {svg_path.resolve()}")
        if args.out_step:
            step_path = Path(args.out_step)
            try:
                if not args.disable_assembly_validation:
                    validation = validate_candidate_geometry(best, dual_discs=not args.single_disc)
                    if not validation.passed:
                        raise RuntimeError(validation.message)
                export_candidate_step(
                    best,
                    step_path,
                    eccentric_shaft_hole_diameter_mm=args.ecc_shaft_hole_dia_mm,
                    dual_discs=not args.single_disc,
                    validate_profile=not args.disable_assembly_validation,
                    min_profile_radius_mm=args.min_profile_radius_mm,
                    disc_pin_clearance_mm=args.disc_pin_clearance_mm,
                    profile_points=args.profile_points,
                )
                print(f"STEP written to: {step_path.resolve()}")
            except RuntimeError as exc:
                print(f"STEP export skipped: {exc}")
        if args.out_step_disc:
            disc_step_path = Path(args.out_step_disc)
            try:
                export_cycloidal_disc_step(
                    best,
                    disc_step_path,
                    eccentric_shaft_hole_diameter_mm=args.ecc_shaft_hole_dia_mm,
                    validate_profile=not args.disable_assembly_validation,
                    min_profile_radius_mm=args.min_profile_radius_mm,
                    disc_pin_clearance_mm=args.disc_pin_clearance_mm,
                    profile_points=args.profile_points,
                )
                print(f"Disc STEP written to: {disc_step_path.resolve()}")
            except RuntimeError as exc:
                print(f"Disc STEP export skipped: {exc}")
        if args.out_step_assembly:
            assembly_step_path = Path(args.out_step_assembly)
            try:
                if not args.disable_assembly_validation:
                    validation = validate_candidate_geometry(best, dual_discs=not args.single_disc)
                    if not validation.passed:
                        raise RuntimeError(validation.message)
                export_candidate_step(
                    best,
                    assembly_step_path,
                    eccentric_shaft_hole_diameter_mm=args.ecc_shaft_hole_dia_mm,
                    dual_discs=not args.single_disc,
                    validate_profile=not args.disable_assembly_validation,
                    min_profile_radius_mm=args.min_profile_radius_mm,
                    disc_pin_clearance_mm=args.disc_pin_clearance_mm,
                    profile_points=args.profile_points,
                )
                print(f"Assembly STEP written to: {assembly_step_path.resolve()}")
            except RuntimeError as exc:
                print(f"Assembly STEP export skipped: {exc}")
        if args.out_step_disc_pins_shaft:
            mesh_step_path = Path(args.out_step_disc_pins_shaft)
            try:
                export_disc_pins_shaft_step(
                    best,
                    mesh_step_path,
                    eccentric_shaft_hole_diameter_mm=args.ecc_shaft_hole_dia_mm,
                    validate_profile=not args.disable_assembly_validation,
                    min_profile_radius_mm=args.min_profile_radius_mm,
                    disc_pin_clearance_mm=args.disc_pin_clearance_mm,
                    profile_points=args.profile_points,
                    contact_band_mm=args.contact_band_mm,
                    contact_alpha_rad=0.0,
                )
                print(f"Disc+pins+shaft STEP written to: {mesh_step_path.resolve()}")
            except RuntimeError as exc:
                print(f"Disc+pins+shaft STEP export skipped: {exc}")
        contact_stats = estimate_contact_pin_stats(
            candidate=best,
            disc_pin_clearance_mm=args.disc_pin_clearance_mm,
            contact_band_mm=args.contact_band_mm,
            angle_samples=args.contact_angle_samples,
            profile_samples=args.contact_profile_samples,
            phase_rad=0.0,
        )
        print(
            "Estimated ring-pin contact (disc A): "
            f"min={contact_stats.min_contact_pins}, "
            f"avg={contact_stats.avg_contact_pins:.2f}, "
            f"max={contact_stats.max_contact_pins} "
            f"(band=+/-{contact_stats.contact_band_mm} mm)"
        )
        report_path = Path(args.out_report)
        written_report = write_report(
            report_path,
            args=args,
            best=asdict(best),
            contact=contact_stats,
        )
        print(f"Report written to: {written_report.resolve()}")
        if args.out_ansys_model:
            ansys_path = Path(args.out_ansys_model)
            written_ansys = write_ansys_static_template(
                path=ansys_path,
                candidate=best,
                material=material,
                target_torque_nm=args.target_torque,
                motor_speed_rpm=args.motor_speed_rpm,
                contact_stats=contact_stats,
            )
            print(f"ANSYS model template written to: {written_ansys.resolve()}")
        print("\nBest candidate:")
        for key, value in asdict(best).items():
            print(f"  {key}: {value}")
    else:
        print(
            "\nNo valid candidates found. "
            "Try reducing target torque, adjusting factors, "
            "or widening geometry search bounds."
        )


if __name__ == "__main__":
    main()
