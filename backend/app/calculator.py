"""
Credit card value calculation engine.

Terminology
-----------
- CardData    : all static data for a card, including nested CurrencyData
- CurrencyData: issuer currency with its CPP, transferability, and comparison factor
- spend       : dict of {category: annual_spend_dollars}
- cpp         : cents per point (from the effective currency, accounting for boost)
- SUB         : sign-up bonus
- years       : years_counted
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from typing import Optional

from .constants import ALL_OTHER_CATEGORY
from .date_utils import add_months


# ---------------------------------------------------------------------------
# Data containers (plain dataclasses — no DB dependency)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CreditLine:
    """Statement credit row for calculations (ids match library `card_credits.id`)."""

    library_credit_id: int
    name: str
    value: float


@dataclass
class CurrencyData:
    """Snapshot of a reward currency for use in the calculator engine."""

    id: int
    name: str
    reward_kind: str  # "points" (incl. miles) or "cash"
    cents_per_point: float
    # Default CPP from the currency definition (never overridden by wallet CPP).
    # Used for balance/point-count calculations that should be CPP-independent.
    comparison_cpp: float = 0.0
    cash_transfer_rate: float = 1.0
    partner_transfer_rate: Optional[float] = None
    # When set, this currency upgrades to the target when any wallet card earns the target directly
    converts_to_currency: Optional["CurrencyData"] = None
    # Rate when converting: 1 unit of this = converts_at_rate units of target (default 1.0)
    converts_at_rate: float = 1.0
    # CPP to use when no transfer enabler card is present; None = no reduction
    no_transfer_cpp: Optional[float] = None
    # Multiplier on wallet CPP when no transfer enabler is present (e.g. 0.7 for Citi);
    # takes precedence over no_transfer_cpp when set.
    no_transfer_rate: Optional[float] = None


@dataclass
class CardData:
    """All static data for one card, ready for the calculator engine."""

    id: int
    name: str
    issuer_name: str              # denormalised for display

    # Default currency this card earns
    currency: CurrencyData

    annual_fee: float
    sub: int
    sub_min_spend: Optional[int]
    sub_months: Optional[int]
    sub_spend_earn: int
    annual_bonus: int
    first_year_fee: Optional[float] = None

    # category -> always-on rate per dollar. For additive cards this already
    # includes the base + uncapped additive premiums. For non-additive cards
    # it's the legacy "highest standalone multiplier replaces base" value.
    multipliers: dict[str, float] = field(default_factory=dict)
    # Group metadata tuple:
    #   (multiplier, categories, top_n, group_id, cap_amount, cap_period_months,
    #    is_rotating, rotation_weights, is_additive)
    # - cap_amount:        per-period spend cap in dollars (None = uncapped)
    # - cap_period_months: 1=monthly, 3=quarterly, 6=semi-annual, 12=annual (None = uncapped)
    # - is_rotating:       True for rotating-bonus cards (Discover IT, Chase Freedom Flex).
    #                      Each category gets its own cap sized by its activation
    #                      probability instead of pooling the cap across the group.
    # - rotation_weights:  category_name -> p_C (activation probability in [0, 1]),
    #                      empty when is_rotating is False.
    # - is_additive:       True if the group's multiplier is a *premium* that
    #                      stacks onto the always-on rate for the matching
    #                      category. False (legacy): the multiplier replaces
    #                      the always-on rate when applied.
    multiplier_groups: list[
        tuple[
            float,
            list[str],
            Optional[int],
            Optional[int],
            Optional[float],
            Optional[int],
            bool,
            dict[str, float],
            bool,
        ]
    ] = field(default_factory=list)
    # Manual group category selections: group_id -> set of selected category names (empty/missing = auto-pick by spend)
    group_selected_categories: dict[int, set[str]] = field(default_factory=dict)
    # Per-wallet rotation overrides: (year, quarter) -> set of pinned category names
    # (lowercased for case-insensitive matching). When present, these categories
    # become the only active rotating-bonus categories for that quarter on this
    # card; all other categories in the rotating universe earn at the All Other
    # rate. The cap is the full group cap_amount, pooled across the pinned set.
    rotation_overrides: dict[tuple[int, int], set[str]] = field(default_factory=dict)
    credit_lines: list[CreditLine] = field(default_factory=list)
    # Set of category names where the multiplier only applies via the card's booking portal
    portal_categories: set[str] = field(default_factory=set)
    # Standalone is_portal=True premiums on this card. Each tuple is
    # (category_name_lowercase, premium_value, is_additive). The calculator
    # gates these by `portal_share`: only `share × spend[category]` of the
    # category's segment dollars get the portal premium; the rest fall back
    # to the card's non-portal rate on that category.
    portal_premiums: list[tuple[str, float, bool]] = field(default_factory=list)
    # Per-wallet share of travel-portal spend for this card's issuer (0..1).
    # Set by `apply_wallet_portal_shares` from wallet_portal_shares rows.
    # Default 0 = portal premiums contribute nothing.
    portal_share: float = 0.0
    # True if this card enables partner transfers for its currency (e.g. Sapphire Reserve for UR)
    transfer_enabler: bool = False

    # Wallet-specific date context (None = active for the full calculation window)
    wallet_added_date: Optional[date] = None
    wallet_closed_date: Optional[date] = None
    # sub_projected_earn_date: auto-calculated from spend profile
    sub_projected_earn_date: Optional[date] = None
    # sub_already_earned: True when user has confirmed SUB earned (no projection needed)
    sub_already_earned: bool = False
    # sub_earnable: False when spend rate is too low to hit the SUB min within the SUB window
    sub_earnable: bool = True


@dataclass
class CardResult:
    """Per-card outputs from the calculator, zeroed when card is not selected."""

    card_id: int
    card_name: str
    selected: bool
    # Net annual cost after credits, amortised SUB/fees, and wallet-allocated category earn (at CPP).
    effective_annual_fee: float = 0.0
    total_points: float = 0.0
    annual_point_earn: float = 0.0
    credit_valuation: float = 0.0
    annual_fee: float = 0.0
    first_year_fee: Optional[float] = None
    sub: int = 0
    annual_bonus: int = 0
    sub_extra_spend: float = 0.0
    sub_spend_earn: int = 0
    # Opportunity cost: net dollar value foregone on the rest of the wallet
    # to cover the SUB extra spend (gross opp cost minus sub_spend_earn value)
    sub_opp_cost_dollars: float = 0.0
    # Gross dollar opportunity cost (best alternative earn on the extra spend,
    # before crediting back the sub_spend_earn earned on the target card)
    sub_opp_cost_gross_dollars: float = 0.0
    avg_spend_multiplier: float = 0.0
    cents_per_point: float = 0.0
    # Effective currency name (may differ from default when upgrade is active)
    effective_currency_name: str = ""
    effective_currency_id: int = 0
    effective_reward_kind: str = "points"
    # Per-category earn breakdown: (category_name, annual_points), sorted desc by points
    category_earn: list[tuple[str, float]] = field(default_factory=list)


@dataclass
class WalletResult:
    """Aggregated wallet outputs."""

    years_counted: int
    total_effective_annual_fee: float
    total_points_earned: float
    total_annual_pts: float
    # Sum of projection-period reward units for cash-kind cards only (× cpp/100 = dollars).
    total_cash_reward_dollars: float = 0.0
    # Σ (total_points × cents_per_point / 100) over selected cards — comparable across currencies.
    total_reward_value_usd: float = 0.0
    # currency_name -> total points over the projection period (spend + SUB/bonuses, net of SUB opp cost).
    currency_pts: dict[str, float] = field(default_factory=dict)
    currency_pts_by_id: dict[int, float] = field(default_factory=dict)
    card_results: list[CardResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# SUB spend planning: feasibility check and scheduling
# ---------------------------------------------------------------------------


@dataclass
class SubCardSchedule:
    """Planned SUB targeting for one card."""

    card_id: int
    start_date: date          # when spend begins targeting this card
    projected_earn_date: date  # when the SUB minimum is projected to be met
    daily_spend_allocated: float  # $/day directed to this card
    # Categories assigned to this card for SUB spend (category_name -> annual $).
    # Empty when the card gets the full wallet spend (sequential exclusive phase).
    category_allocation: dict[str, float] = field(default_factory=dict)


@dataclass
class SubSpendPlan:
    """Result of SUB spend feasibility analysis."""

    feasible: bool
    # True when all cards can be satisfied simultaneously (no sequencing needed)
    parallel: bool = False
    schedules: list[SubCardSchedule] = field(default_factory=list)


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
        group_mult, group_cats, top_n, group_id,
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


# ---------------------------------------------------------------------------
# Currency upgrade helpers
# ---------------------------------------------------------------------------


def _wallet_currency_ids(selected_cards: list[CardData]) -> set[int]:
    """IDs of all currencies directly earned by selected cards."""
    return {c.currency.id for c in selected_cards}


def _transfer_enabled_currency_ids(selected_cards: list[CardData]) -> set[int]:
    """IDs of currencies that have a transfer enabler card in the wallet."""
    return {c.currency.id for c in selected_cards if c.transfer_enabler}


def _enabler_model_currency_ids(all_cards: list[CardData]) -> set[int]:
    """IDs of currencies that use the transfer-enabler model.

    A currency uses the enabler model if any card in the library is marked as a
    transfer enabler for it. These currencies fall back to a reduced CPP (rate,
    fixed, or cash) when no enabler is present in the wallet.
    """
    return {c.currency.id for c in all_cards if c.transfer_enabler}


def _adjust_currency_for_transfer(
    cur: CurrencyData,
    transfer_enabled: set[int],
    uses_enabler_model: set[int],
) -> CurrencyData:
    """Return a CurrencyData copy with CPP reduced when no transfer enabler is present.

    When no transfer enabler exists in the wallet, the CPP falls back to the *higher*
    (better) of two options:
    - **Reduced transfer**: a partial transfer access that still beats cash, expressed
      either as ``no_transfer_rate`` (multiplier on the current CPP, e.g. 0.7 for Citi
      without Strata Premier) or ``no_transfer_cpp`` (fixed fallback, e.g. 1.0).
    - **Cash redemption**: ``cash_transfer_rate`` is the cents-per-point achievable by
      cashing out (e.g. 1.0 for Chase UR portal, 0.5 for Capital One cash erase).

    The two are computed independently and the larger value is used. If neither is
    set, the CPP is unchanged.
    """
    new_converts = None
    if cur.converts_to_currency is not None:
        new_converts = _adjust_currency_for_transfer(
            cur.converts_to_currency, transfer_enabled, uses_enabler_model
        )

    has_enabler = cur.id in transfer_enabled
    # A currency uses the enabler model if any card in the library is marked as
    # a transfer enabler for it. Such currencies fall back to a reduced CPP when
    # no enabler is present in the wallet.
    is_enabler_model = cur.id in uses_enabler_model
    if (has_enabler or not is_enabler_model) and new_converts is None:
        return cur

    new_cpp: Optional[float] = None
    new_comparison: Optional[float] = None

    if not has_enabler and is_enabler_model:
        # Build candidate CPPs from each available fallback mechanism, then take
        # the highest (best) value the user could realize without an enabler card.
        candidates_cpp: list[float] = []
        candidates_comparison: list[float] = []

        if cur.no_transfer_rate is not None:
            candidates_cpp.append(cur.cents_per_point * cur.no_transfer_rate)
            candidates_comparison.append(cur.comparison_cpp * cur.no_transfer_rate)
        elif cur.no_transfer_cpp is not None:
            candidates_cpp.append(cur.no_transfer_cpp)
            candidates_comparison.append(cur.no_transfer_cpp)

        # cash_transfer_rate is the cents-per-point you'd get by cashing out.
        if cur.cash_transfer_rate is not None:
            candidates_cpp.append(cur.cash_transfer_rate)
            candidates_comparison.append(cur.cash_transfer_rate)

        best_cpp = max(candidates_cpp)
        best_comparison = max(candidates_comparison)
        # Only adjust if the fallback is actually a reduction.
        if best_cpp < cur.cents_per_point:
            new_cpp = best_cpp
        if best_comparison < cur.comparison_cpp:
            new_comparison = best_comparison

    if new_cpp is None and new_comparison is None and new_converts is None:
        return cur

    kwargs: dict = {}
    if new_converts is not None:
        kwargs["converts_to_currency"] = new_converts
    if new_cpp is not None:
        kwargs["cents_per_point"] = new_cpp
    if new_comparison is not None:
        kwargs["comparison_cpp"] = new_comparison
    return replace(cur, **kwargs)


def _apply_transfer_enabler_cpp(
    cards: list[CardData], selected_cards: list[CardData]
) -> list[CardData]:
    """Return card copies with CPP adjusted when no transfer enabler is present.

    A currency uses the transfer-enabler model if any card in the library is
    marked as ``transfer_enabler``. For such currencies, when no enabler is in
    the selected wallet, the CPP falls back to the best available reduction:
    ``no_transfer_rate`` (rate-based), ``no_transfer_cpp`` (fixed), and/or
    ``cash_transfer_rate`` (cash-out value) — whichever is highest.
    """
    transfer_enabled = _transfer_enabled_currency_ids(selected_cards)
    uses_enabler_model = _enabler_model_currency_ids(cards)
    return [
        replace(
            card,
            currency=_adjust_currency_for_transfer(
                card.currency, transfer_enabled, uses_enabler_model
            ),
        )
        for card in cards
    ]


def _effective_currency(card: CardData, wallet_currency_ids: set[int]) -> CurrencyData:
    """
    Return the currency this card actually earns given the wallet state.
    When this card's currency has a converts_to_currency and the target
    currency is earned directly by any card in the wallet, use the target.
    """
    cur = card.currency
    if cur.converts_to_currency and cur.converts_to_currency.id in wallet_currency_ids:
        return cur.converts_to_currency
    return cur


def _effective_cpp(card: CardData, wallet_currency_ids: set[int]) -> float:
    return _effective_currency(card, wallet_currency_ids).cents_per_point


def _comparison_cpp(card: CardData, wallet_currency_ids: set[int], for_balance: bool = False) -> float:
    """
    CPP used when comparing cards for category allocation.
    Cash should always compete at face value: 1 cent per point/unit.

    When for_balance=True, uses comparison_cpp (default, non-user-overridden CPP) so that
    point totals used for balance display are independent of wallet CPP overrides.
    """
    eff = _effective_currency(card, wallet_currency_ids)
    if for_balance:
        return 1.0 if eff.reward_kind == "cash" else eff.comparison_cpp
    return 1.0 if eff.reward_kind == "cash" else eff.cents_per_point


def _conversion_rate(card: CardData, wallet_currency_ids: set[int]) -> float:
    """Multiplier from card's currency to effective currency (1.0 or converts_at_rate when upgraded)."""
    eff = _effective_currency(card, wallet_currency_ids)
    return card.currency.converts_at_rate if eff.id != card.currency.id else 1.0


def _effective_annual_earn(
    card: CardData, spend: dict[str, float], wallet_currency_ids: set[int]
) -> float:
    """Points earned in the effective currency (raw earn * conversion rate when upgraded)."""
    return calc_annual_point_earn(card, spend) * _conversion_rate(card, wallet_currency_ids)


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

    for_balance: when True, uses default (non-overridden) CPP for scoring so that
    balance point totals are independent of wallet CPP overrides.
    """
    # SUB priority: if any selected cards are in the priority set, only they compete
    candidates = selected_cards
    if sub_priority_card_ids:
        priority = [c for c in selected_cards if c.id in sub_priority_card_ids]
        if priority:
            candidates = priority

    scored: list[tuple[float, CardData]] = []
    for c in candidates:
        m = _multiplier_for_category(c, category, spend)
        cpp = _comparison_cpp(c, wallet_currency_ids, for_balance=for_balance)
        scored.append((m * cpp, c))
    if not scored:
        return []
    best = max(t[0] for t in scored)
    tied = [c for score, c in scored if math.isclose(score, best, rel_tol=0.0, abs_tol=1e-9)]
    tied.sort(key=lambda c: c.id)
    return tied


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
    total = float(card.annual_bonus)
    for cat, s in spend.items():
        if s <= 0:
            continue
        tied = _tied_cards_for_category(selected_cards, spend, cat, wallet_currency_ids, sub_priority_card_ids, for_balance=for_balance)
        if not tied or card.id not in {c.id for c in tied}:
            continue
        n = len(tied)
        m = _multiplier_for_category(card, cat, spend)
        total += (s / n) * m
    return total


def calc_annual_allocated_spend(
    card: CardData,
    selected_cards: list[CardData],
    spend: dict[str, float],
    wallet_currency_ids: set[int],
    sub_priority_card_ids: set[int] | None = None,
) -> float:
    """
    Total annual spend dollars allocated to this card by the category allocation logic.
    Mirrors calc_annual_point_earn_allocated but sums dollars instead of points.
    """
    if len(selected_cards) <= 1:
        return sum(s for s in spend.values() if s > 0)
    total = 0.0
    for cat, s in spend.items():
        if s <= 0:
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
            pts = (s / n) * m
            if pts > 0:
                result.append((cat, round(pts, 2)))
    if card.annual_bonus > 0:
        result.append(("Annual Bonus", float(card.annual_bonus)))
    result.sort(key=lambda x: x[1], reverse=True)
    return result


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
    Mirrors the segment/active-card/SUB-ROS logic used in _time_weighted_annual_earn so
    the breakdown is consistent with annual_point_earn from _segmented_card_net_per_year.
    Points are accumulated as (seg_fraction × per-category-pts) across all segments where
    this card is active.

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
        sub_prio = _sub_priority_ids_for_segment(active, seg_start)
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

    result = [(cat, round(pts, 2)) for cat, pts in cat_totals.items() if pts > 0]
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
    """Like _effective_annual_earn but category spend is wallet-allocated (see above).

    for_balance: when True, uses default (non-overridden) CPP for allocation scoring so
    that point totals used for balance display are independent of wallet CPP overrides.
    """
    return (
        calc_annual_point_earn_allocated(card, selected_cards, spend, wallet_currency_ids, sub_priority_card_ids, for_balance=for_balance)
        * _conversion_rate(card, wallet_currency_ids)
    )


# ---------------------------------------------------------------------------
# Core per-card calculations
# ---------------------------------------------------------------------------


def calc_annual_point_earn(
    card: CardData,
    spend: dict[str, float],
) -> float:
    """Total points earned per year from category spend plus any annual bonus.
    Uses effective multipliers (top-N applied for groups) and All Other fallback.
    """
    cat_pts = sum(
        s * _multiplier_for_category(card, cat, spend)
        for cat, s in spend.items()
        if s > 0
    )
    return float(card.annual_bonus) + cat_pts


def _credit_annual_and_one_time_totals(card: CardData) -> tuple[float, float]:
    """All credits are recurring; one-time bucket is always 0."""
    annual = sum(line.value for line in card.credit_lines)
    return annual, 0.0


def calc_credit_valuation(card: CardData) -> float:
    """Sum of recurring credit dollar values for display."""
    return sum(line.value for line in card.credit_lines)


def calc_sub_extra_spend(
    card: CardData,
    spend: dict[str, float],
) -> float:
    """
    Additional dollars that must be spent to hit the SUB minimum spend,
    beyond what the card earns naturally from its category assignments.
    """
    if not card.sub_min_spend:
        return 0.0
    natural_spend = sum(
        v for cat, v in spend.items() if _multiplier_for_category(card, cat, spend) > 0
    )
    return max(0.0, card.sub_min_spend - natural_spend)


def _best_wallet_earn_rate_dollars(
    card: CardData,
    selected_cards: list[CardData],
    spend: dict[str, float],
    wallet_currency_ids: set[int],
) -> float:
    """
    Spend-weighted best dollar-equivalent earn rate across all other selected
    cards for each category.

    For every category with positive spend, this finds the other card that
    would earn the most in dollar terms (multiplier × cpp).
    Returns a blended rate in $/$ (dollars earned per dollar spent).

    This replaces the old avg-multiplier approach: it is cross-currency aware
    and picks the *best* alternative rather than averaging all of them.
    """
    others = [c for c in selected_cards if c.id != card.id]
    if not others:
        return 0.0

    total_spend = 0.0
    total_best_earn = 0.0

    for cat, s in spend.items():
        if s <= 0:
            continue
        # Best dollar-earn rate for this category among other selected cards
        best_rate = max(
            _multiplier_for_category(c, cat, spend)
            * _comparison_cpp(c, wallet_currency_ids)
            / 100.0
            for c in others
        )
        total_spend += s
        total_best_earn += s * best_rate

    return total_best_earn / total_spend if total_spend > 0 else 0.0


def calc_sub_opportunity_cost(
    card: CardData,
    selected_cards: list[CardData],
    spend: dict[str, float],
    wallet_currency_ids: set[int],
) -> tuple[float, float]:
    """
    Dollar opportunity cost of redirecting extra SUB spend from the rest of
    the wallet to this card.

    Returns (gross_opp_cost_dollars, net_opp_cost_dollars):
      gross = extra_spend × best_wallet_earn_rate
      net   = gross − value_of_sub_spend_earn_on_this_card
              (i.e. what you truly lose after accounting for what the new card
               earns on that same spend)
    """
    if not card.sub_earnable:
        return 0.0, 0.0

    extra_spend = calc_sub_extra_spend(card, spend)
    if extra_spend <= 0:
        return 0.0, 0.0

    best_rate = _best_wallet_earn_rate_dollars(card, selected_cards, spend, wallet_currency_ids)
    gross = extra_spend * best_rate

    # The extra_spend is distributed proportionally across wallet categories,
    # so it earns at the card's spend-weighted average multiplier rate.
    currency = _effective_currency(card, wallet_currency_ids)
    avg_mult = calc_avg_spend_multiplier(card, spend)
    sub_spend_value = extra_spend * avg_mult * currency.cents_per_point / 100.0
    net = max(0.0, gross - sub_spend_value)

    return round(gross, 4), round(net, 4)


def calc_avg_spend_multiplier(
    card: CardData,
    spend: dict[str, float],
) -> float:
    """Spend-weighted average multiplier across categories with positive spend.
    Uses effective multipliers (top-N applied) and All Other fallback.
    """
    effective = _build_effective_multipliers(card, spend)
    all_other = _all_other_multiplier(effective)
    total_spend = 0.0
    total_pts = 0.0
    for cat, s in spend.items():
        mult = effective.get(cat) or all_other
        if s > 0:
            total_spend += s
            total_pts += s * mult
    return total_pts / total_spend if total_spend > 0 else 0.0


def calc_total_points(
    card: CardData,
    selected_cards: list[CardData],
    spend: dict[str, float],
    years: int,
    wallet_currency_ids: set[int],
    precomputed_earn: Optional[float] = None,
) -> float:
    """
    Total raw points over `years` in the effective currency: category earn × years,
    plus one-time sub_spend_earn and SUB bonus.

    Opportunity cost is intentionally excluded — it is a dollar concept tracked
    separately as sub_opp_cost_dollars on CardResult. Including it here would make
    the currency balance sensitive to CPP (the dollars-to-points conversion changes
    whenever the user adjusts CPP, producing incorrect raw point totals).

    precomputed_earn: if provided, used in place of _effective_annual_earn_allocated
    (e.g. already time-weighted by the segmented calculation in compute_wallet).
    """
    effective_earn = (
        precomputed_earn
        if precomputed_earn is not None
        else _effective_annual_earn_allocated(card, spend, selected_cards, wallet_currency_ids, for_balance=True)
    )
    rate = _conversion_rate(card, wallet_currency_ids)
    # When the SUB is not earnable, exclude the SUB bonus and its earn contribution
    effective_sub = (card.sub_spend_earn * rate) if card.sub_earnable else 0.0
    effective_sub_pts = card.sub if card.sub_earnable else 0
    return (
        effective_earn * years
        + effective_sub
        + effective_sub_pts
    )


def _average_annual_net_dollars(
    card: CardData,
    spend: dict[str, float],
    years: int,
    wallet_currency_ids: set[int],
    selected_cards: list[CardData],
    precomputed_earn: Optional[float] = None,
) -> float:
    """
    Average annual net dollar benefit over `years`, amortising SUB and first-year fee.

    Category spend is wallet-allocated (each category goes to best m×CPP card(s);
    ties split dollars evenly among tied cards).

    effective_earn already includes card.annual_bonus (from _effective_annual_earn_allocated),
    so the annual bonus is naturally amortised over `years` via the earn × years term.

    precomputed_earn: if provided, used in place of _effective_annual_earn_allocated.

    Formula:
      ( effective_earn * cpp / 100 * years
        + sub_spend_pts * cpp / 100
        + sub_pts * cpp / 100
        + annual_credits * years + one_time_credits
        - fee
      ) / years
    """
    currency = _effective_currency(card, wallet_currency_ids)
    cpp = currency.cents_per_point
    effective_earn = (
        precomputed_earn
        if precomputed_earn is not None
        else _effective_annual_earn_allocated(card, spend, selected_cards, wallet_currency_ids)
    )
    annual_credits, one_time_credits = _credit_annual_and_one_time_totals(card)

    rate = _conversion_rate(card, wallet_currency_ids)
    # When the SUB is not earnable, exclude the SUB bonus and its earn contribution
    effective_sub = (card.sub_spend_earn * rate) if card.sub_earnable else 0.0
    effective_sub_pts = card.sub if card.sub_earnable else 0
    fee_y1 = card.first_year_fee if card.first_year_fee is not None else card.annual_fee
    total_fees = fee_y1 + (years - 1) * card.annual_fee
    # effective_earn (from _effective_annual_earn_allocated) already includes card.annual_bonus,
    # so it is counted correctly via the years multiplier above.
    # effective_sub and effective_sub_pts are one-time earns; placing them outside the
    # * years term means they are amortised by the outer / years (i.e. counted once total).
    # (for cash cards cpp=1, so * cpp / 100 is the same as / 100).
    value = (
        (effective_earn / 100 * cpp) * years
        + effective_sub / 100 * cpp
        + effective_sub_pts * cpp / 100
        + annual_credits * years
        + one_time_credits
        - total_fees
    ) / years
    return value


# ---------------------------------------------------------------------------
# Segment-based earn helpers (per-day optimisation)
# ---------------------------------------------------------------------------



def _calendar_quarter(d: date) -> tuple[int, int]:
    """Return (year, quarter) for the calendar quarter containing date d.
    Quarter is 1..4. Used by rotation overrides to look up pinned categories."""
    return (d.year, (d.month - 1) // 3 + 1)


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

    - **Rotating capped group (Discover IT, Chase Freedom Flex):** the cap is
      treated as one-per-category-per-period, sized to `cap × p_C` where p_C
      is the historical activation probability. Categories with p_C = 0
      (never historically active) receive no bonus rate. There is no pooling
      across categories within the rotating group: a quarter where Restaurants
      is the active category does not consume Gas's expected cap.

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
    # group_id -> (group_mult, cap_amount, cap_months, is_rotating, rot_weights)
    # group_id -> (g_mult, g_cap_amt, g_cap_months, is_rotating, rot_weights_lower, is_additive)
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

    # Per-segment rotation override lookup. When the focal card has a pinned
    # set of categories for the calendar quarter containing this segment, the
    # rotating branch switches from per-category historical weights to a
    # pooled cap restricted to the override set.
    seg_year, seg_quarter = _calendar_quarter(seg_start)
    override_for_quarter: set[str] | None = card.rotation_overrides.get(
        (seg_year, seg_quarter)
    )

    # Pass 1: walk every spend category, classify, and stash results we'll
    # finalize in pass 2 (so non-rotating pooled groups can split the cap
    # proportionally across all contributing categories).
    out: dict[str, float] = {}
    # group_id -> list of (cat_name, seg_alloc_dollars, group_mult, cat_mult, is_additive)
    # for pooled groups (also used for rotating-with-override since override pools the cap).
    # cat_mult is the always-on rate for that category on this card (already includes
    # uncapped additive premiums); is_additive comes from the group.
    pooled_pending: dict[int, list[tuple[str, float, float, float, bool]]] = {}
    # group_id -> "rotating-override" marker so pass 2 uses the right cap_state key prefix
    rotating_override_groups: set[int] = set()

    for cat, s in spend.items():
        if s <= 0:
            continue

        if len(active_cards) <= 1:
            allocated_annual = s
        else:
            tied = _tied_cards_for_category(
                active_cards, spend, cat, seg_currency_ids,
                sub_priority_card_ids, for_balance=for_balance,
            )
            if not tied or card.id not in {c.id for c in tied}:
                continue
            allocated_annual = s / len(tied)

        seg_alloc_dollars = allocated_annual * seg_years
        cat_mult = _multiplier_for_category(card, cat, spend)
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

        # For non-additive groups: when top-N has demoted this category to
        # the All Other rate, the bonus path doesn't apply at all.
        if not is_additive and cat_mult <= all_other + 1e-9:
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
            if override_for_quarter is not None:
                # User pinned the active categories for this quarter. The cap
                # becomes a pooled cap across the override set; categories
                # not in the override get the always-on rate. Pinned categories
                # share the full group cap (proportional split in pass 2).
                if cat_lower in override_for_quarter:
                    rotating_override_groups.add(gid)
                    pooled_pending.setdefault(gid, []).append(
                        (cat, seg_alloc_dollars, g_mult, cat_mult, is_additive)
                    )
                else:
                    pts = seg_alloc_dollars * overflow_rate
                    if pts > 0:
                        out[cat] = out.get(cat, 0.0) + pts
                continue

            # No override → per-category cap sized by historical activation probability.
            p_c = rot_weights.get(cat_lower, 0.0)
            if p_c <= 0.0:
                # Category is in the rotating universe but has never been
                # active in our recorded history → no bonus rate.
                pts = seg_alloc_dollars * overflow_rate
                if pts > 0:
                    out[cat] = out.get(cat, 0.0) + pts
                continue
            cat_period_cap = g_cap_amt * p_c
            key = ("rot", gid, period_start, cat_lower)
            if key not in cap_state:
                cap_state[key] = cat_period_cap
            remaining = cap_state[key]
            bonus_dollars = min(seg_alloc_dollars, remaining)
            overflow_dollars = seg_alloc_dollars - bonus_dollars
            cap_state[key] = remaining - bonus_dollars
            pts = bonus_dollars * bonus_rate + overflow_dollars * overflow_rate
            if pts > 0:
                out[cat] = out.get(cat, 0.0) + pts
            continue

        # Non-rotating pooled cap: stash for proportional finalization in pass 2.
        pooled_pending.setdefault(gid, []).append(
            (cat, seg_alloc_dollars, g_mult, cat_mult, is_additive)
        )

    # Pass 2: finalize pooled groups (non-rotating, or rotating-with-override),
    # splitting the remaining cap proportionally to each category's
    # seg-allocated spend.
    for gid, items in pooled_pending.items():
        g_mult, g_cap_amt, g_cap_months, _is_rot, _rot, g_is_add = capped_groups[gid]
        period_start, _ = _cap_period_bounds(seg_start, g_cap_months)
        # Use a separate key prefix for override-driven pooling so the
        # quarter (year, quarter) becomes part of the key — different
        # quarters with different overrides each get their own cap budget.
        if gid in rotating_override_groups:
            key = ("rot_override", gid, seg_year, seg_quarter)
        else:
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
# Optimal allocation LP — solves one segment at a time, mutates cap_state.
# ---------------------------------------------------------------------------


def _solve_segment_allocation_lp(
    active_cards: list[CardData],
    spend: dict[str, float],
    seg_currency_ids: set[int],
    sub_priority_card_ids: set[int] | None,
    seg_days: int,
    seg_start: date,
    cap_state: dict[tuple, float],
    for_balance: bool = False,
) -> dict[int, dict[str, float]]:
    """
    Optimally allocate one segment's spend across the active cards using
    scipy.linprog. Honors:
      - per-category flow conservation (Σ_k allocated = segment_dollars)
      - pooled cap constraints on non-rotating capped groups
      - per-category cap constraints on rotating groups (cap × p_C)
      - rotating overrides (pooled cap restricted to pinned categories
        in that calendar quarter)
      - SUB priority filtering (when SUB-priority cards are present, they
        are the only candidates)
      - segment-prorated cap budgets that flow forward via cap_state

    Returns ``{card_id: {category_name: segment_points_raw_currency}}``.
    Mutates cap_state to record cap consumption for downstream segments.

    Falls back to a per-card greedy via ``_segment_card_earn_pts_per_cat``
    if scipy isn't available or the LP solve fails.
    """
    if seg_days <= 0 or not active_cards:
        return {c.id: {} for c in active_cards}
    seg_years = seg_days / 365.25

    # SUB-priority filter: if any priority cards are active in this segment,
    # only they compete for category allocation (matches the existing
    # _tied_cards_for_category logic).
    competing = active_cards
    if sub_priority_card_ids:
        priority = [c for c in active_cards if c.id in sub_priority_card_ids]
        if priority:
            competing = priority

    # Effective per-card multipliers and CPPs.
    card_mult: dict[int, dict[str, float]] = {}  # card_idx -> cat_lower -> mult
    card_all_other: dict[int, float] = {}
    card_cpp: dict[int, float] = {}
    for k_idx, c in enumerate(competing):
        eff_mults = _build_effective_multipliers(c, spend)
        # Lowercase keys for case-insensitive matching against spend keys
        card_mult[k_idx] = {(k or "").strip().lower(): v for k, v in eff_mults.items()}
        card_all_other[k_idx] = _all_other_multiplier(eff_mults)
        card_cpp[k_idx] = _comparison_cpp(c, seg_currency_ids, for_balance=for_balance)

    # Categories with positive segment spend.
    seg_year, seg_quarter = _calendar_quarter(seg_start)
    cat_dollars: list[tuple[str, float]] = []
    for cat, s in spend.items():
        if s > 0:
            cat_dollars.append((cat, s * seg_years))
    if not cat_dollars:
        return {c.id: {} for c in active_cards}

    # ---- Build cap constraints. ----
    # Each constraint: list of (k_idx, cat_lower) with bonus var in this row,
    # plus cap_remaining (derived from cap_state) and the state_key to update.
    @dataclass
    class _CapConstraint:
        members: list[tuple[int, str]]  # (k_idx, cat_lower) for variables in this row
        remaining: float
        state_key: tuple

    constraints: list[_CapConstraint] = []
    # Track per-(k_idx, cat_lower) the BONUS multiplier when capped, for the
    # variable's coefficient in the objective. Categories without entries here
    # only have a base variable (no bonus path).
    bonus_mult: dict[tuple[int, str], float] = {}
    # Variables that are explicitly capped — every (k_idx, cat_lower) pair
    # the LP needs a separate `b` variable for. Pairs not in this set have
    # only a base variable (their entire allocation earns at base rate).
    capped_pairs: set[tuple[int, str]] = set()
    # For each (k_idx, cat_lower) pair with a bonus path, whether the bonus
    # is additive (stacks on the always-on rate) or replacement (the legacy
    # "highest rate wins" model). Determines whether the BASE variable for
    # that pair earns at the always-on rate (additive) or at the card's All
    # Other (non-additive) — i.e., what overflow above the cap looks like.
    pair_is_additive: dict[tuple[int, str], bool] = {}

    def _bonus_rate_for_pair(k_idx: int, cl: str, g_mult: float, g_is_add: bool) -> float:
        """Effective bonus rate when this group's cap applies. For additive
        groups the premium stacks onto the always-on rate; for non-additive
        groups the group multiplier replaces the base entirely."""
        if g_is_add:
            return card_mult[k_idx].get(cl, card_all_other[k_idx]) + g_mult
        return g_mult

    # ---- Portal premiums (Phase B). ----
    # Each (card, category) with an is_portal=True premium produces a
    # per-segment cap constraint with cap = share × seg_alloc_dollars[cat].
    # The constraint state_key includes the segment date so it never carries
    # across segments (portal shares are per-quarter intent, not cumulative).
    # We add these constraints AFTER per-category seg_alloc is known, so we
    # process them in a second pass below.
    portal_constraint_specs: list[tuple[int, str, float, bool]] = []
    for k_idx, c in enumerate(competing):
        if c.portal_share <= 0.0 or not c.portal_premiums:
            continue
        for cat_lower, premium, p_is_add in c.portal_premiums:
            portal_constraint_specs.append((k_idx, cat_lower, float(premium), bool(p_is_add)))

    for k_idx, c in enumerate(competing):
        for (
            g_mult, g_cats, _topn, g_id,
            g_cap_amt, g_cap_months, g_is_rot, g_rot_weights, g_is_add,
        ) in c.multiplier_groups:
            if g_id is None or g_cap_amt is None or not g_cap_months or g_cap_months <= 0:
                continue
            period_start, _ = _cap_period_bounds(seg_start, g_cap_months)
            cat_lower_set = {(x or "").strip().lower() for x in g_cats}

            override = c.rotation_overrides.get((seg_year, seg_quarter)) if g_is_rot else None

            if g_is_rot and override is not None:
                # Pooled cap restricted to override categories for this quarter.
                state_key = ("rot_override", g_id, seg_year, seg_quarter)
                if state_key not in cap_state:
                    cap_state[state_key] = float(g_cap_amt)
                members: list[tuple[int, str]] = []
                for cl in override:
                    if cl in cat_lower_set:
                        members.append((k_idx, cl))
                        bonus_mult[(k_idx, cl)] = _bonus_rate_for_pair(k_idx, cl, float(g_mult), g_is_add)
                        pair_is_additive[(k_idx, cl)] = g_is_add
                        capped_pairs.add((k_idx, cl))
                if members and cap_state[state_key] > 0:
                    constraints.append(_CapConstraint(
                        members=members,
                        remaining=cap_state[state_key],
                        state_key=state_key,
                    ))
            elif g_is_rot:
                # Per-category caps sized by historical activation probability.
                rot_lookup = {(k or "").strip().lower(): float(v) for k, v in g_rot_weights.items()}
                for cl in cat_lower_set:
                    p_c = rot_lookup.get(cl, 0.0)
                    if p_c <= 0.0:
                        # No bonus path for this category; it earns base only.
                        continue
                    state_key = ("rot", g_id, period_start, cl)
                    if state_key not in cap_state:
                        cap_state[state_key] = float(g_cap_amt) * p_c
                    bonus_mult[(k_idx, cl)] = _bonus_rate_for_pair(k_idx, cl, float(g_mult), g_is_add)
                    pair_is_additive[(k_idx, cl)] = g_is_add
                    capped_pairs.add((k_idx, cl))
                    if cap_state[state_key] > 0:
                        constraints.append(_CapConstraint(
                            members=[(k_idx, cl)],
                            remaining=cap_state[state_key],
                            state_key=state_key,
                        ))
            else:
                # Pooled non-rotating cap.
                state_key = ("pool", g_id, period_start)
                if state_key not in cap_state:
                    cap_state[state_key] = float(g_cap_amt)
                members = []
                for cl in cat_lower_set:
                    members.append((k_idx, cl))
                    bonus_mult[(k_idx, cl)] = _bonus_rate_for_pair(k_idx, cl, float(g_mult), g_is_add)
                    pair_is_additive[(k_idx, cl)] = g_is_add
                    capped_pairs.add((k_idx, cl))
                if members and cap_state[state_key] > 0:
                    constraints.append(_CapConstraint(
                        members=members,
                        remaining=cap_state[state_key],
                        state_key=state_key,
                    ))

    # ---- Portal premium constraints. ----
    # Each portal premium becomes a per-segment cap = share × seg_dollars[cat].
    # The cap is dynamic (computed from this segment's spend, not stored in
    # cap_state) and never carries across segments. The state_key uses a
    # ("portal", k_idx, cat_lower, seg_start) tuple so multiple cards/cats
    # have distinct entries — but we initialize to the dynamic value each
    # time, so cross-segment carry-forward doesn't matter.
    for spec_k_idx, spec_cl, spec_premium, spec_is_add in portal_constraint_specs:
        # Find the matching category (case-insensitive) in cat_dollars.
        cat_idx_match = None
        cat_seg_dollars = 0.0
        for idx, (cat, d_c) in enumerate(cat_dollars):
            if cat.strip().lower() == spec_cl:
                cat_idx_match = idx
                cat_seg_dollars = d_c
                break
        if cat_idx_match is None or cat_seg_dollars <= 0.0:
            continue
        share = competing[spec_k_idx].portal_share
        portal_cap = share * cat_seg_dollars
        if portal_cap <= 0.0:
            continue
        state_key = ("portal", spec_k_idx, spec_cl, seg_start)
        # Always re-initialize (per-segment, no carry-forward).
        cap_state[state_key] = portal_cap
        # The portal premium uses the same additive/non-additive math as a
        # regular capped group. Override bonus_mult only if no other cap is
        # already set for this pair (avoids stomping on a more aggressive
        # standalone bonus path on the same category).
        rate = _bonus_rate_for_pair(spec_k_idx, spec_cl, spec_premium, spec_is_add)
        existing_bonus = bonus_mult.get((spec_k_idx, spec_cl))
        if existing_bonus is None or rate > existing_bonus:
            bonus_mult[(spec_k_idx, spec_cl)] = rate
            pair_is_additive[(spec_k_idx, spec_cl)] = spec_is_add
        capped_pairs.add((spec_k_idx, spec_cl))
        constraints.append(
            _CapConstraint(
                members=[(spec_k_idx, spec_cl)],
                remaining=portal_cap,
                state_key=state_key,
            )
        )

    # ---- Build LP variables and matrices. ----
    # For each (k_idx, cat_idx) pair we always have a `base` variable (e).
    # If (k_idx, cat_lower) ∈ capped_pairs, we additionally have a `bonus` (b)
    # variable. Variable layout, packed into one flat list:
    #   var[i] = either ("e", k_idx, cat_idx) or ("b", k_idx, cat_idx)
    cat_index: dict[str, int] = {cat: i for i, (cat, _) in enumerate(cat_dollars)}
    var_indices: list[tuple[str, int, int]] = []  # ("e"|"b", k_idx, cat_idx)
    var_lookup: dict[tuple[str, int, int], int] = {}

    def _add_var(kind: str, k_idx: int, cat_idx: int) -> int:
        key = (kind, k_idx, cat_idx)
        if key in var_lookup:
            return var_lookup[key]
        var_lookup[key] = len(var_indices)
        var_indices.append(key)
        return var_lookup[key]

    # Add base variables for every (k_idx, cat_idx).
    for k_idx in range(len(competing)):
        for cat, _d in cat_dollars:
            cat_idx = cat_index[cat]
            _add_var("e", k_idx, cat_idx)
    # Add bonus variables wherever the card has a real bonus path:
    #   (a) the constraint loop marked (k_idx, cat_lower) as capped (i.e.,
    #       this category appears in a capped group on this card), OR
    #   (b) the card's always-on multiplier strictly beats its All Other
    #       (e.g., a standalone non-additive bonus like CSR 3x dining).
    for k_idx in range(len(competing)):
        ao = card_all_other[k_idx]
        for cat, _d in cat_dollars:
            cat_lower = cat.strip().lower()
            cat_idx = cat_index[cat]
            in_capped = (k_idx, cat_lower) in capped_pairs
            mult = card_mult[k_idx].get(cat_lower, ao)
            uncapped_bonus = mult > ao + 1e-9
            if in_capped or uncapped_bonus:
                _add_var("b", k_idx, cat_idx)
                # If not already set (uncapped bonus path), record the multiplier.
                if uncapped_bonus:
                    bonus_mult.setdefault((k_idx, cat_lower), mult)

    n_vars = len(var_indices)
    if n_vars == 0:
        return {c.id: {} for c in active_cards}

    # Objective coefficients: maximize Σ rate × var. linprog minimizes,
    # so we use negative coefficients.
    # For BASE variables (e):
    #   - If the (k, cat) pair has an ADDITIVE bonus path, e represents
    #     spend that gets the always-on rate (which already includes any
    #     uncapped additive premiums baked in by db_helpers — e.g.,
    #     Freedom Flex Restaurants = 1 + 2 = 3x).
    #   - If the pair has a NON-ADDITIVE (legacy) bonus path, e represents
    #     spend that "overflowed" the cap and falls to All Other rate.
    #   - If no bonus path exists, e earns the card's always-on rate for
    #     that category (= `card_mult[k][cat]`, which equals all_other for
    #     unlisted categories).
    # For BONUS variables (b), the rate is `bonus_mult[(k, cl)]` populated by
    # the constraint loop above; for additive groups it's `cat_mult + premium`,
    # for non-additive it's the group multiplier outright.
    obj_c = [0.0] * n_vars
    for i, (kind, k_idx, cat_idx) in enumerate(var_indices):
        cat_name = cat_dollars[cat_idx][0]
        cat_lower = cat_name.strip().lower()
        cpp = card_cpp[k_idx]
        if kind == "e":
            if pair_is_additive.get((k_idx, cat_lower), True) is False:
                # Non-additive bonus path → overflow earns at All Other.
                mult = card_all_other[k_idx]
            else:
                # Additive path or no bonus path: always-on rate (which
                # includes uncapped additive premiums via db_helpers).
                mult = card_mult[k_idx].get(cat_lower, card_all_other[k_idx])
        else:
            mult = bonus_mult.get((k_idx, cat_lower), card_all_other[k_idx])
        # Effective $ earned per $ spent.
        rate = mult * cpp / 100.0
        obj_c[i] = -rate

    # Equality constraints: per category, Σ_k (e + b) = d_C
    n_cats = len(cat_dollars)
    A_eq = [[0.0] * n_vars for _ in range(n_cats)]
    b_eq = [0.0] * n_cats
    for cat_idx, (cat, d_c) in enumerate(cat_dollars):
        b_eq[cat_idx] = d_c
        for k_idx in range(len(competing)):
            i_e = var_lookup[("e", k_idx, cat_idx)]
            A_eq[cat_idx][i_e] = 1.0
            i_b = var_lookup.get(("b", k_idx, cat_idx))
            if i_b is not None:
                A_eq[cat_idx][i_b] = 1.0

    # Inequality constraints: each cap constraint sums its bonus variables.
    A_ub: list[list[float]] = []
    b_ub: list[float] = []
    for cc in constraints:
        row = [0.0] * n_vars
        any_member = False
        for (k_idx, cl) in cc.members:
            # Find the cat_idx whose lowercased name matches cl.
            cat_idx = None
            for idx, (cat, _d) in enumerate(cat_dollars):
                if cat.strip().lower() == cl:
                    cat_idx = idx
                    break
            if cat_idx is None:
                continue
            i_b = var_lookup.get(("b", k_idx, cat_idx))
            if i_b is None:
                continue
            row[i_b] = 1.0
            any_member = True
        if any_member:
            A_ub.append(row)
            b_ub.append(cc.remaining)

    # Variable bounds: 0 ≤ var ≤ d_C (a single category never receives more
    # than its own segment dollars on any one card).
    bounds = []
    for kind, k_idx, cat_idx in var_indices:
        bounds.append((0.0, cat_dollars[cat_idx][1]))

    # Solve.
    try:
        from scipy.optimize import linprog

        # Dense matrices are fine for our small problem sizes.
        res = linprog(
            c=obj_c,
            A_ub=A_ub if A_ub else None,
            b_ub=b_ub if b_ub else None,
            A_eq=A_eq,
            b_eq=b_eq,
            bounds=bounds,
            method="highs",
        )
    except Exception:
        # Solver unavailable / failed: degrade to per-card greedy.
        return _greedy_segment_fallback(
            active_cards, spend, seg_currency_ids, sub_priority_card_ids,
            seg_days, seg_start, cap_state, for_balance,
        )

    if not res.success:
        return _greedy_segment_fallback(
            active_cards, spend, seg_currency_ids, sub_priority_card_ids,
            seg_days, seg_start, cap_state, for_balance,
        )

    # ---- Extract per-(card, category) bonus / base dollars from LP. ----
    # alloc[(k_idx, cat_idx)] = (bonus_dollars, base_dollars)
    alloc: dict[tuple[int, int], list[float]] = {}
    for i, (kind, k_idx, cat_idx) in enumerate(var_indices):
        x = float(res.x[i])
        if x <= 1e-12:
            continue
        slot = alloc.setdefault((k_idx, cat_idx), [0.0, 0.0])
        if kind == "b":
            slot[0] += x
        else:
            slot[1] += x

    # ---- Cosmetic redistribution for pooled constraints. ----
    # The LP can pick degenerate solutions when multiple categories within a
    # pooled group have identical bonus rates (e.g., BCP 6% Groceries +
    # Streaming). The total earn is correct, but the per-category split
    # collapses onto whichever variable the simplex picked first. Redistribute
    # bonus dollars proportionally to each category's segment spend so the
    # category breakdown looks balanced. Per-category constraints (rotating
    # without override) and uncapped bonuses are left untouched.
    for cc in constraints:
        if len(cc.members) <= 1:
            continue
        # Only pooled constraints have multiple members. Build the per-cat
        # info we need: (k_idx, cat_idx, seg_dollars).
        members_with_idx: list[tuple[int, int, float]] = []
        total_bonus = 0.0
        total_spend = 0.0
        for (k_idx, cl) in cc.members:
            cat_idx = None
            for idx, (cat, _d) in enumerate(cat_dollars):
                if cat.strip().lower() == cl:
                    cat_idx = idx
                    break
            if cat_idx is None:
                continue
            slot = alloc.get((k_idx, cat_idx))
            if slot is None:
                continue
            members_with_idx.append((k_idx, cat_idx, slot[0] + slot[1]))
            total_bonus += slot[0]
            total_spend += slot[0] + slot[1]
        if total_bonus <= 0 or total_spend <= 0:
            continue
        for k_idx, cat_idx, cat_total in members_with_idx:
            # Redistribute: each category gets total_bonus × (cat_total/total_spend).
            new_bonus = total_bonus * (cat_total / total_spend)
            new_base = cat_total - new_bonus
            slot = alloc[(k_idx, cat_idx)]
            slot[0] = new_bonus
            slot[1] = new_base

    # ---- Convert to per-card per-category points. ----
    out: dict[int, dict[str, float]] = {c.id: {} for c in active_cards}
    for (k_idx, cat_idx), (b_dol, e_dol) in alloc.items():
        cat_name = cat_dollars[cat_idx][0]
        cat_lower = cat_name.strip().lower()
        # Mirror the LP objective rate logic for consistency.
        bonus_m = bonus_mult.get(
            (k_idx, cat_lower),
            card_mult[k_idx].get(cat_lower, card_all_other[k_idx]),
        )
        if pair_is_additive.get((k_idx, cat_lower), True) is False:
            base_m = card_all_other[k_idx]
        else:
            base_m = card_mult[k_idx].get(cat_lower, card_all_other[k_idx])
        pts = b_dol * bonus_m + e_dol * base_m
        if pts <= 0:
            continue
        card_id = competing[k_idx].id
        out[card_id][cat_name] = out[card_id].get(cat_name, 0.0) + pts

    # ---- Update cap_state with bonus dollars consumed by each constraint. ----
    for cc in constraints:
        consumed = 0.0
        for (k_idx, cl) in cc.members:
            cat_idx = None
            for idx, (cat, _d) in enumerate(cat_dollars):
                if cat.strip().lower() == cl:
                    cat_idx = idx
                    break
            if cat_idx is None:
                continue
            i_b = var_lookup.get(("b", k_idx, cat_idx))
            if i_b is None:
                continue
            consumed += float(res.x[i_b])
        cap_state[cc.state_key] = max(0.0, cc.remaining - consumed)

    return out


def _greedy_segment_fallback(
    active_cards: list[CardData],
    spend: dict[str, float],
    seg_currency_ids: set[int],
    sub_priority_card_ids: set[int] | None,
    seg_days: int,
    seg_start: date,
    cap_state: dict[tuple, float],
    for_balance: bool = False,
) -> dict[int, dict[str, float]]:
    """Per-card greedy fallback when scipy/LP solve fails. Uses the existing
    _segment_card_earn_pts_per_cat path for each card with a SHARED cap_state
    so per-card overflow at least respects prior consumption."""
    out: dict[int, dict[str, float]] = {}
    for c in active_cards:
        out[c.id] = _segment_card_earn_pts_per_cat(
            c, spend, active_cards, seg_currency_ids,
            sub_priority_card_ids, seg_days, seg_start, cap_state, for_balance,
        )
    return out


def _is_sub_active_in_segment(card: CardData, seg_start: date) -> bool:
    """
    Whether this card has an active SUB window at the given segment start.
    True when: card has an earnable SUB, is in its SUB window,
    and the SUB has not yet been earned before this segment starts.
    """
    if (
        not card.sub
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
) -> set[int]:
    """
    Return the set of card IDs that have active SUB windows in this segment.
    These cards get absolute priority in category allocation.
    """
    return {c.id for c in active_cards if _is_sub_active_in_segment(c, seg_start)}


def _time_weighted_annual_earn(
    card: CardData,
    selected_cards: list[CardData],
    spend: dict[str, float],
    wallet_currency_ids: set[int],
    window_start: date,
    window_end: date,
    for_balance: bool = False,
) -> float:
    """
    Time-weighted annual earn for `card` across the calculation window.

    For each segment, the active card set and SUB priority may differ.
    Cards only contribute earn for segments where they are active.

    for_balance: when True, uses default (non-overridden) CPP for allocation scoring so
    that point totals used for balance display are CPP-independent.
    """
    total_days = (window_end - window_start).days
    if total_days <= 0:
        return _effective_annual_earn_allocated(card, spend, selected_cards, wallet_currency_ids, for_balance=for_balance)

    segments = _build_segments(window_start, window_end, selected_cards)
    weighted = 0.0
    for seg_start, seg_end, active in segments:
        if card not in active:
            continue
        seg_fraction = (seg_end - seg_start).days / total_days
        seg_currency_ids = {c.currency.id for c in active}
        sub_prio = _sub_priority_ids_for_segment(active, seg_start)
        earn = _effective_annual_earn_allocated(
            card, spend, active, seg_currency_ids, sub_priority_card_ids=sub_prio, for_balance=for_balance
        )
        weighted += earn * seg_fraction
    return weighted


# ---------------------------------------------------------------------------
# Segment-based per-card net value
# ---------------------------------------------------------------------------


def _segmented_card_net_per_year(
    card: CardData,
    selected_cards: list[CardData],
    spend: dict[str, float],
    window_start: date,
    window_end: date,
    precomputed_seg_alloc: list[dict[int, dict[str, float]]] | None = None,
    precomputed_seg_alloc_balance: list[dict[int, dict[str, float]]] | None = None,
) -> tuple[float, float, float]:
    """
    Returns (average_annual_net_dollars, annualized_point_earn, annualized_point_earn_for_balance)
    for `card` using true daily proration over [window_start, window_end).

    - Earn and annual credits: accumulated per segment × (seg_days / 365.25)
    - Fees: prorated by the card's actual active days in the window
      (first-year fee for the first 12 months from wallet_added_date, annual
      fee for the rest)
    - One-time credits: added once if card is active at any point
    - SUB value and sub_spend_earn: one-time dollar additions
    - SUB opportunity cost: one-time deduction
    Everything is divided by total_years to give the average annual figure.

    annualized_point_earn uses wallet CPP for allocation (for EV display).
    annualized_point_earn_for_balance uses default CPP for allocation so that
    balance/point totals are independent of wallet CPP overrides.

    precomputed_seg_alloc / precomputed_seg_alloc_balance: optional pre-solved
    per-segment allocations from compute_wallet's LP optimizer. When provided,
    the inner segment loop reads {card_id: {category: pts}} from the cache
    instead of running the per-card greedy. The cache must be aligned to the
    segment list returned by `_build_segments(window_start, window_end, selected_cards)`.
    """
    total_days = (window_end - window_start).days
    if total_days <= 0:
        wallet_currency_ids = _wallet_currency_ids(selected_cards)
        earn = _effective_annual_earn_allocated(
            card, spend, selected_cards, wallet_currency_ids
        )
        earn_for_balance = _effective_annual_earn_allocated(
            card, spend, selected_cards, wallet_currency_ids, for_balance=True
        )
        net = _average_annual_net_dollars(
            card, spend, 1, wallet_currency_ids, selected_cards, precomputed_earn=earn
        )
        return net, earn, earn_for_balance

    total_years = total_days / 365.25
    active_wallet_currency_ids = _wallet_currency_ids(selected_cards)
    segments = _build_segments(window_start, window_end, selected_cards)

    total_earn_dollars = 0.0
    annualized_earn_pts = 0.0
    annualized_earn_pts_for_balance = 0.0
    total_credits = 0.0
    card_ever_active = False

    # When no precomputed cache is supplied (e.g. tests calling this directly),
    # fall back to per-card greedy with local cap state. Two separate states
    # because wallet-CPP and balance-CPP can pick different winning cards.
    local_cap_state: dict[tuple, float] = {}
    local_cap_state_balance: dict[tuple, float] = {}
    conv_rate = _conversion_rate(card, active_wallet_currency_ids)

    for seg_idx, (seg_start, seg_end, active) in enumerate(segments):
        if card not in active:
            continue
        card_ever_active = True
        seg_days = (seg_end - seg_start).days
        seg_currency_ids = {c.currency.id for c in active}
        sub_prio = _sub_priority_ids_for_segment(active, seg_start)

        if precomputed_seg_alloc is not None:
            cat_pts = precomputed_seg_alloc[seg_idx].get(card.id, {})
        else:
            cat_pts = _segment_card_earn_pts_per_cat(
                card, spend, active, seg_currency_ids, sub_prio,
                seg_days, seg_start, local_cap_state,
            )
        if precomputed_seg_alloc_balance is not None:
            cat_pts_balance = precomputed_seg_alloc_balance[seg_idx].get(card.id, {})
        else:
            cat_pts_balance = _segment_card_earn_pts_per_cat(
                card, spend, active, seg_currency_ids, sub_prio,
                seg_days, seg_start, local_cap_state_balance, for_balance=True,
            )
        seg_years = seg_days / 365.25
        # Annual bonus is uniform per year — prorate to segment.
        seg_pts_raw = sum(cat_pts.values()) + float(card.annual_bonus) * seg_years
        seg_pts_raw_balance = sum(cat_pts_balance.values()) + float(card.annual_bonus) * seg_years
        seg_pts = seg_pts_raw * conv_rate
        seg_pts_balance = seg_pts_raw_balance * conv_rate

        eff_currency = _effective_currency(card, seg_currency_ids)
        total_earn_dollars += seg_pts * eff_currency.cents_per_point / 100.0
        annualized_earn_pts += seg_pts * 365.25 / total_days
        annualized_earn_pts_for_balance += seg_pts_balance * 365.25 / total_days

        annual_credits, _ = _credit_annual_and_one_time_totals(card)
        total_credits += annual_credits * seg_days / 365.25

    # One-time credits
    _, one_time_credits = _credit_annual_and_one_time_totals(card)
    if card_ever_active:
        total_credits += one_time_credits

    # SUB: one-time bonus value only.
    # sub_spend_earn and opportunity cost are deliberately excluded here:
    # the SUB ROS boost in the segment earn already redirects spend to this card
    # during its SUB window (captured in total_earn_dollars above), so adding
    # sub_spend_earn would double-count those points, and subtracting net_opp
    # would double-count the cost already reflected in other cards' reduced
    # segment earn.
    if card.sub_earnable and card.sub:
        earned = card.sub_projected_earn_date
        if earned is None or window_start <= earned <= window_end:
            eff_currency = _effective_currency(card, active_wallet_currency_ids)
            total_earn_dollars += card.sub * eff_currency.cents_per_point / 100.0

    # Fees: prorated by card's actual active days in the window
    card_start_in_window = max(card.wallet_added_date or window_start, window_start)
    card_end_in_window = min(card.wallet_closed_date or window_end, window_end)
    active_days = max(0, (card_end_in_window - card_start_in_window).days)

    if card.first_year_fee is not None and card.wallet_added_date is not None:
        first_year_end = add_months(card.wallet_added_date, 12)
        first_year_overlap = max(0, (
            min(first_year_end, card_end_in_window) - max(card.wallet_added_date, card_start_in_window)
        ).days)
        rest_days = max(0, active_days - first_year_overlap)
        total_fee = (
            card.first_year_fee / 365.25 * first_year_overlap
            + card.annual_fee / 365.25 * rest_days
        )
    else:
        fee = card.annual_fee if card.annual_fee is not None else 0.0
        total_fee = fee / 365.25 * active_days

    total_net = total_earn_dollars + total_credits - total_fee
    return total_net / total_years, annualized_earn_pts, annualized_earn_pts_for_balance


# ---------------------------------------------------------------------------
# Wallet-level aggregation
# ---------------------------------------------------------------------------


def compute_wallet(
    all_cards: list[CardData],
    selected_ids: set[int],
    spend: dict[str, float],
    years: int,
    window_start: Optional[date] = None,
    window_end: Optional[date] = None,
    sub_priority_card_ids: set[int] | None = None,
) -> WalletResult:
    """
    Compute results for every card in `all_cards`.
    Only cards with id in `selected_ids` contribute to totals and currency points.

    window_start / window_end: when provided and any selected card has date info,
    the earn calculation is time-weighted across segments based on card open/close
    and SUB earn boundaries (per-day optimisation).
    """
    selected_cards = [c for c in all_cards if c.id in selected_ids]

    # Adjust CPP for currencies that lack a transfer enabler in the wallet.
    all_cards = _apply_transfer_enabler_cpp(all_cards, selected_cards)
    selected_cards = [c for c in all_cards if c.id in selected_ids]

    active_wallet_currency_ids = _wallet_currency_ids(selected_cards)

    # Use segmented calculation when window dates are available and either:
    #   (a) any card has date context (open/close), or
    #   (b) any card has a capped multiplier group — caps need per-period
    #       segmentation to enforce, so the simple path can't model them.
    def _has_capped_group(c: CardData) -> bool:
        if any(
            cap_amt is not None and cap_months and cap_months > 0
            for _m, _cats, _topn, _gid, cap_amt, cap_months, _is_rot, _rot_weights, _is_add in c.multiplier_groups
        ):
            return True
        # A card with portal premiums and a non-zero portal share also needs
        # the segmented LP path so the per-segment portal cap can apply.
        if c.portal_share > 0.0 and c.portal_premiums:
            return True
        return False

    use_segmentation = (
        window_start is not None
        and window_end is not None
        and (
            any(
                c.wallet_added_date is not None or c.wallet_closed_date is not None
                for c in selected_cards
            )
            or any(_has_capped_group(c) for c in selected_cards)
        )
    )

    # When the segmented path is in play, pre-solve the optimal cross-card
    # allocation for every segment ONCE — both for wallet-CPP scoring (used
    # by EV) and balance-CPP scoring (used by point totals). Each card then
    # reads its own allocation out of the cache. cap_state mutates forward
    # in time as segments consume cap budgets within the same period.
    seg_alloc_cache: list[dict[int, dict[str, float]]] | None = None
    seg_alloc_cache_balance: list[dict[int, dict[str, float]]] | None = None
    if use_segmentation and window_start is not None and window_end is not None:
        segments_for_cache = _build_segments(window_start, window_end, selected_cards)
        seg_alloc_cache = []
        seg_alloc_cache_balance = []
        cap_state_lp: dict[tuple, float] = {}
        cap_state_lp_balance: dict[tuple, float] = {}
        for seg_start, seg_end, active in segments_for_cache:
            seg_days = (seg_end - seg_start).days
            seg_currency_ids = {c.currency.id for c in active}
            sub_prio = _sub_priority_ids_for_segment(active, seg_start)
            seg_alloc_cache.append(
                _solve_segment_allocation_lp(
                    active, spend, seg_currency_ids, sub_prio,
                    seg_days, seg_start, cap_state_lp, for_balance=False,
                )
            )
            seg_alloc_cache_balance.append(
                _solve_segment_allocation_lp(
                    active, spend, seg_currency_ids, sub_prio,
                    seg_days, seg_start, cap_state_lp_balance, for_balance=True,
                )
            )

    card_results: list[CardResult] = []

    for card in all_cards:
        selected = card.id in selected_ids

        if not selected:
            card_results.append(
                CardResult(
                    card_id=card.id,
                    card_name=card.name,
                    selected=False,
                    annual_fee=card.annual_fee,
                    first_year_fee=card.first_year_fee,
                    sub=card.sub,
                    cents_per_point=card.currency.cents_per_point,
                    effective_currency_name=card.currency.name,
                    effective_currency_id=card.currency.id,
                    effective_reward_kind=card.currency.reward_kind,
                )
            )
            continue

        eff_currency = _effective_currency(card, active_wallet_currency_ids)

        if use_segmentation:
            net_annual, annual_point_earn, annual_point_earn_for_balance = _segmented_card_net_per_year(
                card, selected_cards, spend,
                window_start, window_end,  # type: ignore[arg-type]
                precomputed_seg_alloc=seg_alloc_cache,
                precomputed_seg_alloc_balance=seg_alloc_cache_balance,
            )
            effective_annual_fee = round(-net_annual, 4)
            # total_points: annualized earn (default CPP) × total window years + one-time SUB bonus.
            # Uses for_balance earn so point totals are independent of wallet CPP overrides.
            # sub_spend_earn and net_opp are excluded (already captured in segment earn).
            total_years_window = (window_end - window_start).days / 365.25  # type: ignore[operator]
            sub_earnable_pts = card.sub if card.sub_earnable else 0
            total_points = annual_point_earn_for_balance * total_years_window + sub_earnable_pts
        else:
            annual_point_earn = _effective_annual_earn_allocated(
                card, spend, selected_cards, active_wallet_currency_ids,
                sub_priority_card_ids=sub_priority_card_ids,
            )
            annual_point_earn_for_balance = _effective_annual_earn_allocated(
                card, spend, selected_cards, active_wallet_currency_ids,
                sub_priority_card_ids=sub_priority_card_ids, for_balance=True,
            )
            net_annual = _average_annual_net_dollars(
                card, spend, years, active_wallet_currency_ids, selected_cards,
                precomputed_earn=annual_point_earn,
            )
            effective_annual_fee = round(-net_annual, 4)
            total_points = calc_total_points(
                card, selected_cards, spend, years, active_wallet_currency_ids,
                precomputed_earn=annual_point_earn_for_balance,
            )
        credit_val = calc_credit_valuation(card)
        sub_extra = calc_sub_extra_spend(card, spend)
        gross_opp, net_opp = calc_sub_opportunity_cost(card, selected_cards, spend, active_wallet_currency_ids)
        avg_mult = calc_avg_spend_multiplier(card, spend)
        if use_segmentation:
            # Time-weighted breakdown: reads from the same per-segment LP cache
            # the EV path used so categories match annual_point_earn exactly.
            cat_earn = _segmented_category_earn_breakdown(
                card, selected_cards, spend, window_start, window_end,  # type: ignore[arg-type]
                precomputed_seg_alloc=seg_alloc_cache,
            )
        else:
            cat_earn = calc_category_earn_breakdown(
                card, selected_cards, spend, active_wallet_currency_ids,
                sub_priority_card_ids=sub_priority_card_ids,
            )
            # sub_spend_earn is a separate one-time contribution not captured in annual_point_earn
            # on the simple path; add it explicitly. On the segmented path it is already embedded
            # in segment earn via SUB priority allocation.
            if card.sub_earnable and card.sub_spend_earn > 0:
                cat_earn = list(cat_earn) + [("SUB Spend", float(card.sub_spend_earn))]
                cat_earn.sort(key=lambda x: x[1], reverse=True)

        # Surface only the SUB values that were actually counted in totals.
        # When sub_earnable is False (e.g. in-wallet cards whose SUB is historical
        # or cards the user can't reach the min spend on), the calculator already
        # excluded these from total_points and effective_annual_fee — reporting
        # the raw library values here would let the UI double-subtract them.
        reported_sub = card.sub if card.sub_earnable else 0
        reported_sub_spend_earn = card.sub_spend_earn if card.sub_earnable else 0
        card_results.append(
            CardResult(
                card_id=card.id,
                card_name=card.name,
                selected=True,
                effective_annual_fee=effective_annual_fee,
                total_points=round(total_points, 2),
                annual_point_earn=round(annual_point_earn, 2),
                credit_valuation=round(credit_val, 2),
                annual_fee=card.annual_fee,
                first_year_fee=card.first_year_fee,
                sub=reported_sub,
                annual_bonus=card.annual_bonus,
                sub_extra_spend=round(sub_extra, 2),
                sub_spend_earn=reported_sub_spend_earn,
                sub_opp_cost_dollars=net_opp,
                sub_opp_cost_gross_dollars=gross_opp,
                avg_spend_multiplier=round(avg_mult, 4),
                cents_per_point=eff_currency.cents_per_point,
                effective_currency_name=eff_currency.name,
                effective_currency_id=eff_currency.id,
                effective_reward_kind=eff_currency.reward_kind,
                category_earn=cat_earn,
            )
        )

    selected_results = [r for r in card_results if r.selected]
    total_effective_annual_fee = round(
        sum(r.effective_annual_fee for r in selected_results), 4
    )
    points_only = [r for r in selected_results if r.effective_reward_kind != "cash"]
    cash_only = [r for r in selected_results if r.effective_reward_kind == "cash"]
    total_points_earned = round(sum(r.total_points for r in points_only), 2)
    total_annual_pts = round(sum(r.annual_point_earn for r in points_only), 2)
    total_cash_reward_dollars = round(
        sum(r.total_points * r.cents_per_point / 100.0 for r in cash_only), 4
    )
    total_reward_value_usd = round(
        sum(r.total_points * r.cents_per_point / 100.0 for r in selected_results), 4
    )

    # Total raw points over the projection period, by effective currency (spend + SUB + bonuses)
    currency_pts: dict[str, float] = {}
    currency_pts_by_id: dict[int, float] = {}
    for r in selected_results:
        name = (r.effective_currency_name or "").strip()
        if name:
            currency_pts[name] = currency_pts.get(name, 0.0) + r.total_points
        cid = r.effective_currency_id
        if cid:
            currency_pts_by_id[cid] = currency_pts_by_id.get(cid, 0.0) + r.total_points
    currency_pts = {k: round(v, 2) for k, v in currency_pts.items()}
    currency_pts_by_id = {k: round(v, 2) for k, v in currency_pts_by_id.items()}

    return WalletResult(
        years_counted=years,
        total_effective_annual_fee=total_effective_annual_fee,
        total_points_earned=total_points_earned,
        total_annual_pts=total_annual_pts,
        total_cash_reward_dollars=total_cash_reward_dollars,
        total_reward_value_usd=total_reward_value_usd,
        currency_pts=currency_pts,
        currency_pts_by_id=currency_pts_by_id,
        card_results=card_results,
    )
