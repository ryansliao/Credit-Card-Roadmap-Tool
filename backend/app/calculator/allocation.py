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

from ..constants import HOUSING_PROCESSING_FEE_PERCENT
from .currency import (
    _comparison_cpp,
    _conversion_rate,
    _secondary_currency_comparison_bonus,
)
from .multipliers import (
    _all_other_multiplier,
    _get_category_appearance_rate,
    _multiplier_for_category,
    _pct_bonus,
)
from .types import CardData

# Duplicated here to avoid importing from compute.py (which imports from this
# module). Must match the value in compute.py exactly.
FOREIGN_CAT_PREFIX = "__foreign__"


def _housing_fee_score_penalty(card: CardData, category: str) -> float:
    """Cents/$ to subtract from a card's allocation score on a housing
    category. Returns 0 for waived cards or non-housing categories.

    The penalty is the housing processing fee (3%) expressed in the same
    cents/$ units as the score (mult × cpp + sec_bonus). Subtracting it
    lets the LP/tied-winner pick the post-fee best card without mutating
    the gross multiplier, so ``category_multipliers`` and ROS stay clean.
    """
    if not card.housing_fee_categories:
        return 0.0
    base = (
        category[len(FOREIGN_CAT_PREFIX):]
        if category.startswith(FOREIGN_CAT_PREFIX)
        else category
    )
    if base.strip().lower() in card.housing_fee_categories:
        return HOUSING_PROCESSING_FEE_PERCENT
    return 0.0


def _rotating_cap_info(
    card: CardData, category: str
) -> tuple[int, float, float, float] | None:
    """Return ``(group_id, annual_bonus_cap_dollars, bonus_mult, overflow_mult)``
    for the rotating group containing ``category`` on ``card``.

    Returns ``None`` when the category is not in any rotating group on the
    card, when the matching group has no per-period cap, or when the group
    has no group_id (which would prevent pooling).

    The annual cap is ``cap_amt × (12 / cap_months)``, the per-period cap
    grossed up to a year. The cap is pooled across all categories in the
    same rotating group — at most ``cap_amt`` of bonus-rate spend per
    period across the entire group, so at most ``annual_cap`` per year.

    The bonus rate matches ``_build_effective_multipliers`` for rotating
    groups: additive groups stack the premium on the always-on rate;
    non-additive groups use the group multiplier as a replacement. The
    overflow rate is the card's always-on rate for the category (the explicit
    rate when set, otherwise All Other).
    """
    base_cat = (
        category[len(FOREIGN_CAT_PREFIX):]
        if category.startswith(FOREIGN_CAT_PREFIX)
        else category
    )
    cat_lower = (base_cat or "").strip().lower()
    if not cat_lower:
        return None
    for (
        g_mult, g_cats, _topn, gid,
        cap_amt, cap_months, is_rotating, _rot, is_add,
    ) in card.multiplier_groups:
        if not is_rotating or gid is None:
            continue
        cats_lower = {(c or "").strip().lower() for c in g_cats}
        if cat_lower not in cats_lower:
            continue
        if cap_amt is None or not cap_months or cap_months <= 0:
            return None
        annual_cap = float(cap_amt) * (12.0 / float(cap_months))
        overflow_mult = _all_other_multiplier(card.multipliers)
        for ek, ev in card.multipliers.items():
            if (ek or "").strip().lower() == cat_lower:
                overflow_mult = ev
                break
        bonus_mult = (overflow_mult + g_mult) if is_add else g_mult
        return gid, annual_cap, bonus_mult, overflow_mult
    return None


def _pooled_rotating_blends(
    card: CardData,
    captures: list[tuple[str, float, float]],
) -> dict[str, float]:
    """Return ``{category: effective_mult}`` for rotating categories on
    ``card`` where the pooled per-group annual cap binds.

    ``captures`` is a list of ``(category, captured_dollars, bonus_mult)``
    rows — one per spend category that landed on this card. Categories not
    in any rotating group are ignored, and rotating groups whose total
    captured spend stays at or below the annual cap return no entries (the
    caller falls back to the original ``bonus_mult``).

    When the pool binds, each member category gets a proportional share of
    the bonus budget and the rest earns at its own overflow rate. The
    spend-weighted blend lets the caller keep the simple ``captured × mult``
    math while reflecting the cap.

    The segmented path enforces caps per period itself, so callers in that
    path must NOT use this helper.
    """
    grouped: dict[int, list[tuple[str, float, float, float]]] = {}
    annual_caps: dict[int, float] = {}
    for cat, captured, bonus_mult in captures:
        if captured <= 0:
            continue
        info = _rotating_cap_info(card, cat)
        if info is None:
            continue
        gid, annual_cap, _bonus, overflow_mult = info
        grouped.setdefault(gid, []).append((cat, captured, bonus_mult, overflow_mult))
        annual_caps[gid] = annual_cap

    out: dict[str, float] = {}
    for gid, items in grouped.items():
        cap = annual_caps[gid]
        total = sum(captured for _c, captured, _b, _o in items)
        if total <= cap or total <= 0:
            continue
        for cat, captured, bonus_mult, overflow_mult in items:
            cap_share = (captured / total) * cap
            overflow_share = captured - cap_share
            out[cat] = (
                cap_share * bonus_mult + overflow_share * overflow_mult
            ) / captured
    return out


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


def _compute_category_shares(
    selected_cards: list[CardData],
    spend: dict[str, float],
    category: str,
    wallet_currency_ids: set[int],
    sub_priority_card_ids: set[int] | None = None,
    for_balance: bool = False,
) -> list[tuple[CardData, float, float]]:
    """
    Compute each card's share of a category's spend using frequency-weighted allocation.

    For rotating categories, cards compete at their full bonus rate and capture
    their activation frequency's share of spend. Higher-rate cards get priority;
    remaining spend goes to the next-best card.

    Returns list of (card, share, multiplier) tuples sorted by share descending.
    ``share`` is a fraction in [0, 1] summing to 1.0 across all cards.
    ``multiplier`` is the rate at which the card earns on its share.

    Example: Freedom (5x, freq=0.167) vs CSP (3x, freq=1.0) for dining
    - Freedom has higher rate (5x > 3x), gets first priority
    - Freedom captures 0.167 of spend at 5x
    - CSP captures remaining 0.833 at 3x
    """
    # SUB priority filtering
    candidates = selected_cards
    if sub_priority_card_ids:
        priority = [c for c in selected_cards if c.id in sub_priority_card_ids]
        if priority:
            candidates = priority

    # Manual category pin: pinned cards get all spend
    pinned = _category_priority_cards(candidates, category)
    if pinned:
        n = len(pinned)
        return [(c, 1.0 / n, _portal_blended_multiplier(c, category, _multiplier_for_category(c, category, spend))) for c in pinned]

    # Build scored list: (score, card, multiplier, frequency)
    scored: list[tuple[float, CardData, float, float]] = []
    for c in candidates:
        m = _multiplier_for_category(c, category, spend)
        m = _portal_blended_multiplier(c, category, m)
        freq = _get_category_appearance_rate(c, category)
        cpp = _comparison_cpp(c, wallet_currency_ids, for_balance=for_balance)
        sec_bonus = _secondary_currency_comparison_bonus(c, category=category, for_balance=for_balance)
        score = m * cpp * c.earn_bonus_factor + sec_bonus - _housing_fee_score_penalty(c, category)
        scored.append((score, c, m, freq))

    if not scored:
        return []

    # Sort by score descending (highest rate gets priority)
    scored.sort(key=lambda x: (-x[0], x[1].id))

    # Greedy allocation: each card gets min(their_frequency, remaining) share
    remaining = 1.0
    result: list[tuple[CardData, float, float]] = []

    for score, card, mult, freq in scored:
        if remaining <= 0:
            break
        share = min(freq, remaining)
        if share > 1e-9:
            result.append((card, share, mult))
            remaining -= share

    # Sort by share descending for consistent output
    result.sort(key=lambda x: (-x[1], x[0].id))
    return result


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
    each other. SUB priority takes precedence over manual category pins since
    hitting minimum spend is critical.

    Category priority override: if any candidate card pins ``category`` via its
    ``priority_categories`` set, only those cards compete. This applies after
    SUB priority filtering, so pins only affect allocation among non-SUB cards
    or among SUB cards if multiple have pins.

    for_balance: when True, uses default (non-overridden) CPP for scoring so that
    balance point totals are independent of wallet CPP overrides.
    """
    # SUB priority: if any selected cards are in the priority set, only they compete.
    # SUB priority takes precedence over manual category pins since hitting the
    # minimum spend is more important than category optimization.
    candidates = selected_cards
    if sub_priority_card_ids:
        priority = [c for c in selected_cards if c.id in sub_priority_card_ids]
        if priority:
            candidates = priority

    # Manual category pin: if any candidate has this category pinned, use only
    # the pinned cards. This applies after SUB filtering, so pins only affect
    # allocation among non-SUB cards or among multiple SUB cards with pins.
    pinned = _category_priority_cards(candidates, category)
    if pinned:
        return sorted(pinned, key=lambda c: c.id)

    scored: list[tuple[float, CardData]] = []
    for c in candidates:
        m = _multiplier_for_category(c, category, spend)
        m = _portal_blended_multiplier(c, category, m)
        cpp = _comparison_cpp(c, wallet_currency_ids, for_balance=for_balance)
        # Secondary currency adds a flat value per dollar to the comparison score.
        # This ensures cards earning a secondary currency (e.g. Bilt Cash → Bilt Points)
        # compete at their true effective value, not just the primary multiplier.
        sec_bonus = _secondary_currency_comparison_bonus(c, category=category, for_balance=for_balance)
        score = m * cpp * c.earn_bonus_factor + sec_bonus - _housing_fee_score_penalty(c, category)
        scored.append((score, c))
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
    Points from spend using time-weighted allocation for rotating categories.

    Each category's spend is split among cards based on their rates and activation
    probabilities. Higher-rate cards get priority; rotating cards capture their
    probability share at full bonus rate, with remaining spend going to the next
    best card.

    sub_priority_card_ids: optional set of card IDs with active SUBs that get
    absolute priority in category allocation.

    for_balance: when True, uses default (non-overridden) CPP for scoring so that
    balance point totals are independent of wallet CPP overrides.
    """
    if len(selected_cards) <= 1:
        return calc_annual_point_earn(card, spend)
    per_cat: list[tuple[str, float, float]] = []
    for cat, s in spend.items():
        if s <= 0:
            continue
        shares = _compute_category_shares(
            selected_cards, spend, cat, wallet_currency_ids,
            sub_priority_card_ids, for_balance=for_balance
        )
        for c, share, mult in shares:
            if c.id == card.id:
                per_cat.append((cat, s * share, mult))
                break
    blends = _pooled_rotating_blends(card, per_cat)
    cat_pts = 0.0
    for cat, captured, mult in per_cat:
        cat_pts += captured * blends.get(cat, mult)
    return float(card.annual_bonus) + cat_pts + _pct_bonus(card, cat_pts)


def calc_housing_spend_allocated(
    card: CardData,
    selected_cards: list[CardData],
    spend: dict[str, float],
    wallet_currency_ids: set[int],
    sub_priority_card_ids: set[int] | None = None,
) -> float:
    """Annual housing-category spend dollars allocated to this card under
    the standard allocation logic. Used to compute the per-card housing
    processing fee — only categories in ``card.housing_fee_categories``
    contribute, so waived cards always return 0. Foreign-eligible variants
    (``__foreign__Rent``) count too if their base category is in the set.
    """
    if not card.housing_fee_categories:
        return 0.0
    def _is_housing(cat: str) -> bool:
        base = cat[len(FOREIGN_CAT_PREFIX):] if cat.startswith(FOREIGN_CAT_PREFIX) else cat
        return base.strip().lower() in card.housing_fee_categories

    if len(selected_cards) <= 1:
        return sum(s for cat, s in spend.items() if s > 0 and _is_housing(cat))
    total = 0.0
    for cat, s in spend.items():
        if s <= 0 or not _is_housing(cat):
            continue
        shares = _compute_category_shares(
            selected_cards, spend, cat, wallet_currency_ids, sub_priority_card_ids,
        )
        for c, share, _mult in shares:
            if c.id == card.id:
                total += s * share
                break
    return total


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
        shares = _compute_category_shares(selected_cards, spend, cat, wallet_currency_ids, sub_priority_card_ids)
        for c, share, _mult in shares:
            if c.id == card.id:
                total += s * share
                break
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
        per_cat: list[tuple[str, float, float]] = []
        for cat, s in spend.items():
            if s <= 0:
                continue
            shares = _compute_category_shares(selected_cards, spend, cat, wallet_currency_ids, sub_priority_card_ids)
            for c, share, mult in shares:
                if c.id == card.id:
                    per_cat.append((cat, s * share, mult))
                    break
        blends = _pooled_rotating_blends(card, per_cat)
        for cat, captured, mult in per_cat:
            pts = captured * blends.get(cat, mult)
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
