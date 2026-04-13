"""Simple-path category allocation.

Tied-winner logic: each spend category is assigned to the card(s) with the
highest ``multiplier × CPP × earn_bonus_factor + secondary_bonus`` score.
Tied cards split category dollars evenly and each earns on their allocated
share.

The segmented (time-weighted) version of this allocation lives in
``segments.py`` / ``segment_lp.py`` / ``segmented_ev.py``; this module is
only the simple, full-wallet-active path used when no date context is
available.
"""
from __future__ import annotations

import math

from .currency import (
    _comparison_cpp,
    _conversion_rate,
    _secondary_currency_comparison_bonus,
)
from .multipliers import _multiplier_for_category, _pct_bonus
from .types import CardData

# Duplicated here to avoid importing from compute.py (which imports from this
# module). Must match the value in compute.py exactly.
FOREIGN_CAT_PREFIX = "__foreign__"


def _portal_blended_multiplier(card: CardData, category: str, base_mult: float) -> float:
    """Return the effective multiplier for *category* on *card*, blending in
    any portal premium according to ``card.portal_share``.

    When the card has no portal share or the category has no portal premium,
    returns ``base_mult`` unchanged.  Otherwise the result is::

        share * portal_rate + (1 - share) * base_mult

    where ``portal_rate`` is either a replacement or additive premium
    depending on the ``is_additive`` flag on the portal multiplier row.
    """
    if card.portal_share <= 0.0 or not card.portal_premiums:
        return base_mult
    cat_lower = category.strip().lower()
    for cl, premium, is_add in card.portal_premiums:
        if cl == cat_lower:
            portal_rate = (base_mult + premium) if is_add else premium
            return card.portal_share * portal_rate + (1.0 - card.portal_share) * base_mult
    return base_mult


def _category_priority_cards(
    selected_cards: list[CardData],
    category: str,
) -> list[CardData]:
    """Return the subset of ``selected_cards`` that have ``category`` pinned
    via a manual wallet override. Returns an empty list when no card claims
    the category. Comparison is case-insensitive and strips the foreign
    prefix so ``__foreign__Dining`` matches a ``Dining`` priority.
    """
    base = category[len(FOREIGN_CAT_PREFIX):] if category.startswith(FOREIGN_CAT_PREFIX) else category
    key = (base or "").strip().lower()
    if not key:
        return []
    return [c for c in selected_cards if key in c.priority_categories]


def _tied_cards_for_category(
    selected_cards: list[CardData],
    spend: dict[str, float],
    category: str,
    wallet_currency_ids: set[int],
    sub_priority_card_ids: set[int] | None = None,
    for_balance: bool = False,
) -> list[CardData]:
    """
    All selected cards tied for the best multiplier × effective CPP on this category.
    Category dollars are split evenly across them; each card applies its own multiplier
    to its share (see calc_annual_point_earn_allocated).

    sub_priority_card_ids: when provided, cards with IDs in this set get absolute
    priority — they are the only candidates unless none are present. When multiple
    SUB-priority cards compete, they use normal multiplier × CPP scoring against
    each other.

    Category priority override: if any selected card pins ``category`` via its
    ``priority_categories`` set, only those cards compete. This takes precedence
    over the SUB priority filter so a manual pin always wins.

    for_balance: when True, uses default (non-overridden) CPP for scoring so that
    balance point totals are independent of wallet CPP overrides.
    """
    # Manual category pin overrides every other filter — honoured ahead of
    # SUB priority so a user pin always wins even during a SUB boost window.
    pinned = _category_priority_cards(selected_cards, category)
    if pinned:
        return sorted(pinned, key=lambda c: c.id)

    # SUB priority: if any selected cards are in the priority set, only they compete
    candidates = selected_cards
    if sub_priority_card_ids:
        priority = [c for c in selected_cards if c.id in sub_priority_card_ids]
        if priority:
            candidates = priority

    scored: list[tuple[float, CardData]] = []
    for c in candidates:
        m = _multiplier_for_category(c, category, spend)
        m = _portal_blended_multiplier(c, category, m)
        cpp = _comparison_cpp(c, wallet_currency_ids, for_balance=for_balance)
        # Secondary currency adds a flat value per dollar to the comparison score.
        # This ensures cards earning a secondary currency (e.g. Bilt Cash → Bilt Points)
        # compete at their true effective value, not just the primary multiplier.
        sec_bonus = _secondary_currency_comparison_bonus(c, category=category, for_balance=for_balance)
        scored.append((m * cpp * c.earn_bonus_factor + sec_bonus, c))
    if not scored:
        return []
    best = max(t[0] for t in scored)
    tied = [c for score, c in scored if math.isclose(score, best, rel_tol=0.0, abs_tol=1e-9)]
    tied.sort(key=lambda c: c.id)
    return tied


def calc_annual_point_earn(
    card: CardData,
    spend: dict[str, float],
) -> float:
    """Total points earned per year from category spend plus any annual bonus.
    Uses effective multipliers (top-N applied for groups) and All Other fallback.
    Includes recurring percentage bonus but NOT first-year-only percentage bonus.
    Portal premiums are blended in according to ``card.portal_share``.
    """
    cat_pts = sum(
        s * _portal_blended_multiplier(card, cat, _multiplier_for_category(card, cat, spend))
        for cat, s in spend.items()
        if s > 0
    )
    return float(card.annual_bonus) + cat_pts + _pct_bonus(card, cat_pts)


def calc_annual_point_earn_allocated(
    card: CardData,
    selected_cards: list[CardData],
    spend: dict[str, float],
    wallet_currency_ids: set[int],
    sub_priority_card_ids: set[int] | None = None,
    for_balance: bool = False,
) -> float:
    """
    Points from spend: each category is assigned to the card(s) with the best
    multiplier × effective CPP; tied cards split category dollars evenly, each
    earning (share × own multiplier). Annual bonus still applies in full to every card.

    sub_priority_card_ids: optional set of card IDs with active SUBs that get
    absolute priority in category allocation.

    for_balance: when True, uses default (non-overridden) CPP for scoring so that
    balance point totals are independent of wallet CPP overrides.
    """
    if len(selected_cards) <= 1:
        return calc_annual_point_earn(card, spend)
    cat_pts = 0.0
    for cat, s in spend.items():
        if s <= 0:
            continue
        tied = _tied_cards_for_category(selected_cards, spend, cat, wallet_currency_ids, sub_priority_card_ids, for_balance=for_balance)
        if not tied or card.id not in {c.id for c in tied}:
            continue
        n = len(tied)
        m = _multiplier_for_category(card, cat, spend)
        m = _portal_blended_multiplier(card, cat, m)
        cat_pts += (s / n) * m
    return float(card.annual_bonus) + cat_pts + _pct_bonus(card, cat_pts)


def calc_annual_allocated_spend(
    card: CardData,
    selected_cards: list[CardData],
    spend: dict[str, float],
    wallet_currency_ids: set[int],
    sub_priority_card_ids: set[int] | None = None,
    exclude_categories: set[str] | None = None,
) -> float:
    """
    Total annual spend dollars allocated to this card by the category allocation logic.
    Mirrors calc_annual_point_earn_allocated but sums dollars instead of points.

    ``exclude_categories``: lowercase category names (and/or ``__foreign__``
    variants) to skip entirely — used by the secondary currency earn path so
    cards like Bilt 2.0 in Bilt Cash mode don't earn Bilt Cash on housing.
    """
    def _excluded(cat: str) -> bool:
        if not exclude_categories:
            return False
        return cat.lower() in exclude_categories

    if len(selected_cards) <= 1:
        return sum(s for cat, s in spend.items() if s > 0 and not _excluded(cat))
    total = 0.0
    for cat, s in spend.items():
        if s <= 0 or _excluded(cat):
            continue
        tied = _tied_cards_for_category(selected_cards, spend, cat, wallet_currency_ids, sub_priority_card_ids)
        if not tied or card.id not in {c.id for c in tied}:
            continue
        total += s / len(tied)
    return total


def calc_category_earn_breakdown(
    card: CardData,
    selected_cards: list[CardData],
    spend: dict[str, float],
    wallet_currency_ids: set[int],
    sub_priority_card_ids: set[int] | None = None,
) -> list[tuple[str, float]]:
    """
    Per-category annual earn breakdown: list of (category_name, points) sorted by points desc.
    Mirrors the allocation logic in calc_annual_point_earn_allocated.
    Includes spend categories with positive earn, plus annual bonus.
    Points are in raw (pre-conversion) currency units, consistent with category spend items.
    sub_priority_card_ids: optional set of card IDs with active SUBs for priority allocation.
    """
    result: list[tuple[str, float]] = []
    if len(selected_cards) <= 1:
        for cat, s in spend.items():
            if s <= 0:
                continue
            m = _multiplier_for_category(card, cat, spend)
            m = _portal_blended_multiplier(card, cat, m)
            pts = s * m
            if pts > 0:
                result.append((cat, round(pts, 2)))
    else:
        for cat, s in spend.items():
            if s <= 0:
                continue
            tied = _tied_cards_for_category(selected_cards, spend, cat, wallet_currency_ids, sub_priority_card_ids)
            if not tied or card.id not in {c.id for c in tied}:
                continue
            n = len(tied)
            m = _multiplier_for_category(card, cat, spend)
            m = _portal_blended_multiplier(card, cat, m)
            pts = (s / n) * m
            if pts > 0:
                result.append((cat, round(pts, 2)))
    if card.annual_bonus > 0:
        result.append(("Annual Bonus", float(card.annual_bonus)))
    # Percentage-based bonus line items
    cat_pts_total = sum(pts for _, pts in result if _ != "Annual Bonus")
    pct_recurring = _pct_bonus(card, cat_pts_total)
    if pct_recurring > 0:
        result.append((f"Annual Bonus ({card.annual_bonus_percent:g}%)", round(pct_recurring, 2)))
    result.sort(key=lambda x: x[1], reverse=True)
    return result


def _effective_annual_earn_allocated(
    card: CardData,
    spend: dict[str, float],
    selected_cards: list[CardData],
    wallet_currency_ids: set[int],
    sub_priority_card_ids: set[int] | None = None,
    for_balance: bool = False,
) -> float:
    """Wallet-allocated annual earn in the effective currency.

    Mirrors ``calc_annual_point_earn_allocated`` but multiplies by the card's
    conversion rate so upgraded currencies (UR Cash → Chase UR, etc.) are
    valued correctly.

    for_balance: when True, uses default (non-overridden) CPP for allocation
    scoring so that point totals used for balance display are independent of
    wallet CPP overrides.
    """
    return (
        calc_annual_point_earn_allocated(card, selected_cards, spend, wallet_currency_ids, sub_priority_card_ids, for_balance=for_balance)
        * _conversion_rate(card, wallet_currency_ids)
    )
