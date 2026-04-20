"""Segment construction and per-segment per-card earn.

The segmented calculation path splits the wallet's calculation window into
contiguous segments at every card open/close/SUB-earn boundary and at every
capped-group period boundary, then computes points per segment. This module
hosts the segment builder, the per-card per-category segment earn function
(with cap enforcement), and the segmented category breakdown. The LP-based
optimal allocation lives in ``segment_lp.py``; the top-level orchestrator is
in ``segmented_ev.py``.
"""
from __future__ import annotations

from datetime import date

from ..date_utils import add_months
from .allocation import (
    _compute_category_shares,
    calc_annual_allocated_spend,
    calc_category_earn_breakdown,
)
from .currency import _wallet_currency_ids
from .multipliers import (
    _all_other_multiplier,
    _build_effective_multipliers,
    _multiplier_for_category,
    _pct_bonus,
)
from .types import CardData


# ---------------------------------------------------------------------------
# Cap-period helper
# ---------------------------------------------------------------------------


def _cap_period_bounds(d: date, cap_months: int) -> tuple[date, date]:
    """
    Return (period_start, period_end) for the cap period containing date d.
    Periods are anchored at Jan 1 of each year and advance in steps of cap_months,
    so 12=calendar year, 6=semi-annual (Jan/Jul), 3=calendar quarters, 1=calendar months.
    period_end is the start of the next period (exclusive).
    """
    months_since_anchor = (d.year - 1) * 12 + (d.month - 1)
    period_idx = months_since_anchor // cap_months
    start_total_months = period_idx * cap_months
    start_year = start_total_months // 12 + 1
    start_month = start_total_months % 12 + 1
    period_start = date(start_year, start_month, 1)
    period_end = add_months(period_start, cap_months)
    return period_start, period_end


# ---------------------------------------------------------------------------
# Segment builder
# ---------------------------------------------------------------------------


def _build_segments(
    window_start: date,
    window_end: date,
    selected_cards: list[CardData],
) -> list[tuple[date, date, list[CardData]]]:
    """
    Split [window_start, window_end) into contiguous segments at every card
    open/close/sub-earn boundary.  Returns list of (seg_start, seg_end, active_cards).

    Also adds boundaries at cap-period starts for any selected card with a
    capped multiplier group, so segments never span a cap-period boundary
    (lets cap enforcement clamp per-segment spend without splitting later).

    When all cards have wallet_added_date=None and there are no capped groups,
    returns a single segment covering the full window with all selected cards
    active — identical to the non-segmented path.
    """
    change_dates: set[date] = {window_start, window_end}
    for card in selected_cards:
        for d in (card.wallet_added_date, card.wallet_closed_date):
            if d is not None and window_start < d < window_end:
                change_dates.add(d)
        if not card.sub_already_earned:
            earned = card.sub_projected_earn_date
            if earned is not None and window_start < earned < window_end:
                change_dates.add(earned)
        # SUB window expiry: ensures boost never bleeds past sub_window_end even if
        # sub_projected_earn_date is None or falls outside the calc window.
        if not card.sub_already_earned and card.wallet_added_date is not None and card.sub_months is not None:
            sub_window_end = add_months(card.wallet_added_date, card.sub_months)
            if window_start < sub_window_end < window_end:
                change_dates.add(sub_window_end)

    # Cap-period boundaries: every distinct cap_period_months across selected cards
    # gets period-start boundaries within the window.
    distinct_cap_months: set[int] = set()
    for card in selected_cards:
        for (
            _mult, _cats, _topn, _gid,
            cap_amt, cap_months, _is_rot, _rot_weights, _is_add,
        ) in card.multiplier_groups:
            if cap_amt is None or not cap_months or cap_months <= 0:
                continue
            distinct_cap_months.add(cap_months)
    for cap_months in distinct_cap_months:
        _, period_end = _cap_period_bounds(window_start, cap_months)
        cur = period_end
        while cur < window_end:
            if cur > window_start:
                change_dates.add(cur)
            cur = add_months(cur, cap_months)

    boundaries = sorted(change_dates)
    segments: list[tuple[date, date, list[CardData]]] = []
    for i in range(len(boundaries) - 1):
        seg_start, seg_end = boundaries[i], boundaries[i + 1]
        active = [
            c for c in selected_cards
            if (c.wallet_added_date or window_start) <= seg_start
            and (c.wallet_closed_date is None or c.wallet_closed_date >= seg_end)
        ]
        segments.append((seg_start, seg_end, active))
    return segments


# ---------------------------------------------------------------------------
# Per-card per-segment earn (with cap enforcement)
# ---------------------------------------------------------------------------


def _segment_card_earn_pts_per_cat(
    card: CardData,
    spend: dict[str, float],
    active_cards: list[CardData],
    seg_currency_ids: set[int],
    sub_priority_card_ids: set[int] | None,
    seg_days: int,
    seg_start: date,
    cap_state: dict[tuple, float],
    for_balance: bool = False,
) -> dict[str, float]:
    """
    Per-category segment-prorated points earned by `card` over this segment, in
    raw card-currency units (conversion not applied), with cap enforcement on
    capped multiplier groups. Annual bonus NOT included.

    Allocation matches calc_annual_point_earn_allocated: ties split category
    spend evenly across the best-rate cards. Cap enforcement has two flavors:

    - **Non-rotating capped group (e.g. BCP groceries 6% to $6k/yr):** all
      group categories share one cap dollar pool per period. When the focal
      card's allocated spend exceeds the remaining pool, the bonus dollars are
      distributed across the contributing categories *proportionally* to their
      individual seg-allocated spend (Phase 1a — order-independent). The
      remainder of each category's spend earns at the All Other rate.

    - **Rotating capped group (Discover IT, Chase Freedom Flex):** uses
      frequency-weighted allocation where spend is split based on activation
      probability. The card captures p_C share of category spend and earns at
      the full bonus rate on that share (up to the cap). Spend above the cap
      earns at the overflow rate. Categories with p_C = 0 (never historically
      active) get no bonus. There is no pooling across categories within the
      rotating group; each gets its own per-period budget.

    Both flavors share `cap_state`, keyed by:
      - non-rotating: ``("pool", group_id, period_start)`` → remaining $
      - rotating:     ``("rot", group_id, period_start, category_name)`` → remaining $

    The dict is mutated as caps are consumed; callers pass a fresh dict per
    (focal card, calc) pair so multi-segment cap periods share the budget
    chronologically.
    """
    if seg_days <= 0:
        return {}
    seg_years = seg_days / 365.25
    effective = _build_effective_multipliers(card, spend)
    all_other = _all_other_multiplier(effective)

    # Build capped-group lookups for the focal card.
    # group_id -> (group_mult, cap_amount, cap_months, is_rotating, rot_weights, is_additive)
    capped_groups: dict[int, tuple[float, float, int, bool, dict[str, float], bool]] = {}
    cat_to_capped_gid: dict[str, int] = {}
    for (
        g_mult, g_cats, _topn, g_id,
        g_cap_amt, g_cap_months, g_is_rot, g_rot_weights, g_is_add,
    ) in card.multiplier_groups:
        if g_id is None or g_cap_amt is None or not g_cap_months or g_cap_months <= 0:
            continue
        # Normalize rotation weights to lowercased keys for case-insensitive lookup.
        rot_lookup = {(k or "").strip().lower(): float(v) for k, v in g_rot_weights.items()}
        capped_groups[g_id] = (
            float(g_mult), float(g_cap_amt), int(g_cap_months),
            bool(g_is_rot), rot_lookup, bool(g_is_add),
        )
        for c in g_cats:
            if c:
                cat_to_capped_gid[c.strip().lower()] = g_id

    # Portal premiums on this card, indexed by lowercased category name.
    # cat_lower -> (premium_value, is_additive). Only populated when the
    # card has a non-zero portal_share.
    portal_lookup: dict[str, tuple[float, bool]] = {}
    if card.portal_share > 0.0:
        for cl, premium, p_is_add in card.portal_premiums:
            portal_lookup[cl] = (float(premium), bool(p_is_add))

    # Pass 1: walk every spend category, classify, and stash results we'll
    # finalize in pass 2 (so non-rotating pooled groups can split the cap
    # proportionally across all contributing categories).
    out: dict[str, float] = {}
    # group_id -> list of (cat_name, seg_alloc_dollars, group_mult, cat_mult, is_additive)
    # for pooled groups. cat_mult is the always-on rate for that category on this card
    # (already includes uncapped additive premiums); is_additive comes from the group.
    pooled_pending: dict[int, list[tuple[str, float, float, float, bool]]] = {}

    for cat, s in spend.items():
        if s <= 0:
            continue

        if len(active_cards) <= 1:
            allocated_annual = s
            cat_mult = _multiplier_for_category(card, cat, spend)
        else:
            # Use frequency-weighted allocation for rotating categories
            shares = _compute_category_shares(
                active_cards, spend, cat, seg_currency_ids,
                sub_priority_card_ids, for_balance=for_balance,
            )
            card_share = next(
                ((share, mult) for c, share, mult in shares if c.id == card.id),
                None
            )
            if card_share is None:
                continue
            share_frac, cat_mult = card_share
            allocated_annual = s * share_frac

        seg_alloc_dollars = allocated_annual * seg_years
        cat_lower = cat.strip().lower()
        gid = cat_to_capped_gid.get(cat_lower)

        # Categories not in any capped group earn at their always-on rate
        # — plus an optional portal premium on `share × seg_alloc_dollars`.
        if gid is None:
            if cat_lower in portal_lookup and card.portal_share > 0.0:
                portal_premium, portal_is_add = portal_lookup[cat_lower]
                eligible = seg_alloc_dollars * card.portal_share
                non_eligible = seg_alloc_dollars - eligible
                if portal_is_add:
                    portal_rate = cat_mult + portal_premium
                else:
                    portal_rate = portal_premium
                pts = eligible * portal_rate + non_eligible * cat_mult
            else:
                pts = seg_alloc_dollars * cat_mult
            if pts > 0:
                out[cat] = out.get(cat, 0.0) + pts
            continue

        g_mult, g_cap_amt, g_cap_months, is_rotating, rot_weights, is_additive = capped_groups[gid]

        # For non-additive non-rotating groups: when top-N has demoted this
        # category to the All Other rate, the bonus path doesn't apply at all.
        # Rotating non-additive groups are intentionally excluded — they don't
        # use top-N, and their universe categories *naturally* have
        # cat_mult == all_other because the bonus rate lives on the group
        # (e.g. Discover IT's 5x), not on a standalone CardCategoryMultiplier.
        if (
            not is_additive
            and not is_rotating
            and cat_mult <= all_other + 1e-9
        ):
            pts = seg_alloc_dollars * cat_mult
            if pts > 0:
                out[cat] = out.get(cat, 0.0) + pts
            continue

        # Effective bonus and overflow rates per dollar:
        #   - Additive: bonus = cat_mult + g_mult (stack premium on top of always-on),
        #               overflow = cat_mult (still earns the always-on portion above the cap)
        #   - Non-additive: bonus = g_mult (replaces base), overflow = all_other (legacy)
        if is_additive:
            bonus_rate = cat_mult + g_mult
            overflow_rate = cat_mult
        else:
            bonus_rate = g_mult
            overflow_rate = all_other

        period_start, _ = _cap_period_bounds(seg_start, g_cap_months)

        if is_rotating:
            # With frequency-weighted allocation, the activation probability
            # is already accounted for in the spend share allocated to this
            # card. The card earns at the full bonus rate on its allocated
            # share, not an EV-blended rate.
            p_c = rot_weights.get(cat_lower, 0.0)
            if p_c <= 0.0:
                # Category is in the rotating universe but has never been
                # active in our recorded history → no bonus path.
                pts = seg_alloc_dollars * overflow_rate
                if pts > 0:
                    out[cat] = out.get(cat, 0.0) + pts
                continue
            key = ("rot", gid, period_start, cat_lower)
            if key not in cap_state:
                cap_state[key] = float(g_cap_amt)
            remaining = cap_state[key]
            bonus_dollars = min(seg_alloc_dollars, remaining)
            overflow_dollars = seg_alloc_dollars - bonus_dollars
            cap_state[key] = remaining - bonus_dollars
            # Use the full bonus rate since frequency is in the allocation share
            pts = bonus_dollars * bonus_rate + overflow_dollars * overflow_rate
            if pts > 0:
                out[cat] = out.get(cat, 0.0) + pts
            continue

        # Non-rotating pooled cap: stash for proportional finalization in pass 2.
        pooled_pending.setdefault(gid, []).append(
            (cat, seg_alloc_dollars, g_mult, cat_mult, is_additive)
        )

    # Pass 2: finalize pooled groups, splitting the remaining cap
    # proportionally to each category's seg-allocated spend.
    for gid, items in pooled_pending.items():
        g_mult, g_cap_amt, g_cap_months, _is_rot, _rot, g_is_add = capped_groups[gid]
        period_start, _ = _cap_period_bounds(seg_start, g_cap_months)
        key = ("pool", gid, period_start)
        if key not in cap_state:
            cap_state[key] = g_cap_amt
        remaining = cap_state[key]

        total_alloc = sum(d for _c, d, _m, _cm, _ia in items)
        if total_alloc <= 0:
            continue

        # Per-category effective rates: additive groups stack the premium on
        # top of cat_mult, non-additive groups use g_mult / all_other.
        def _bonus_rate(group_m: float, cat_m: float, item_is_add: bool) -> float:
            return cat_m + group_m if item_is_add else group_m

        def _overflow_rate(cat_m: float, item_is_add: bool) -> float:
            return cat_m if item_is_add else all_other

        if remaining <= 0:
            # Cap fully consumed by an earlier segment in this period.
            for cat_name, alloc_d, _gm, cat_m, item_is_add in items:
                pts = alloc_d * _overflow_rate(cat_m, item_is_add)
                if pts > 0:
                    out[cat_name] = out.get(cat_name, 0.0) + pts
            continue

        if total_alloc <= remaining:
            # Whole group fits under the cap; everything earns at bonus rate.
            for cat_name, alloc_d, gm, cat_m, item_is_add in items:
                pts = alloc_d * _bonus_rate(gm, cat_m, item_is_add)
                if pts > 0:
                    out[cat_name] = out.get(cat_name, 0.0) + pts
            cap_state[key] = remaining - total_alloc
        else:
            # Cap binds: each category gets a proportional share of remaining.
            for cat_name, alloc_d, gm, cat_m, item_is_add in items:
                bonus_share = alloc_d / total_alloc * remaining
                overflow = alloc_d - bonus_share
                pts = (
                    bonus_share * _bonus_rate(gm, cat_m, item_is_add)
                    + overflow * _overflow_rate(cat_m, item_is_add)
                )
                if pts > 0:
                    out[cat_name] = out.get(cat_name, 0.0) + pts
            cap_state[key] = 0.0

    return out


# ---------------------------------------------------------------------------
# SUB priority per segment
# ---------------------------------------------------------------------------


def _is_sub_active_in_segment(card: CardData, seg_start: date) -> bool:
    """
    Whether this card has an active SUB window at the given segment start.
    True when: card has an earnable SUB, is in its SUB window,
    and the SUB has not yet been earned before this segment starts.
    """
    if (
        not card.sub_points
        or not card.sub_min_spend
        or not card.sub_earnable
        or not card.wallet_added_date
        or card.sub_already_earned
    ):
        return False
    if seg_start < card.wallet_added_date:
        return False
    earned = card.sub_projected_earn_date
    if earned is not None and earned <= seg_start:
        return False
    sub_window_end = (
        add_months(card.wallet_added_date, card.sub_months)
        if card.sub_months
        else None
    )
    if sub_window_end is not None and seg_start >= sub_window_end:
        return False
    return True


def _sub_priority_ids_for_segment(
    active_cards: list[CardData],
    seg_start: date,
    spend: dict[str, float] | None = None,
    wallet_currency_ids: set[int] | None = None,
) -> set[int]:
    """
    Return the set of card IDs that have active SUB windows in this segment
    AND whose natural allocated spend (without priority) is insufficient to
    meet the SUB minimum. Cards that can hit the SUB naturally don't need
    the allocation boost.
    """
    candidates = {c.id for c in active_cards if _is_sub_active_in_segment(c, seg_start)}
    if not candidates or spend is None or wallet_currency_ids is None:
        return candidates
    result = set()
    for c in active_cards:
        if c.id not in candidates:
            continue
        natural_spend = calc_annual_allocated_spend(c, active_cards, spend, wallet_currency_ids)
        if c.sub_min_spend and natural_spend >= c.sub_min_spend:
            continue
        result.add(c.id)
    return result


# ---------------------------------------------------------------------------
# Time-weighted category breakdown (display-side)
# ---------------------------------------------------------------------------


def _segmented_category_earn_breakdown(
    card: CardData,
    selected_cards: list[CardData],
    spend: dict[str, float],
    window_start: date,
    window_end: date,
    precomputed_seg_alloc: list[dict[int, dict[str, float]]] | None = None,
) -> list[tuple[str, float]]:
    """
    Time-weighted per-category earn breakdown for the segmented calculation path.
    Points are accumulated as (seg_fraction × per-category-pts) across all
    segments where this card is active.

    precomputed_seg_alloc: optional pre-solved per-segment allocations from the
    LP optimizer. When provided, the breakdown reads from the cache to ensure it
    matches what _segmented_card_net_per_year computed for the same segments.
    """
    total_days = (window_end - window_start).days
    if total_days <= 0:
        return calc_category_earn_breakdown(
            card, selected_cards, spend, _wallet_currency_ids(selected_cards)
        )

    segments = _build_segments(window_start, window_end, selected_cards)
    cat_totals: dict[str, float] = {}
    local_cap_state: dict[tuple, float] = {}

    for seg_idx, (seg_start, seg_end, active) in enumerate(segments):
        if card not in active:
            continue
        seg_days = (seg_end - seg_start).days
        seg_currency_ids = {c.currency.id for c in active}
        sub_prio = _sub_priority_ids_for_segment(active, seg_start, spend, seg_currency_ids)
        if precomputed_seg_alloc is not None:
            seg_cat_pts = precomputed_seg_alloc[seg_idx].get(card.id, {})
        else:
            seg_cat_pts = _segment_card_earn_pts_per_cat(
                card, spend, active, seg_currency_ids, sub_prio,
                seg_days, seg_start, local_cap_state,
            )
        # seg_cat_pts is segment-actual raw-currency points. Convert to the
        # card's effective annual-rate share so the breakdown matches
        # annual_point_earn (which is also time-weighted annual rate).
        for cat, pts in seg_cat_pts.items():
            cat_totals[cat] = cat_totals.get(cat, 0) + pts * 365.25 / total_days

    # Annual bonus is included at full value (same as calc_annual_point_earn_allocated).
    if card.annual_bonus > 0:
        cat_totals["Annual Bonus"] = float(card.annual_bonus)
    # Recurring percentage bonus
    cat_pts_total = sum(v for k, v in cat_totals.items() if k != "Annual Bonus")
    pct_recurring = _pct_bonus(card, cat_pts_total)
    if pct_recurring > 0:
        cat_totals[f"Annual Bonus ({card.annual_bonus_percent:g}%)"] = pct_recurring

    result = [(cat, round(pts, 2)) for cat, pts in cat_totals.items() if pts > 0]
    result.sort(key=lambda x: x[1], reverse=True)
    return result
