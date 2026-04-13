from __future__ import annotations

from itertools import combinations_with_replacement
from typing import List, Tuple

from .models import RatioSelection


def prod(values):
    out = 1
    for v in values:
        out *= v
    return out


def decompose_ratio(
    overall_ratio: int,
    min_stage_ratio: int = 6,
    max_stage_ratio: int = 119,
    max_stages: int = 3,
    top_n: int = 20,
) -> Tuple[List[Tuple[int, ...]], List[Tuple[int, Tuple[int, ...], int]]]:
    exact = []
    closest = []
    for stage_count in range(1, max_stages + 1):
        for combo in combinations_with_replacement(
            range(min_stage_ratio, max_stage_ratio + 1), stage_count
        ):
            total = prod(combo)
            err = abs(total - overall_ratio)
            if total == overall_ratio:
                exact.append(combo)
            closest.append((err, combo, total))
    closest.sort(key=lambda x: (x[0], len(x[1]), x[1]))
    return exact, closest[:top_n]


def choose_representative_stage(
    overall_ratio: int,
    stage_ratio: int | None,
    max_stages: int,
    min_stage_ratio: int,
    max_stage_ratio: int,
) -> RatioSelection:
    if stage_ratio is not None:
        return RatioSelection(representative_stage_ratio=stage_ratio, source_combo=None)

    exact, closest = decompose_ratio(
        overall_ratio,
        min_stage_ratio=min_stage_ratio,
        max_stage_ratio=max_stage_ratio,
        max_stages=max_stages,
        top_n=10,
    )
    if exact:
        exact_sorted = sorted(
            exact,
            key=lambda combo: (max(combo) - min(combo), len(combo), combo),
        )
        combo = exact_sorted[0]
        representative = combo[len(combo) // 2]
        return RatioSelection(representative_stage_ratio=representative, source_combo=combo)

    best = closest[0][1]
    representative = best[len(best) // 2]
    return RatioSelection(representative_stage_ratio=representative, source_combo=best)
