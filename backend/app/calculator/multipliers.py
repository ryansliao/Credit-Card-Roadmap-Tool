"""Multiplier lookup + percentage bonus factor helpers.

Given a ``CardData`` and a spend dict, return the effective per-category
multiplier after top-N group logic and All Other fallback. Also hosts the
small percentage-bonus factor helpers used by both the simple and segmented
allocation paths.
"""
from __future__ import annotations

from datetime import date

from ..constants import ALL_OTHER_CATEGORY
from ..date_utils import add_months
from .currency import _comparison_cpp
from .types import CardData


# ---------------------------------------------------------------------------
# Category multiplier: All Other fallback + grouped top-N
# ---------------------------------------------------------------------------


def _all_other_multiplier(multipliers: dict[str, float]) -> float:
    """Get the All Other multiplier from a category->multiplier dict (case-insensitive)."""
    for cat, mult in multipliers.items():
        if cat.strip().lower() == ALL_OTHER_CATEGORY.lower():
            return mult
    return 1.0


def _spend_for_category(spend: dict[str, float], category: str) -> float:
    """Get spend amount for a category (case-insensitive match)."""
    c = (category or "").strip().lower()
    if not c:
        return 0.0
    for k, v in spend.items():
        if (k or "").strip().lower() == c:
            return v
    return 0.0


def _build_effective_multipliers(card: CardData, spend: dict[str, float]) -> dict[str, float]:
    """
    Build category -> multiplier map for this card given spend.
    Applies top-N logic for groups: only the top N spending categories in each group
    get the group rate; the rest get All Other.
    """
    effective = dict(card.multipliers)
    all_other = _all_other_multiplier(effective)

    for (
        _group_mult, group_cats, top_n, group_id,
        _cap_amt, _cap_months, _is_rot, _rot_weights, _is_add,
    ) in card.multiplier_groups:
        if top_n is None or top_n <= 0:
            continue
        # Use manual selections if present for this group, otherwise auto-pick by spend
        manual = card.group_selected_categories.get(group_id) if group_id else None
        if manual:
            top_set = manual
        else:
            # Rank group categories by spend (desc); only top N get group_mult
            ranked = sorted(
                group_cats,
                key=lambda c: _spend_for_category(spend, c) if c else 0.0,
                reverse=True,
            )
            top_set = set(ranked[:top_n])
        for cat in group_cats:
            key = cat.strip() if cat else ""
            if not key:
                continue
            if key not in top_set:
                # Overwrite multiplier for this category (match key in effective case-insensitively)
                for ek in list(effective):
                    if (ek or "").strip().lower() == key.lower():
                        effective[ek] = all_other
                        break
                else:
                    effective[key] = all_other

    return effective


def _multiplier_for_category(
    card: CardData, spend_category: str, spend: dict[str, float]
) -> float:
    """
    Return the multiplier for this spend category.
    Uses effective multipliers (with top-N applied) then All Other fallback.
    """
    effective = _build_effective_multipliers(card, spend)
    key = spend_category.strip()
    if key in effective:
        return effective[key]
    key_lower = key.lower()
    for cat, mult in effective.items():
        if cat.strip().lower() == key_lower:
            return mult
    return _all_other_multiplier(effective)


def _card_category_earn_rate(
    card: CardData,
    category: str,
    spend: dict[str, float],
    wallet_currency_ids: set[int],
) -> float:
    """Dollar earn rate for one card on one category: multiplier × CPP / 100."""
    m = _multiplier_for_category(card, category, spend)
    cpp = _comparison_cpp(card, wallet_currency_ids)
    return m * cpp / 100.0


# ---------------------------------------------------------------------------
# Percentage-bonus scoring factors
# ---------------------------------------------------------------------------


def _pct_bonus(card: CardData, cat_pts: float) -> float:
    """Recurring percentage bonus points (0 when first-year-only or no percent set)."""
    if card.annual_bonus_percent and not card.annual_bonus_first_year_only:
        return cat_pts * card.annual_bonus_percent / 100
    return 0.0


def _first_year_pct_bonus(card: CardData, cat_pts: float) -> float:
    """First-year-only percentage bonus points (0 when recurring or no percent set)."""
    if card.annual_bonus_percent and card.annual_bonus_first_year_only:
        return cat_pts * card.annual_bonus_percent / 100
    return 0.0


def _calc_earn_bonus_factor(card: CardData, years: int = 1) -> float:
    """Allocation scoring factor for the percentage bonus.

    Recurring: ``1 + pct/100`` (full every year).
    First-year-only: ``1 + pct/100/years`` (amortised over projection window).
    """
    if not card.annual_bonus_percent:
        return 1.0
    if card.annual_bonus_first_year_only:
        return 1 + card.annual_bonus_percent / 100 / max(years, 1)
    return 1 + card.annual_bonus_percent / 100


def _segment_earn_bonus_factor(card: CardData, seg_start: date) -> float:
    """Per-segment allocation factor for first-year-only percentage bonus.

    Returns the full factor during the card's first year, 1.0 after.
    Recurring bonuses always use the full factor regardless of segment.
    """
    if not card.annual_bonus_percent:
        return 1.0
    if not card.annual_bonus_first_year_only:
        return 1 + card.annual_bonus_percent / 100
    # First-year-only: active only during the card's first 12 months.
    if card.wallet_added_date:
        first_year_end = add_months(card.wallet_added_date, 12)
        if seg_start < first_year_end:
            return 1 + card.annual_bonus_percent / 100
    return 1.0
