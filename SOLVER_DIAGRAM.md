# Cycloidal Drive Sizing — Solver Architecture

## Overview

This tool automatically generates and ranks candidate designs for a cycloidal reduction gear stage. Given a target torque, overall ratio, motor speed, and material, it sweeps a parameter space, enforces geometry and strength constraints analytically, scores each valid candidate, and exports a ranked CSV.

---

## Module Map

```
cycloidal_geometry_solver.py   ← CLI entry point
│
├── ratio.py                   ← decompose overall ratio into stage ratios
├── materials.py               ← material property library (4 presets)
├── models.py                  ← dataclasses: SolverConfig, Candidate, StrengthReport, …
│
└── cycloid/
    ├── solver.py              ← core design generator (main algorithm)
    └── strength.py            ← stress calculations & safety factor checks
```

---

## End-to-End Data Flow

```mermaid
flowchart TD
    A([CLI: cycloidal_geometry_solver.py]) --> B[Parse arguments\ntorque, ratio, material,\nsafety factors, RPM]
    B --> C[ratio.py\ndecompose_ratio → choose_representative_stage]
    C --> D[materials.py\nget_material]
    D --> E[Build SolverConfig]
    E --> F[solver.generate_candidates]

    subgraph LOOPS["Parameter Search Space — 6 nested loops"]
        L1[ring_roller_ratio] --> L2[eccentricity_ratio]
        L2 --> L3[output_pin_count]
        L3 --> L4[ro_ratio\noutput pin circle fraction]
        L4 --> L5[output_roller_fraction]
        L5 --> L6[disc_thickness_mm]
    end

    F --> LOOPS
    L6 --> G

    subgraph SIZING["required_radius_for_constraints()"]
        G[Check geometric\nfeasibility ratios] -->|invalid| SKIP1((skip))
        G -->|valid| H[Solve minimum ring pitch radius\nfrom 5 independent constraints]
        H --> H1[r_from_bearing\nHertz contact stress]
        H --> H2[r_from_pin_shear\noutput pin shear]
        H --> H3[r_from_lobe_shear\ncycloidal lobe shear]
        H --> H4[r_from_spacing\npin clearance]
        H --> H5[r_from_radial_margin\nfit inside ring]
        H1 & H2 & H3 & H4 & H5 --> I[required_radius = max of all 5]
    end

    I --> J[Round up to nearest step\nenforce min/max bounds]
    J -->|exceeds max| SKIP2((skip))
    J -->|OK| K[Compute full geometry\nring roller, eccentricity,\noutput pin circle, hole sizes]

    subgraph GEOM["Geometric Validity Checks"]
        K --> M1{output_hole ≥ 90%\nof pin spacing?}
        M1 -->|yes| SKIP3((skip))
        M1 -->|no| M2{radial_margin ≤ 0?}
        M2 -->|yes| SKIP4((skip))
        M2 -->|no| N[Compute forces\ntangential, per lobe,\nper output pin]
    end

    subgraph STRENGTH["strength.evaluate_strength()"]
        N --> O[Calculate 4 stress types\nbearing · pin shear\nlobe shear · ligament bending]
        O --> P{is_strength_acceptable?\nall SFs ≥ 1.0}
        P -->|no| SKIP5((skip))
        P -->|yes| Q[minimum_strength_sf]
    end

    subgraph SCORING["score_candidate()"]
        Q --> R["score =\n  +0.08 × radius          compactness\n  +1000 × |ecc − 0.03|    eccentricity preference\n  −0.20 × thickness        reward thinner disc\n  −0.15 × output margin    reward clearance\n  −0.08 × ring margin      reward clearance\n  −12   × min(SF, 3)       reward strength\n  +0.20 × bearing_stress   penalise stress"]
    end

    R --> S[Append Candidate\nall geometry + stresses + SFs + score]
    S --> LOOPS

    LOOPS -->|all combos done| T[Sort candidates\nby score ascending]
    T --> U[candidate_rows — top N]
    U --> V[write_csv]
    V --> W([cycloidal_geometry_candidates.csv])

    style LOOPS fill:#e8f4f8,stroke:#4a9abb
    style SIZING fill:#f0f8e8,stroke:#5a9a4a
    style GEOM   fill:#fff8e8,stroke:#b8860b
    style STRENGTH fill:#fde8e8,stroke:#bb4a4a
    style SCORING  fill:#f0e8f8,stroke:#7a4abb
```

---

## Key Stages Explained

### 1 — Ratio Decomposition (`ratio.py`)

`decompose_ratio()` finds all 1–3 stage combinations whose product equals (or closely approximates) the target overall ratio. `choose_representative_stage()` picks the best single-stage ratio to design for.

### 2 — Parameter Sweep (`solver.generate_candidates`)

Six nested loops span the continuous design space. Every combination of roller ratios, eccentricity, pin counts, circle fractions, and disc thickness is evaluated analytically — no FEA or iteration required.

### 3 — Minimum Radius (`required_radius_for_constraints`)

For a given parameter set, the function derives the minimum ring pitch radius **R** that satisfies five independent constraints simultaneously, each expressed as a closed-form formula:

| Constraint | Driven by |
|---|---|
| `r_from_bearing` | Hertz contact stress limit on output rollers |
| `r_from_pin_shear` | Shear stress across output pin cross-section |
| `r_from_lobe_shear` | Shear of cycloidal disc lobe under tangential force |
| `r_from_spacing` | Minimum clearance between adjacent output pins |
| `r_from_radial_margin` | Output pin circle must fit inside ring roller envelope |

`R = max(all five)` — the tightest constraint governs.

### 4 — Geometry Derivation

With **R** fixed, all absolute dimensions follow directly:

```
ring_roller_radius     = ring_roller_ratio × ring_pin_spacing(R)
eccentricity           = eccentricity_ratio × R
output_pin_circle_r    = ro_ratio × R
output_roller_diameter = output_roller_fraction × output_pin_spacing
output_hole_diameter   = output_roller_diameter + 2×eccentricity + 2×clearance
```

### 5 — Strength Verification (`strength.py`)

Four failure modes are checked. A candidate is rejected if any safety factor falls below 1.0:

| Failure Mode | Formula basis |
|---|---|
| Bearing stress | Projected area contact (force / area) |
| Output pin shear | Solid circular cross-section shear |
| Lobe shear | Disc lobe as a cantilever-shear element |
| Ligament bending | Thin-wall bending of material between output holes |

### 6 — Scoring (`score_candidate`)

A scalar score combines six terms (lower = better). The dominant drivers are:
- **Compactness** — penalises large radius
- **Eccentricity** — softly targets ~3 % of radius
- **Safety factor** — rewards margin above 1.0, saturates at SF = 3

Candidates are sorted ascending; `candidates[0]` is the recommended design.

---

## Output Fields (`Candidate`)

Each row in the CSV contains ~50 fields grouped into four categories:

| Category | Examples |
|---|---|
| Topology | `stage_ratio`, `ring_pin_count`, `lobe_count` |
| Geometry | `ring_pitch_radius_mm`, `eccentricity_mm`, `output_roller_diameter_mm`, `output_hole_diameter_mm` |
| Strength | `bearing_stress_mpa`, `sf_bearing`, `sf_lobe_shear`, `minimum_strength_sf` |
| Performance | `estimated_disc_outer_diameter_mm`, `estimated_output_speed_rpm`, `score` |

---

## Materials (`materials.py`)

| Key | Material | Yield (MPa) |
|---|---|---|
| `4140_qt` | 4140 Q&T Steel | 655 |
| `1045_cd` | 1045 Cold Drawn Steel | 530 |
| `17-4ph_h900` | 17-4PH Stainless H900 | 1170 |
| `7075_t6` | 7075-T6 Aluminium | 503 |

Pass with `--material <key>` on the CLI.
