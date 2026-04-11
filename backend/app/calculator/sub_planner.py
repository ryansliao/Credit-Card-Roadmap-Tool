"""SUB spend planning: EDF feasibility + EV-aware category split.

Plans how to direct wallet spend so all active sign-up-bonus minimums can be
hit before their deadlines with the smallest EV sacrifice. The core output
is a ``SubSpendPlan`` consumed by ``compute_wallet`` (to mark SUB-priority
cards) and by ``wallet_results.py`` (to surface projected earn dates to the
UI).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta

from ..date_utils import add_months
from .multipliers import _card_category_earn_rate
from .types import CardData, SubCardSchedule, SubSpendPlan


def plan_sub_targeting(
    sub_cards: list[CardData],
    spend: dict[str, float],
    window_start: date,
    wallet_currency_ids: set[int] | None = None,
) -> SubSpendPlan:
    """
    Determine whether all active SUB minimums can be met and how to split
    the wallet's spend categories to maximise EV while doing so.

    Algorithm (EV-aware urgency-constrained allocation):

    1. **Feasibility gate** — sort cards by deadline (EDF).  Simulate directing
       all wallet spend to each card in order.  If any card's minimum can't be
       met before its window expires, the plan is infeasible.

    2. **EV-optimal category assignment** — assign each spend category to the
       SUB card that earns the most dollar value on it (multiplier × CPP).
       This is the unconstrained EV-maximising split.

    3. **Urgency rebalancing** — walk cards from most to least urgent.  If a
       card's assigned categories don't provide enough daily spend to hit its
       minimum within its window, steal categories from less-urgent cards,
       choosing the categories where the earn-rate sacrifice is smallest first.
       This ensures all deadlines are met at minimum EV cost.

    4. **Surplus distribution** — any daily spend beyond what's needed for SUB
       minimums is directed to the card with the best earn rate on the remaining
       categories, so EV is maximised during the SUB period.
    """
    if not sub_cards:
        return SubSpendPlan(feasible=True, parallel=True)

    total_daily = sum(spend.values()) / 365.0
    if total_daily <= 0:
        return SubSpendPlan(feasible=False)

    # ---- gather per-card requirements ----
    # A card's effective spend window starts at the later of window_start and
    # its wallet_added_date (future cards can't receive spend before they open).
    @dataclass
    class _Need:
        card: CardData
        min_spend: float
        spend_start: date     # max(window_start, wallet_added_date)
        window_end: date
        remaining_days: int   # days between spend_start and window_end
        required_daily: float  # min_spend / remaining_days

    needs: list[_Need] = []
    for card in sub_cards:
        if not card.sub_min_spend or not card.wallet_added_date:
            continue
        w_end = (
            add_months(card.wallet_added_date, card.sub_months)
            if card.sub_months
            else add_months(window_start, 12)
        )
        spend_start = max(window_start, card.wallet_added_date)
        remaining = (w_end - spend_start).days
        if remaining <= 0:
            continue
        needs.append(
            _Need(
                card=card,
                min_spend=float(card.sub_min_spend),
                spend_start=spend_start,
                window_end=w_end,
                remaining_days=remaining,
                required_daily=card.sub_min_spend / remaining,
            )
        )

    if not needs:
        return SubSpendPlan(feasible=True, parallel=True)

    # ---- 1. feasibility gate (EDF sequential simulation) ----
    # Cards that open later don't compete for spend with earlier cards, so the
    # EDF cursor only advances within each card's actual spend window.
    needs.sort(key=lambda n: n.window_end)
    cursor = window_start
    for n in needs:
        # Card can't start receiving spend before its spend_start.
        effective_cursor = max(cursor, n.spend_start)
        days_left = (n.window_end - effective_cursor).days
        if days_left <= 0:
            return SubSpendPlan(feasible=False)
        days_needed = math.ceil(n.min_spend / total_daily)
        if days_needed > days_left:
            return SubSpendPlan(feasible=False)
        cursor = effective_cursor + timedelta(days=days_needed)

    # ---- single card fast path ----
    if len(needs) == 1:
        n = needs[0]
        days_to_earn = math.ceil(n.min_spend / total_daily)
        all_cats = {cat: s for cat, s in spend.items() if s > 0}
        return SubSpendPlan(
            feasible=True,
            parallel=True,
            schedules=[SubCardSchedule(
                card_id=n.card.id,
                start_date=n.spend_start,
                projected_earn_date=n.spend_start + timedelta(days=days_to_earn),
                daily_spend_allocated=total_daily,
                category_allocation=all_cats,
            )],
        )

    # Build currency set from the SUB cards if not provided.
    if wallet_currency_ids is None:
        wallet_currency_ids = {n.card.currency.id for n in needs}

    # ---- 2. attempt EV-optimal parallel category split ----
    # This only works when all required daily rates fit within total_daily —
    # i.e. overlapping SUB windows whose combined need doesn't exceed budget.
    # For staggered windows with no true overlap, the sequential fallback
    # handles it correctly.
    parallel_plan = _try_parallel_category_split(needs, spend, total_daily, wallet_currency_ids)
    if parallel_plan is not None:
        return parallel_plan

    # ---- 3. sequential (EDF) schedule ----
    # The EDF gate already proved this is feasible.  Build the schedule.
    all_cats = {cat: s for cat, s in spend.items() if s > 0}
    cursor = window_start
    schedules: list[SubCardSchedule] = []
    for n in needs:
        effective_cursor = max(cursor, n.spend_start)
        days_needed = math.ceil(n.min_spend / total_daily)
        schedules.append(SubCardSchedule(
            card_id=n.card.id,
            start_date=effective_cursor,
            projected_earn_date=effective_cursor + timedelta(days=days_needed),
            daily_spend_allocated=total_daily,
            category_allocation=all_cats,
        ))
        cursor = effective_cursor + timedelta(days=days_needed)

    return SubSpendPlan(feasible=True, parallel=False, schedules=schedules)


def _try_parallel_category_split(
    needs: list,  # list of _Need (can't type the nested dataclass)
    spend: dict[str, float],
    total_daily: float,
    wallet_currency_ids: set[int],
) -> SubSpendPlan | None:
    """
    Try to split categories among SUB cards so all can be satisfied in parallel.

    Returns a SubSpendPlan if successful, None if the combined required daily
    rates exceed the wallet's total (meaning true parallel isn't possible).
    """
    # Quick check: if sum of required daily rates > total daily, parallel
    # is impossible — cards need more simultaneous spend than exists.
    total_required = sum(n.required_daily for n in needs)
    if total_required > total_daily + 1e-9:
        return None

    # EV-optimal category assignment: each category → best-earning SUB card.
    card_by_id = {n.card.id: n.card for n in needs}
    cat_assignment: dict[str, int] = {}
    for cat, s in spend.items():
        if s <= 0:
            continue
        best_id = needs[0].card.id
        best_rate = -1.0
        for n in needs:
            rate = _card_category_earn_rate(n.card, cat, spend, wallet_currency_ids)
            if rate > best_rate:
                best_rate = rate
                best_id = n.card.id
        cat_assignment[cat] = best_id

    # Build fractional shares: category -> {card_id: annual_$ share}.
    cat_shares: dict[str, dict[int, float]] = {}
    for cat, owner_id in cat_assignment.items():
        cat_shares[cat] = {owner_id: spend[cat]}

    need_by_id = {n.card.id: n for n in needs}

    def _assigned_daily(cid: int) -> float:
        total = 0.0
        for cat, owners in cat_shares.items():
            total += owners.get(cid, 0.0) / 365.0
        return total

    def _donor_surplus(donor_id: int) -> float:
        return _assigned_daily(donor_id) - need_by_id[donor_id].required_daily

    # Urgency rebalancing: walk from most to least urgent, steal categories
    # from cards with surplus to fill shortfalls, picking lowest-EV-cost first.
    for n in needs:
        shortfall_daily = n.required_daily - _assigned_daily(n.card.id)
        if shortfall_daily <= 1e-9:
            continue

        candidates: list[tuple[float, str, int]] = []
        for cat, owners in cat_shares.items():
            for donor_id, donor_share in owners.items():
                if donor_id == n.card.id or donor_share <= 0:
                    continue
                if _donor_surplus(donor_id) <= 1e-9:
                    continue
                donor_rate = _card_category_earn_rate(
                    card_by_id[donor_id], cat, spend, wallet_currency_ids
                )
                my_rate = _card_category_earn_rate(n.card, cat, spend, wallet_currency_ids)
                candidates.append((donor_rate - my_rate, cat, donor_id))

        candidates.sort(key=lambda t: t[0])

        for _, cat, donor_id in candidates:
            if shortfall_daily <= 1e-9:
                break
            surplus = _donor_surplus(donor_id)
            if surplus <= 1e-9:
                continue
            donor_share = cat_shares[cat].get(donor_id, 0.0)
            if donor_share <= 0:
                continue
            take_daily = min(shortfall_daily, surplus, donor_share / 365.0)
            take_annual = take_daily * 365.0
            cat_shares[cat][donor_id] = donor_share - take_annual
            cat_shares[cat][n.card.id] = cat_shares[cat].get(n.card.id, 0.0) + take_annual
            shortfall_daily = n.required_daily - _assigned_daily(n.card.id)

        if _assigned_daily(n.card.id) < n.required_daily - 1e-9:
            return None  # can't satisfy this card even after rebalancing

    # Build schedules from the allocation.
    schedules: list[SubCardSchedule] = []
    for n in needs:
        daily = _assigned_daily(n.card.id)
        cats = {
            cat: share
            for cat, owners in cat_shares.items()
            for cid, share in owners.items()
            if cid == n.card.id and share > 0.01
        }
        days_to_earn = math.ceil(n.min_spend / daily) if daily > 0 else n.remaining_days
        schedules.append(SubCardSchedule(
            card_id=n.card.id,
            start_date=n.spend_start,
            projected_earn_date=n.spend_start + timedelta(days=days_to_earn),
            daily_spend_allocated=daily,
            category_allocation=cats,
        ))

    return SubSpendPlan(feasible=True, parallel=True, schedules=schedules)
