"""Multiplier lookup + percentage bonus factor helpers.

Given a ``CardData`` and a spend dict, return the effective per-category
multiplier after top-N group logic and All Other fallback. Also hosts the
small percentage-bonus factor helpers used by both the simple and segmented
allocation paths.
"""
from __future__ import annotations

from dataclasses import replace as dataclass_replace
from datetime import date

from ..constants import ALL_OTHER_CATEGORY
from ..date_utils import add_months
from .currency import _comparison_cpp, _secondary_currency_comparison_bonus
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


def _compute_optimal_topn_selections(
    cards: list[CardData],
    selected_ids: set[int],
    spend: dict[str, float],
    wallet_currency_ids: set[int],
) -> list[CardData]:
    """Pre-compute optimal top-N category selections for all cards.

    For each card with a top-N multiplier group, selects the categories that
    maximize **incremental wallet value** — the additional dollar value the
    wallet gains by this card winning the category with the boosted rate vs
    the best alternative card earning it instead.

    This is smarter than just picking by raw spend: if another card already
    earns 4x on Groceries, boosting this card to 5x only provides +1x
    incremental; but boosting Gas from 1x to 5x provides +4x incremental even
    if Gas spend is lower.

    Spend caps are respected: if a group has a $1,500/quarter cap, only the
    first $6,000/year of spend in that category gets the bonus rate. Excess
    spend falls back to the All Other rate.

    Returns a new list of CardData with ``group_selected_categories`` populated.
    """
    if not cards:
        return cards

    selected_cards = [c for c in cards if c.id in selected_ids]
    if len(selected_cards) <= 1:
        return cards

    def _card_category_score(card: CardData, category: str, with_mult: float) -> float:
        """Compute allocation score for a card on a category with a given multiplier."""
        cpp = _comparison_cpp(card, wallet_currency_ids)
        sec_bonus = _secondary_currency_comparison_bonus(card, category=category)
        return with_mult * cpp * card.earn_bonus_factor + sec_bonus

    def _best_other_score(exclude_card: CardData, category: str) -> float:
        """Best score from other selected cards on this category (no top-N boost)."""
        best = 0.0
        for c in selected_cards:
            if c.id == exclude_card.id:
                continue
            m = c.multipliers.get(category)
            if m is None:
                for k, v in c.multipliers.items():
                    if k.strip().lower() == category.strip().lower():
                        m = v
                        break
            if m is None:
                m = _all_other_multiplier(c.multipliers)
            score = _card_category_score(c, category, m)
            if score > best:
                best = score
        return best

    result: list[CardData] = []
    for card in cards:
        if card.id not in selected_ids:
            result.append(card)
            continue

        has_topn_group = any(
            top_n is not None and top_n > 0
            for _, _, top_n, _, _, _, is_rot, _, _ in card.multiplier_groups
            if not is_rot
        )
        if not has_topn_group:
            result.append(card)
            continue

        selections: dict[int, set[str]] = {}

        for (
            group_mult, group_cats, top_n, group_id,
            cap_amt, cap_months, is_rotating, _rot_weights, _is_add,
        ) in card.multiplier_groups:
            if top_n is None or top_n <= 0 or is_rotating or group_id is None:
                continue

            all_other = _all_other_multiplier(card.multipliers)

            # Compute annual cap from per-period cap if present
            annual_cap: float | None = None
            if cap_amt is not None and cap_months and cap_months > 0:
                periods_per_year = 12 / cap_months
                annual_cap = cap_amt * periods_per_year

            incremental_values: list[tuple[str, float]] = []
            for cat in group_cats:
                if not cat:
                    continue
                cat_spend = _spend_for_category(spend, cat)
                if cat_spend <= 0:
                    incremental_values.append((cat, 0.0))
                    continue

                our_boosted_score = _card_category_score(card, cat, group_mult)
                our_base_score = _card_category_score(card, cat, all_other)
                best_other = _best_other_score(card, cat)

                if our_boosted_score <= best_other:
                    # Even with boost, we don't win this category
                    incremental_values.append((cat, 0.0))
                    continue

                # Apply cap: only capped_spend gets the boosted rate
                if annual_cap is not None and cat_spend > annual_cap:
                    capped_spend = annual_cap
                    overflow_spend = cat_spend - annual_cap
                else:
                    capped_spend = cat_spend
                    overflow_spend = 0.0

                # Value from capped portion: boosted rate vs best alternative
                capped_value = (our_boosted_score - best_other) * capped_spend / 100.0

                # Value from overflow: our base rate vs best alternative
                # (overflow goes to All Other rate regardless of boost)
                if overflow_spend > 0 and our_base_score > best_other:
                    overflow_value = (our_base_score - best_other) * overflow_spend / 100.0
                else:
                    overflow_value = 0.0

                # Total incremental value is the gain on the capped portion only,
                # since overflow earns the same whether or not we pick this category
                incremental = capped_value
                incremental_values.append((cat, incremental))

            incremental_values.sort(key=lambda x: x[1], reverse=True)
            top_cats = {cat for cat, _ in incremental_values[:top_n]}
            selections[group_id] = top_cats

        if selections:
            result.append(dataclass_replace(card, group_selected_categories=selections))
        else:
            result.append(card)

    return result


def _build_effective_multipliers(card: CardData, spend: dict[str, float]) -> dict[str, float]:
    """
    Build category -> multiplier map for this card given spend.
    Applies top-N logic for groups: only the top N spending categories in each group
    get the group rate; the rest get All Other.

    If ``group_selected_categories`` is populated (pre-computed by
    ``_compute_optimal_topn_selections``), uses those selections instead of
    falling back to spend-based ranking.
    """
    effective = dict(card.multipliers)
    all_other = _all_other_multiplier(effective)

    for (
        group_mult, group_cats, top_n, group_id,
        _cap_amt, _cap_months, is_rotating, _rot_weights, _is_add,
    ) in card.multiplier_groups:
        if top_n is None or top_n <= 0:
            continue

        precomputed = card.group_selected_categories.get(group_id) if group_id else None
        if precomputed:
            top_set = precomputed
        else:
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
            # Promotion only applies to non-rotating top-N groups (e.g. Bilt
            # Obsidian's "Dining or Groceries" choice). Rotating groups are
            # EV-blended by the segmented path via rotation_weights; the
            # simple path doesn't attempt to model them accurately.
            if key in top_set:
                if is_rotating:
                    continue  # leave whatever is in effective unchanged
                target_rate = group_mult
            else:
                target_rate = all_other
            # Upsert by case-insensitive match; only create a new key if none exists.
            for ek in list(effective):
                if (ek or "").strip().lower() == key.lower():
                    effective[ek] = target_rate
                    break
            else:
                effective[key] = target_rate

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
