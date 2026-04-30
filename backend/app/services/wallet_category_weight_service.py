"""Per-wallet override of UserSpendCategoryMapping.default_weight.

The service exposes CRUD for the editor in the Spending tab. The
``apply_weight_overrides`` helper is pure (no DB) and is also used by
CalculatorDataService to merge override rows into the mapping
expansion before normalization.
"""
from __future__ import annotations

from typing import Iterable


def apply_weight_overrides(
    defaults_by_user_cat: dict[int, list[tuple[int, str, float]]],
    overrides: dict[tuple[int, int], float],
) -> dict[int, list[tuple[str, float]]]:
    """Merge per-wallet weight overrides into the default mapping set.

    Args:
        defaults_by_user_cat: Maps user_category_id -> list of
            (earn_category_id, earn_category_name, default_weight).
            This is the live default mapping set as loaded from
            UserSpendCategoryMapping.
        overrides: Maps (user_category_id, earn_category_id) -> weight
            from the wallet_user_spend_category_weights table.

    Returns:
        Maps user_category_id -> list of (earn_category_name, weight)
        with overrides applied. Iteration order matches the input
        defaults so the calculator's downstream normalization is stable.
        Override rows for earn_category_ids not in the current default
        set are silently ignored (they're orphans from a since-changed
        seed).
    """
    out: dict[int, list[tuple[str, float]]] = {}
    for user_cat_id, rows in defaults_by_user_cat.items():
        merged: list[tuple[str, float]] = []
        for earn_cat_id, earn_cat_name, default_weight in rows:
            weight = overrides.get((user_cat_id, earn_cat_id), default_weight)
            merged.append((earn_cat_name, weight))
        out[user_cat_id] = merged
    return out
