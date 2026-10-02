"""Relative footfall classification and ranking (pure functions).

Categories are not fixed thresholds: poles are ranked by footfall and split
by configurable shares of the distribution (top 25% HIGH, next 40% MEDIUM,
rest LOW by default). Poles with equal footfall always share a category.
"""

import bisect
import math
from collections.abc import Mapping
from dataclasses import dataclass

from app.models.enums import FootfallCategory


@dataclass(frozen=True)
class PoleRank:
    rank: int  # 1 = highest footfall overall
    category: FootfallCategory
    category_rank: int  # 1 = highest footfall within its category
    percentile: float  # share of poles with footfall <= this pole's, 0-100


def classify_footfall(
    footfall_by_id: Mapping[int, int], high_share: float, medium_share: float
) -> dict[int, PoleRank]:
    if not 0 <= high_share <= 1 or not 0 <= medium_share <= 1 or high_share + medium_share > 1:
        raise ValueError("high_share and medium_share must be in [0, 1] and sum to <= 1")

    n = len(footfall_by_id)
    if n == 0:
        return {}

    ordered = sorted(footfall_by_id.items(), key=lambda kv: (-kv[1], kv[0]))
    ascending = sorted(footfall_by_id.values())
    n_high = math.ceil(n * high_share)
    n_medium = math.ceil(n * (high_share + medium_share)) - n_high

    result: dict[int, PoleRank] = {}
    counters = {c: 0 for c in FootfallCategory}
    prev_value: int | None = None
    prev_category = FootfallCategory.HIGH
    prev_rank = 0
    for i, (pole_id, value) in enumerate(ordered):
        if value == prev_value:
            category, rank = prev_category, prev_rank  # ties share category & rank
        else:
            rank = i + 1
            if i < n_high:
                category = FootfallCategory.HIGH
            elif i < n_high + n_medium:
                category = FootfallCategory.MEDIUM
            else:
                category = FootfallCategory.LOW
        counters[category] += 1
        at_or_below = bisect.bisect_right(ascending, value)
        result[pole_id] = PoleRank(
            rank=rank,
            category=category,
            category_rank=counters[category],
            percentile=round(100 * at_or_below / n, 1),
        )
        prev_value, prev_category, prev_rank = value, category, rank
    return result
