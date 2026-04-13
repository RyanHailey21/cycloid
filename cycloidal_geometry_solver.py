"""
Cycloidal stage geometry solver
===============================

Generates candidate single-stage cycloidal drive geometries and performs
material-based first-pass strength checks.

Example
-------
python cycloidal_geometry_solver.py --overall-ratio 658503 --max-stages 3 --target-torque 3000 --material 4140_qt
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from pathlib import Path

from cycloid import (
    SafetyFactors,
    SolverConfig,
    available_material_keys,
    candidate_rows,
    choose_representative_stage,
    generate_candidates,
    get_material,
)


def write_csv(path: Path, rows):
    if not rows:
        return
    with path.open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


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

    config = SolverConfig(
        stage_ratio=ratio_selection.representative_stage_ratio,
        motor_speed_rpm=args.motor_speed_rpm,
        target_output_torque_nm=args.target_torque,
        material=material,
        safety_factors=safety_factors,
    )

    candidates = generate_candidates(config)

    out_csv = Path(args.out_csv)
    rows = candidate_rows(candidates, args.top_n)
    write_csv(out_csv, rows)

    print(f"Overall ratio target: {args.overall_ratio}:1")
    if ratio_selection.source_combo is not None:
        print(f"Representative stage chosen from decomposition: {ratio_selection.source_combo}")
    print(f"Representative stage ratio: {ratio_selection.representative_stage_ratio}:1")
    print(f"Ring pin count N: {ratio_selection.representative_stage_ratio + 1}")
    print(f"Lobe count: {ratio_selection.representative_stage_ratio}")
    print(f"Material: {material.name} (yield={material.yield_strength_mpa} MPa)")
    print(
        "Safety factors: "
        f"bearing={safety_factors.bearing}, "
        f"shear={safety_factors.shear}, "
        f"bending={safety_factors.bending}"
    )
    print(f"Candidate count: {len(candidates)}")
    print(f"CSV written to: {out_csv.resolve()}")

    if candidates:
        best = candidates[0]
        print("\nBest candidate:")
        for key, value in asdict(best).items():
            print(f"  {key}: {value}")
    else:
        print(
            "\nNo valid candidates found. "
            "Try reducing target torque, adjusting safety factors, "
            "or widening geometry search bounds."
        )


if __name__ == "__main__":
    main()
