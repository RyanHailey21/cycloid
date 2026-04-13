from __future__ import annotations

from typing import Dict

from .models import Material


MATERIAL_LIBRARY: Dict[str, Material] = {
    "4140_qt": Material(
        name="4140 Q&T Steel",
        density_kg_m3=7850.0,
        elastic_modulus_gpa=205.0,
        poisson_ratio=0.29,
        yield_strength_mpa=655.0,
    ),
    "1045_cd": Material(
        name="1045 Cold Drawn Steel",
        density_kg_m3=7850.0,
        elastic_modulus_gpa=205.0,
        poisson_ratio=0.29,
        yield_strength_mpa=530.0,
    ),
    "17_4ph_h900": Material(
        name="17-4PH Stainless (H900)",
        density_kg_m3=7800.0,
        elastic_modulus_gpa=200.0,
        poisson_ratio=0.27,
        yield_strength_mpa=1170.0,
    ),
    "7075_t6": Material(
        name="7075-T6 Aluminum",
        density_kg_m3=2810.0,
        elastic_modulus_gpa=71.7,
        poisson_ratio=0.33,
        yield_strength_mpa=505.0,
    ),
}


def get_material(material_key: str) -> Material:
    key = material_key.lower()
    if key not in MATERIAL_LIBRARY:
        valid = ", ".join(sorted(MATERIAL_LIBRARY.keys()))
        raise ValueError(f"Unknown material '{material_key}'. Valid options: {valid}")
    return MATERIAL_LIBRARY[key]


def available_material_keys():
    return sorted(MATERIAL_LIBRARY.keys())
