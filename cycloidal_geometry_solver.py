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
    FatigueConfig,
    SafetyFactors,
    SolverConfig,
    available_material_keys,
    candidate_rows,
    choose_representative_stage,
    generate_candidates,
    get_material,
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
    print(f"Candidate count: {len(candidates)}")
    print(f"CSV written to: {written_csv.resolve()}")

    if candidates:
        best = candidates[0]
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
