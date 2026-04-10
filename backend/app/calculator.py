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

from .constants import ALL_OTHER_CATEGORY, FOREIGN_TRANSACTION_FEE_PERCENT, PREFERRED_FOREIGN_NETWORKS
from .date_utils import add_months


# ---------------------------------------------------------------------------
# Data containers (plain dataclasses — no DB dependency)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CreditLine:
    """Statement credit row for calculations (ids match library `credits.id`)."""

    library_credit_id: int
    name: str
    value: float
    excludes_first_year: bool = False
    is_one_time: bool = False


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
    sub_points: int
    sub_cash: float  # dollar-denominated SUB bonus (e.g. $200 cash back), added at face value
    sub_min_spend: Optional[int]
    sub_months: Optional[int]
    sub_spend_earn: int
    annual_bonus: int
    annual_bonus_percent: float = 0.0
    annual_bonus_first_year_only: bool = False
    # Multiplier on allocation score that reflects the percentage bonus.
    # Set by compute_wallet before calculation. 1.0 = no bonus.
    # Recurring 10%: 1.1. First-year-only 100% over 2yr: 1.5.
    earn_bonus_factor: float = 1.0
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
    #                      Each category earns at the EV-blended rate
    #                      `p_C × bonus + (1 − p_C) × overflow` up to the FULL
    #                      per-period cap, instead of pretending the user can
    #                      perfectly time spend toward whichever quarter the
    #                      issuer activates. There is no pooling across
    #                      categories within the rotating group.
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
    credit_lines: list[CreditLine] = field(default_factory=list)
    # Set of category names where the multiplier only applies via the card's booking portal
    portal_categories: set[str] = field(default_factory=set)
    # Standalone is_portal=True premiums on this card. Each tuple is
    # (category_name_lowercase, premium_value, is_additive). The calculator
    # gates these by `portal_share`: only `share × spend[category]` of the
    # category's segment dollars get the portal premium; the rest fall back
    # to the card's non-portal rate on that category.
    portal_premiums: list[tuple[str, float, bool]] = field(default_factory=list)
    # Per-wallet share of travel-portal spend for this card (0..1). When the
    # card belongs to multiple TravelPortals, this is the *max* share across
    # those portals (so per-card calculations and the legacy greedy path see
    # the most-generous share). The LP path uses `portal_memberships` instead,
    # which preserves the portal_id grouping needed to pool caps across cards
    # that share a portal.
    # Set by `apply_wallet_portal_shares` from wallet_portal_shares rows.
    # Default 0 = portal premiums contribute nothing.
    portal_share: float = 0.0
    # {travel_portal_id: share} for every TravelPortal this card belongs to
    # in the current wallet. Empty when the card has no portal share rows.
    # The LP uses this to build *pooled* portal-cap constraints — all cards
    # in the same portal share one cap = `share × seg_dollars[cat]`, instead
    # of each card having its own independent cap.
    portal_memberships: dict[int, float] = field(default_factory=dict)
    # True if this card enables partner transfers for its currency (e.g. Sapphire Reserve for UR)
    transfer_enabler: bool = False

    # Foreign transaction fee: True = card charges ~3% FTF on foreign spend
    has_foreign_transaction_fee: bool = False
    # Payment network name (e.g. "Visa", "Mastercard") for FTF allocation priority
    network_name: Optional[str] = None
    # Bonus multiplier from a "Foreign Transactions" category (e.g. Summit 5x foreign)
    foreign_multiplier_bonus: float = 0.0

    # Secondary currency earned at a flat rate on all allocated spend
    # (e.g. Bilt Cash at 4% alongside Bilt Points via multipliers)
    secondary_currency: Optional[CurrencyData] = None
    secondary_currency_rate: float = 0.0  # e.g. 0.04 for 4%
    # Conversion cap: secondary currency can only convert to points when non-housing
    # spend on this card ≤ cap_rate × housing spend. 0 = no cap. (e.g. 0.75 for Bilt)
    secondary_currency_cap_rate: float = 0.0

    # Point accelerator: spend secondary currency to earn bonus primary points
    # (e.g. Bilt: $200 Bilt Cash for +1x on next $5,000, up to 5x/year)
    accelerator_cost: int = 0           # secondary currency points per activation
    accelerator_spend_limit: float = 0.0  # spend cap per activation in dollars
    accelerator_bonus_multiplier: float = 0.0  # extra primary multiplier per activation
    accelerator_max_activations: int = 0  # max activations per year

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
    sub_points: int = 0
    annual_bonus: int = 0
    annual_bonus_percent: float = 0.0
    annual_bonus_first_year_only: bool = False
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

    # Secondary currency earn
    secondary_currency_earn: float = 0.0        # gross secondary pts over projection window
    secondary_currency_name: str = ""
    secondary_currency_id: int = 0
    accelerator_activations: int = 0            # how many accelerator activations used
    accelerator_bonus_points: float = 0.0       # extra primary currency pts earned
    accelerator_cost_points: float = 0.0        # secondary currency pts spent on accelerator
    secondary_currency_net_earn: float = 0.0    # gross secondary pts minus accelerator cost
    secondary_currency_value_dollars: float = 0.0  # annualized dollar value of net secondary earn


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
    # Secondary currency totals (e.g. Bilt Cash earned across all cards)
    secondary_currency_pts: dict[str, float] = field(default_factory=dict)
    secondary_currency_pts_by_id: dict[int, float] = field(default_factory=dict)
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


def _secondary_currency_comparison_bonus(
    card: CardData,
    wallet_currency_ids: set[int],
    for_balance: bool = False,
) -> float:
    """
    Cents-per-dollar bonus from the secondary currency for allocation scoring.

    Returns the additional value (in cents) that each dollar spent on this card
    generates via the secondary currency. This is added to the primary
    ``multiplier × CPP`` score so allocation accounts for the secondary earn.
    """
    if card.secondary_currency is None or card.secondary_currency_rate <= 0:
        return 0.0
    sec = card.secondary_currency
    # secondary_currency_rate is a fraction (e.g. 0.04 for 4%).
    # Per dollar: earn rate * 100 secondary pts (cash cents).
    # Value those pts via conversion or CPP.
    if sec.converts_to_currency:
        target_cpp = sec.converts_to_currency.comparison_cpp if for_balance else sec.converts_to_currency.cents_per_point
        return card.secondary_currency_rate * 100 * sec.converts_at_rate * target_cpp
    cpp = sec.comparison_cpp if for_balance else sec.cents_per_point
    return card.secondary_currency_rate * 100 * cpp


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
        # Secondary currency adds a flat value per dollar to the comparison score.
        # This ensures cards earning a secondary currency (e.g. Bilt Cash → Bilt Points)
        # compete at their true effective value, not just the primary multiplier.
        sec_bonus = _secondary_currency_comparison_bonus(c, wallet_currency_ids, for_balance=for_balance)
        scored.append((m * cpp * c.earn_bonus_factor + sec_bonus, c))
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
    cat_pts = 0.0
    for cat, s in spend.items():
        if s <= 0:
            continue
        tied = _tied_cards_for_category(selected_cards, spend, cat, wallet_currency_ids, sub_priority_card_ids, for_balance=for_balance)
        if not tied or card.id not in {c.id for c in tied}:
            continue
        n = len(tied)
        m = _multiplier_for_category(card, cat, spend)
        cat_pts += (s / n) * m
    return float(card.annual_bonus) + cat_pts + _pct_bonus(card, cat_pts)


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
    # Percentage-based bonus line items
    cat_pts_total = sum(pts for _, pts in result if _ != "Annual Bonus")
    pct_recurring = _pct_bonus(card, cat_pts_total)
    if pct_recurring > 0:
        result.append((f"Annual Bonus ({card.annual_bonus_percent:g}%)", round(pct_recurring, 2)))
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


def calc_annual_point_earn(
    card: CardData,
    spend: dict[str, float],
) -> float:
    """Total points earned per year from category spend plus any annual bonus.
    Uses effective multipliers (top-N applied for groups) and All Other fallback.
    Includes recurring percentage bonus but NOT first-year-only percentage bonus.
    """
    cat_pts = sum(
        s * _multiplier_for_category(card, cat, spend)
        for cat, s in spend.items()
        if s > 0
    )
    return float(card.annual_bonus) + cat_pts + _pct_bonus(card, cat_pts)


def _credit_annual_and_one_time_totals(
    card: CardData,
) -> tuple[float, float, float]:
    """Return (annual_all_years, annual_skip_first_year, one_time).

    Credits with ``excludes_first_year=True`` (e.g. anniversary free night
    awards) are separated into the second bucket so callers can count them
    for ``years - 1`` instead of ``years``.

    Credits with ``is_one_time=True`` go into the one-time bucket and are
    amortised over the projection period (not multiplied by years).
    """
    annual = sum(
        line.value for line in card.credit_lines
        if not line.excludes_first_year and not line.is_one_time
    )
    annual_skip = sum(
        line.value for line in card.credit_lines
        if line.excludes_first_year and not line.is_one_time
    )
    one_time = sum(
        line.value for line in card.credit_lines if line.is_one_time
    )
    return annual, annual_skip, one_time


def calc_credit_valuation(card: CardData) -> float:
    """Sum of recurring credit dollar values for display."""
    return sum(line.value for line in card.credit_lines)


def calc_sub_extra_spend(
    card: CardData,
    spend: dict[str, float],
    selected_cards: list[CardData] | None = None,
    wallet_currency_ids: set[int] | None = None,
) -> float:
    """
    Additional dollars that must be spent to hit the SUB minimum spend,
    beyond what the card earns naturally from its category assignments.

    When *selected_cards* is provided, uses allocation-aware logic so that
    only categories where this card wins (or ties for) best earn rate count
    toward "natural spend".  Without it, falls back to single-card logic.
    """
    if not card.sub_min_spend:
        return 0.0
    if selected_cards and len(selected_cards) > 1 and wallet_currency_ids is not None:
        natural_spend = 0.0
        for cat, s in spend.items():
            if s <= 0:
                continue
            tied = _tied_cards_for_category(
                selected_cards, spend, cat, wallet_currency_ids,
            )
            if tied and card.id in {c.id for c in tied}:
                natural_spend += s / len(tied)
    else:
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

    extra_spend = calc_sub_extra_spend(card, spend, selected_cards, wallet_currency_ids)
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
    effective_sub_pts = card.sub_points if card.sub_earnable else 0
    # First-year-only percentage bonus: one-time points based on annual category earn.
    fy_bonus = 0.0
    if card.annual_bonus_percent and card.annual_bonus_first_year_only and rate:
        raw_cat_pts = effective_earn / rate - card.annual_bonus
        fy_bonus = _first_year_pct_bonus(card, raw_cat_pts) * rate
    return (
        effective_earn * years
        + effective_sub
        + effective_sub_pts
        + fy_bonus
    )


# ---------------------------------------------------------------------------
# Secondary currency and accelerator helpers
# ---------------------------------------------------------------------------


@dataclass
class _SecondaryResult:
    """Output from secondary currency + accelerator computation."""
    gross_annual_pts: float = 0.0       # gross secondary currency pts earned per year
    net_annual_pts: float = 0.0         # after subtracting accelerator cost per year
    dollar_value_annual: float = 0.0    # annualized dollar contribution
    activations: int = 0                # accelerator activations per year
    bonus_pts_annual: float = 0.0       # extra primary currency pts per year from accelerator
    cost_pts_annual: float = 0.0        # secondary currency pts spent on accelerator per year


def _calc_secondary_currency(
    card: CardData,
    allocated_annual_spend: float,
    wallet_currency_ids: set[int],
    housing_spend: float = 0.0,
) -> _SecondaryResult:
    """
    Compute secondary currency earn and accelerator net value for a card.

    The secondary currency earns at a flat rate on all spend allocated to this
    card. The accelerator lets the user spend secondary currency points to earn
    bonus primary currency points.

    housing_spend: total annual housing spend (Rent + Mortgage) in the wallet.
    When card.secondary_currency_cap_rate > 0, conversion to points is only
    possible up to cap_rate × housing_spend worth of non-housing spend. Beyond
    that, the secondary currency is valued at 0.
    """
    if card.secondary_currency is None or card.secondary_currency_rate <= 0:
        return _SecondaryResult()

    # Secondary currency earn: rate is a fraction of dollars (e.g. 0.04 for 4%).
    # For cash-kind currencies, 1 point = 1 cent, so $1 at 4% = 4 cents = 4 pts.
    annual_secondary_dollars = allocated_annual_spend * card.secondary_currency_rate
    annual_secondary_pts = annual_secondary_dollars * 100  # dollars to cents (cash points)

    # Conversion cap: only a portion of the secondary earn may be convertible.
    # When cap_rate > 0, convertible spend is capped at cap_rate × housing_spend.
    # Secondary pts from spend beyond the cap are valued at 0.
    if card.secondary_currency_cap_rate > 0 and housing_spend > 0:
        convertible_spend = min(allocated_annual_spend, card.secondary_currency_cap_rate * housing_spend)
    elif card.secondary_currency_cap_rate > 0 and housing_spend <= 0:
        # No housing spend means nothing can convert
        convertible_spend = 0.0
    else:
        # No cap
        convertible_spend = allocated_annual_spend
    convertible_pts = convertible_spend * card.secondary_currency_rate * 100

    # Accelerator: spend secondary currency to earn bonus primary points.
    # Accelerator cost is deducted from convertible secondary pts.
    activations = 0
    bonus_pts_annual = 0.0
    cost_pts_annual = 0.0
    if (
        card.accelerator_cost > 0
        and card.accelerator_spend_limit > 0
        and card.accelerator_bonus_multiplier > 0
        and card.accelerator_max_activations > 0
    ):
        # How many activations can the spend profile support?
        max_by_spend = int(allocated_annual_spend / card.accelerator_spend_limit) if card.accelerator_spend_limit > 0 else 0
        max_possible = min(card.accelerator_max_activations, max_by_spend)

        # Each activation: benefit = extra primary pts valued in dollars,
        # cost = secondary pts converted to dollars.
        primary_currency = _effective_currency(card, wallet_currency_ids)
        primary_cpp = primary_currency.cents_per_point
        benefit_pts_per = card.accelerator_spend_limit * card.accelerator_bonus_multiplier
        benefit_dollars_per = benefit_pts_per * primary_cpp / 100.0

        # Cost: accelerator_cost is in secondary currency points.
        # Value the cost via the secondary currency's conversion or CPP.
        sec_cur = card.secondary_currency
        if sec_cur.converts_to_currency:
            cost_dollars_per = card.accelerator_cost * sec_cur.converts_at_rate * sec_cur.converts_to_currency.cents_per_point / 100.0
        else:
            cost_dollars_per = card.accelerator_cost * sec_cur.cents_per_point / 100.0

        # Only activate when benefit exceeds cost and we have convertible pts to spend
        if benefit_dollars_per > cost_dollars_per:
            # Limit activations by available convertible secondary pts
            max_by_pts = int(convertible_pts / card.accelerator_cost) if card.accelerator_cost > 0 else 0
            activations = min(max_possible, max_by_pts)
        bonus_pts_annual = activations * benefit_pts_per
        cost_pts_annual = activations * card.accelerator_cost

    # Net convertible pts after accelerator cost
    net_convertible_pts = max(0.0, convertible_pts - cost_pts_annual)

    # Value: only convertible portion is valued (via conversion to points or CPP).
    # Non-convertible portion is valued at 0.
    sec_cur = card.secondary_currency
    if sec_cur.converts_to_currency:
        dollar_value_annual = net_convertible_pts * sec_cur.converts_at_rate * sec_cur.converts_to_currency.cents_per_point / 100.0
    else:
        dollar_value_annual = net_convertible_pts * sec_cur.cents_per_point / 100.0

    return _SecondaryResult(
        gross_annual_pts=annual_secondary_pts,
        net_annual_pts=annual_secondary_pts - cost_pts_annual,
        dollar_value_annual=dollar_value_annual,
        activations=activations,
        bonus_pts_annual=bonus_pts_annual,
        cost_pts_annual=cost_pts_annual,
    )


def _average_annual_net_dollars(
    card: CardData,
    spend: dict[str, float],
    years: int,
    wallet_currency_ids: set[int],
    selected_cards: list[CardData],
    precomputed_earn: Optional[float] = None,
    housing_spend: float = 0.0,
) -> float:
    """
    Average annual net dollar benefit over `years`, amortising SUB and first-year fee.

    Category spend is wallet-allocated (each category goes to best m×CPP card(s);
    ties split dollars evenly among tied cards).

    effective_earn already includes card.annual_bonus (from _effective_annual_earn_allocated),
    so the annual bonus is naturally amortised over `years` via the earn × years term.

    precomputed_earn: if provided, used in place of _effective_annual_earn_allocated.

    housing_spend: total annual housing spend (Rent + Mortgage) in the wallet,
    used for secondary currency conversion cap calculations.

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
    annual_credits, annual_credits_skip, one_time_credits = _credit_annual_and_one_time_totals(card)

    rate = _conversion_rate(card, wallet_currency_ids)
    # When the SUB is not earnable, exclude the SUB bonus and its earn contribution
    effective_sub = (card.sub_spend_earn * rate) if card.sub_earnable else 0.0
    effective_sub_pts = card.sub_points if card.sub_earnable else 0
    effective_sub_cash = card.sub_cash if card.sub_earnable else 0.0
    fee_y1 = card.first_year_fee if card.first_year_fee is not None else card.annual_fee
    total_fees = fee_y1 + (years - 1) * card.annual_fee
    # effective_earn (from _effective_annual_earn_allocated) already includes card.annual_bonus
    # and any recurring percentage bonus, so they are counted correctly via the years
    # multiplier. effective_sub and effective_sub_pts are one-time earns; placing them
    # outside the * years term means they are amortised by the outer / years.
    # First-year-only percentage bonus is also one-time, amortised like SUB.
    fy_bonus_eff = 0.0
    if card.annual_bonus_percent and card.annual_bonus_first_year_only and rate:
        raw_cat_pts = effective_earn / rate - card.annual_bonus
        fy_bonus_eff = _first_year_pct_bonus(card, raw_cat_pts) * rate
    # Secondary currency: flat-rate earn on allocated spend + accelerator net value.
    # dollar_value_annual covers the net secondary currency earn (gross minus accelerator cost).
    # bonus_pts_annual covers extra primary currency pts earned via the accelerator.
    allocated_spend = calc_annual_allocated_spend(card, selected_cards, spend, wallet_currency_ids)
    sec = _calc_secondary_currency(card, allocated_spend, wallet_currency_ids, housing_spend=housing_spend)
    # Accelerator bonus points are primary currency points; value them at primary CPP.
    accel_bonus_dollars_annual = sec.bonus_pts_annual * cpp / 100.0

    value = (
        (effective_earn / 100 * cpp) * years
        + effective_sub / 100 * cpp
        + effective_sub_pts * cpp / 100
        + effective_sub_cash
        + fy_bonus_eff / 100 * cpp
        + annual_credits * years
        + annual_credits_skip * max(years - 1, 0)
        + one_time_credits
        + sec.dollar_value_annual * years
        + accel_bonus_dollars_annual * years
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
      the FULL `cap_per_billing_cycle` per category per period (not scaled by
      p_C). The bonus rate applied to spend up to the cap is the *expected*
      rate over the period:

          ev_rate(C) = p_C × bonus_rate_when_active + (1 − p_C) × overflow_rate

      where p_C is the historical activation probability for category C.
      This credits expected points instead of assuming the user can perfectly
      time their spend toward whichever category the issuer activates in a
      given quarter. Categories with p_C = 0 (never historically active)
      collapse to the overflow rate. There is no pooling across categories
      within the rotating group; each gets its own per-period budget.

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

    seg_year, seg_quarter = _calendar_quarter(seg_start)

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
            # Expected-value rate for this category.
            #
            # The calculator does NOT pretend the user can perfectly time their
            # spend to whichever category is active in a given quarter. Instead,
            # every dollar in C earns a blended rate that mixes the bonus rate
            # (with probability p_C the issuer activates this category in the
            # quarter) and the overflow rate (otherwise):
            #
            #     ev_rate(C) = p_C × bonus_rate + (1 − p_C) × overflow_rate
            #
            # This rate applies to spend up to the FULL per-period cap (not a
            # p_C-scaled cap). Above the cap, spend reverts to the overflow
            # rate, since the issuer's cap binds even on the active quarters.
            p_c = rot_weights.get(cat_lower, 0.0)
            if p_c <= 0.0:
                # Category is in the rotating universe but has never been
                # active in our recorded history → no bonus path; ev_rate
                # collapses to overflow.
                pts = seg_alloc_dollars * overflow_rate
                if pts > 0:
                    out[cat] = out.get(cat, 0.0) + pts
                continue
            ev_rate = p_c * bonus_rate + (1.0 - p_c) * overflow_rate
            key = ("rot", gid, period_start, cat_lower)
            if key not in cap_state:
                cap_state[key] = float(g_cap_amt)
            remaining = cap_state[key]
            bonus_dollars = min(seg_alloc_dollars, remaining)
            overflow_dollars = seg_alloc_dollars - bonus_dollars
            cap_state[key] = remaining - bonus_dollars
            pts = bonus_dollars * ev_rate + overflow_dollars * overflow_rate
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
      - per-category cap constraints on rotating groups, where the bonus
        var earns at the expected rate
        ``p_C × bonus + (1 − p_C) × overflow`` up to the FULL per-quarter
        cap (the LP allocates *expected* points, not perfectly-timed spend)
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
        card_cpp[k_idx] = _comparison_cpp(c, seg_currency_ids, for_balance=for_balance) * c.earn_bonus_factor

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

    # ---- Portal premiums. ----
    # Each TravelPortal in the wallet has one share value that represents
    # "fraction of travel-coverable spend booked through this portal." The
    # cap is therefore POOLED across every card belonging to that portal —
    # the user can only book each $1 of travel through the portal once, so
    # the total bonus dollars across all member cards must respect that
    # single share × seg_dollars[cat] limit.
    #
    # We bucket portal premiums by (portal_id, cat_lower) below: each bucket
    # collects every (card_idx, premium, is_additive) member of that portal
    # that exposes a premium for the category. One pooled _CapConstraint is
    # emitted per bucket in the constraint pass below.
    #
    # `portal_buckets[(portal_id, cat_lower)] = (share, [(k_idx, premium, is_add), ...])`
    portal_buckets: dict[tuple[int, str], tuple[float, list[tuple[int, float, bool]]]] = {}
    for k_idx, c in enumerate(competing):
        if not c.portal_memberships or not c.portal_premiums:
            continue
        for portal_id, share in c.portal_memberships.items():
            if share <= 0.0:
                continue
            for cat_lower, premium, p_is_add in c.portal_premiums:
                bucket = portal_buckets.get((portal_id, cat_lower))
                if bucket is None:
                    portal_buckets[(portal_id, cat_lower)] = (
                        float(share),
                        [(k_idx, float(premium), bool(p_is_add))],
                    )
                else:
                    bucket[1].append((k_idx, float(premium), bool(p_is_add)))

    for k_idx, c in enumerate(competing):
        for (
            g_mult, g_cats, _topn, g_id,
            g_cap_amt, g_cap_months, g_is_rot, g_rot_weights, g_is_add,
        ) in c.multiplier_groups:
            if g_id is None or g_cap_amt is None or not g_cap_months or g_cap_months <= 0:
                continue
            period_start, _ = _cap_period_bounds(seg_start, g_cap_months)
            cat_lower_set = {(x or "").strip().lower() for x in g_cats}

            if g_is_rot:
                # Per-category EV-blended bonus rate, applied up to the FULL
                # quarterly cap (not a p_C-scaled cap). The bonus var earns at
                #
                #     ev_rate = p_C × bonus_rate_when_active
                #             + (1 − p_C) × overflow_rate
                #
                # so the LP credits expected points rather than pretending the
                # user can route every dollar to the active quarter. Above the
                # cap the base var takes over at the overflow rate, which is
                # the always-on `cat_mult` for additive groups (Freedom Flex)
                # and `all_other` for non-additive groups (Discover IT).
                rot_lookup = {(k or "").strip().lower(): float(v) for k, v in g_rot_weights.items()}
                for cl in cat_lower_set:
                    p_c = rot_lookup.get(cl, 0.0)
                    if p_c <= 0.0:
                        # No bonus path for this category; it earns base only.
                        continue
                    state_key = ("rot", g_id, period_start, cl)
                    if state_key not in cap_state:
                        cap_state[state_key] = float(g_cap_amt)
                    active_bonus_rate = _bonus_rate_for_pair(
                        k_idx, cl, float(g_mult), g_is_add
                    )
                    if g_is_add:
                        overflow_rate_for_pair = card_mult[k_idx].get(
                            cl, card_all_other[k_idx]
                        )
                    else:
                        overflow_rate_for_pair = card_all_other[k_idx]
                    ev_rate = (
                        p_c * active_bonus_rate
                        + (1.0 - p_c) * overflow_rate_for_pair
                    )
                    bonus_mult[(k_idx, cl)] = ev_rate
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

    # ---- Portal premium constraints (pooled per portal). ----
    # For each (portal_id, category) bucket built above, emit ONE constraint
    # whose members are every card-bonus-var in that portal/category combo.
    # The cap is `share × seg_dollars[cat]` — a wallet-wide pool, not per
    # card. The LP can then route the eligible spend to whichever member
    # earns the most per dollar (typically the highest portal multiplier),
    # while the rest of the spend falls to base/standalone variables.
    for (portal_id, spec_cl), (share, members_spec) in portal_buckets.items():
        # Find the matching category (case-insensitive) in cat_dollars.
        cat_seg_dollars = 0.0
        for cat, d_c in cat_dollars:
            if cat.strip().lower() == spec_cl:
                cat_seg_dollars = d_c
                break
        if cat_seg_dollars <= 0.0 or share <= 0.0:
            continue
        portal_cap = share * cat_seg_dollars
        if portal_cap <= 0.0:
            continue
        state_key = ("portal", portal_id, spec_cl, seg_start)
        # Always re-initialize per segment (portal shares are per-quarter
        # intent, not cumulative).
        cap_state[state_key] = portal_cap
        constraint_members: list[tuple[int, str]] = []
        for spec_k_idx, spec_premium, spec_is_add in members_spec:
            # Each member gets its own bonus var with its own rate.
            rate = _bonus_rate_for_pair(spec_k_idx, spec_cl, spec_premium, spec_is_add)
            existing_bonus = bonus_mult.get((spec_k_idx, spec_cl))
            if existing_bonus is None or rate > existing_bonus:
                bonus_mult[(spec_k_idx, spec_cl)] = rate
                pair_is_additive[(spec_k_idx, spec_cl)] = spec_is_add
            capped_pairs.add((spec_k_idx, spec_cl))
            constraint_members.append((spec_k_idx, spec_cl))
        if constraint_members:
            constraints.append(
                _CapConstraint(
                    members=constraint_members,
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
            # The base variable always earns at the card's always-on rate for
            # this category — i.e., what the category earns *without* the
            # bonus path being active. For cards where the only multiplier on
            # the category lives inside a non-additive cap group (BCP 6x
            # Groceries, Discover IT rotating Gas), `card_mult[k][cat]` is
            # not set and falls back to All Other, matching the original
            # "overflow → All Other" behaviour for legacy non-additive groups.
            #
            # When the card has BOTH a standalone always-on multiplier AND a
            # non-additive bonus on the same category (e.g. CSR Airlines 4x
            # standalone + 8x Chase Travel portal expansion), `card_mult` is
            # 4x and the base var correctly earns 4x on the non-portal
            # portion, instead of being silently dropped to All Other = 1x.
            mult = card_mult[k_idx].get(cat_lower, card_all_other[k_idx])
        else:
            mult = bonus_mult.get((k_idx, cat_lower), card_all_other[k_idx])
        # Effective $ earned per $ spent (primary earn + secondary currency bonus).
        sec_bonus = _secondary_currency_comparison_bonus(competing[k_idx], seg_currency_ids, for_balance=for_balance)
        rate = mult * cpp / 100.0 + sec_bonus / 100.0
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
        sub_prio = _sub_priority_ids_for_segment(active, seg_start, spend, seg_currency_ids)
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
    housing_spend: float = 0.0,
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
            card, spend, 1, wallet_currency_ids, selected_cards, precomputed_earn=earn,
            housing_spend=housing_spend,
        )
        return net, earn, earn_for_balance

    total_years = total_days / 365.25
    active_wallet_currency_ids = _wallet_currency_ids(selected_cards)
    segments = _build_segments(window_start, window_end, selected_cards)

    total_earn_dollars = 0.0
    annualized_earn_pts = 0.0
    annualized_earn_pts_for_balance = 0.0
    annualized_raw_cat_pts = 0.0  # raw category earn (no fixed bonus/conversion), for first-year pct bonus
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
        sub_prio = _sub_priority_ids_for_segment(active, seg_start, spend, seg_currency_ids)

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
        seg_cat_pts_raw = sum(cat_pts.values())
        seg_cat_pts_raw_balance = sum(cat_pts_balance.values())
        # Annualize segment category earn for percentage bonus calculation.
        seg_cat_annual = seg_cat_pts_raw / seg_years if seg_years > 0 else 0.0
        seg_cat_annual_balance = seg_cat_pts_raw_balance / seg_years if seg_years > 0 else 0.0
        seg_pct_bonus = _pct_bonus(card, seg_cat_annual) * seg_years
        seg_pct_bonus_balance = _pct_bonus(card, seg_cat_annual_balance) * seg_years
        seg_pts_raw = seg_cat_pts_raw + float(card.annual_bonus) * seg_years + seg_pct_bonus
        seg_pts_raw_balance = seg_cat_pts_raw_balance + float(card.annual_bonus) * seg_years + seg_pct_bonus_balance
        seg_pts = seg_pts_raw * conv_rate
        seg_pts_balance = seg_pts_raw_balance * conv_rate

        eff_currency = _effective_currency(card, seg_currency_ids)
        total_earn_dollars += seg_pts * eff_currency.cents_per_point / 100.0
        annualized_earn_pts += seg_pts * 365.25 / total_days
        annualized_earn_pts_for_balance += seg_pts_balance * 365.25 / total_days
        annualized_raw_cat_pts += seg_cat_pts_raw * 365.25 / total_days

        annual_credits, annual_credits_skip, _ = _credit_annual_and_one_time_totals(card)
        total_credits += annual_credits * seg_days / 365.25
        # Anniversary-only credits: only count days after the card's 1-year mark.
        if annual_credits_skip and card.wallet_added_date:
            anniversary = add_months(card.wallet_added_date, 12)
            if seg_end > anniversary:
                eligible_start = max(seg_start, anniversary)
                eligible_days = (seg_end - eligible_start).days
                total_credits += annual_credits_skip * eligible_days / 365.25
        elif annual_credits_skip and not card.wallet_added_date:
            # No date context: assume card is past its first year.
            total_credits += annual_credits_skip * seg_days / 365.25

    # One-time credits
    _, _, one_time_credits = _credit_annual_and_one_time_totals(card)
    if card_ever_active:
        total_credits += one_time_credits

    # SUB: one-time bonus value only.
    # sub_spend_earn and opportunity cost are deliberately excluded here:
    # the SUB ROS boost in the segment earn already redirects spend to this card
    # during its SUB window (captured in total_earn_dollars above), so adding
    # sub_spend_earn would double-count those points, and subtracting net_opp
    # would double-count the cost already reflected in other cards' reduced
    # segment earn.
    if card.sub_earnable and card.sub_points:
        earned = card.sub_projected_earn_date
        if earned is None or window_start <= earned <= window_end:
            eff_currency = _effective_currency(card, active_wallet_currency_ids)
            total_earn_dollars += card.sub_points * eff_currency.cents_per_point / 100.0
    if card.sub_earnable and card.sub_cash:
        total_credits += card.sub_cash

    # First-year-only percentage bonus: one-time earn based on annualized category
    # earn rate, counted once regardless of window length (like SUB).
    if card_ever_active and card.annual_bonus_percent and card.annual_bonus_first_year_only:
        fy_bonus_raw = _first_year_pct_bonus(card, annualized_raw_cat_pts)
        fy_bonus_eff = fy_bonus_raw * conv_rate
        eff_currency = _effective_currency(card, active_wallet_currency_ids)
        total_earn_dollars += fy_bonus_eff * eff_currency.cents_per_point / 100.0

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

    # Secondary currency: flat-rate earn prorated to the card's active window.
    # Use the full annual allocated spend scaled by active fraction of the window.
    if card.secondary_currency and card.secondary_currency_rate > 0 and card_ever_active:
        annual_alloc = calc_annual_allocated_spend(card, selected_cards, spend, active_wallet_currency_ids)
        active_fraction = active_days / 365.25 if active_days > 0 else 0.0
        # Compute housing spend from spend dict using housing_category_names
        # (passed through from compute_wallet; not available here, so use the
        # card-level cap with full wallet housing spend passed as param)
        sec = _calc_secondary_currency(card, annual_alloc, active_wallet_currency_ids, housing_spend=housing_spend)
        total_earn_dollars += sec.dollar_value_annual * active_fraction * total_years
        # Accelerator bonus: extra primary pts valued at primary CPP
        eff_currency_sec = _effective_currency(card, active_wallet_currency_ids)
        total_earn_dollars += sec.bonus_pts_annual * eff_currency_sec.cents_per_point / 100.0 * active_fraction * total_years

    total_net = total_earn_dollars + total_credits - total_fee
    return total_net / total_years, annualized_earn_pts, annualized_earn_pts_for_balance


# ---------------------------------------------------------------------------
# Wallet-level aggregation
# ---------------------------------------------------------------------------


FOREIGN_CAT_PREFIX = "__foreign__"


def _split_spend_for_foreign(
    cards: list[CardData],
    selected_ids: set[int],
    spend: dict[str, float],
    foreign_spend_pct: float,
) -> tuple[list[CardData], dict[str, float]]:
    """
    Split each spend category into a domestic portion and a foreign portion.

    The foreign portion is given a unique key prefix (``__foreign__``) so the
    existing allocation logic treats it as a separate category. Each card's
    multipliers dict is augmented with an explicit entry for every foreign
    category, computed as:

      - 0 (effectively excluded) if the card has FTF and any selected no-FTF
        card exists, OR if the card is not on a preferred network and any
        selected no-FTF Visa/Mastercard exists.
      - Otherwise: max(card's category multiplier, card's "Foreign Transactions"
        multiplier) — so a card like Summit with 3x Foreign Transactions still
        earns its base 3x Dining on foreign Dining (no double-up), but earns
        3x on foreign Groceries (replacing 1x All Other).
    """
    if foreign_spend_pct <= 0:
        return cards, spend
    frac = max(0.0, min(1.0, foreign_spend_pct / 100.0))
    if frac <= 0:
        return cards, spend

    selected = [c for c in cards if c.id in selected_ids]
    has_no_ftf = any(not c.has_foreign_transaction_fee for c in selected)
    has_no_ftf_visa_mc = any(
        (not c.has_foreign_transaction_fee)
        and c.network_name in PREFERRED_FOREIGN_NETWORKS
        for c in selected
    )

    # Build modified spend dict with split categories
    new_spend: dict[str, float] = {}
    foreign_keys: dict[str, str] = {}  # category -> foreign key
    for cat, amt in spend.items():
        if amt > 0:
            new_spend[cat] = amt * (1 - frac)
            fk = f"{FOREIGN_CAT_PREFIX}{cat}"
            new_spend[fk] = amt * frac
            foreign_keys[cat] = fk
        else:
            new_spend[cat] = amt

    # Build modified card list with explicit foreign multipliers per category
    new_cards: list[CardData] = []
    for card in cards:
        # Eligibility for foreign spend allocation:
        # - If any no-FTF card exists, FTF cards are excluded
        # - If any no-FTF Visa/MC card exists, non-Visa/MC cards are excluded
        eligible = True
        if has_no_ftf and card.has_foreign_transaction_fee:
            eligible = False
        elif has_no_ftf_visa_mc and (
            not card.network_name or card.network_name not in PREFERRED_FOREIGN_NETWORKS
        ):
            eligible = False

        # The "foreign rate" any selected card uses on a foreign category C is
        # max(its multiplier on C, its Foreign Transactions multiplier).
        foreign_base = card.foreign_multiplier_bonus  # from "Foreign Transactions"
        # Compute the card's All Other rate (used as fallback for categories
        # not explicitly in the multipliers dict).
        ao_rate = _all_other_multiplier(card.multipliers)

        new_mults = dict(card.multipliers)
        for orig_cat, fk in foreign_keys.items():
            if not eligible:
                new_mults[fk] = 0.0
                continue
            # Effective per-category rate: explicit if present, else All Other
            cat_rate = card.multipliers.get(orig_cat, ao_rate)
            # Case-insensitive lookup fallback
            if orig_cat not in card.multipliers:
                for k, v in card.multipliers.items():
                    if k.strip().lower() == orig_cat.strip().lower():
                        cat_rate = v
                        break
            new_mults[fk] = max(cat_rate, foreign_base)

        new_cards.append(replace(card, multipliers=new_mults))

    return new_cards, new_spend


def _merge_foreign_breakdown(
    breakdown: list[tuple[str, float]],
) -> list[tuple[str, float]]:
    """Combine ``__foreign__X`` entries back into ``X`` for display."""
    merged: dict[str, float] = {}
    order: list[str] = []
    for label, pts in breakdown:
        if label.startswith(FOREIGN_CAT_PREFIX):
            base = label[len(FOREIGN_CAT_PREFIX):]
        else:
            base = label
        if base not in merged:
            merged[base] = 0.0
            order.append(base)
        merged[base] += pts
    out = [(name, round(merged[name], 2)) for name in order if merged[name] > 0]
    out.sort(key=lambda x: x[1], reverse=True)
    return out


def compute_wallet(
    all_cards: list[CardData],
    selected_ids: set[int],
    spend: dict[str, float],
    years: int,
    window_start: Optional[date] = None,
    window_end: Optional[date] = None,
    sub_priority_card_ids: set[int] | None = None,
    housing_category_names: set[str] | None = None,
    foreign_spend_pct: float = 0.0,
) -> WalletResult:
    """
    Compute results for every card in `all_cards`.
    Only cards with id in `selected_ids` contribute to totals and currency points.

    window_start / window_end: when provided and any selected card has date info,
    the earn calculation is time-weighted across segments based on card open/close
    and SUB earn boundaries (per-day optimisation).
    """
    selected_cards = [c for c in all_cards if c.id in selected_ids]

    # Foreign spend: split each category into a domestic and a foreign portion,
    # injecting per-card "foreign category" multipliers that account for
    # FTF priority filtering (no-FTF cards win all foreign spend if any exist;
    # no-FTF Visa/MC win over no-FTF other networks).
    all_cards, spend = _split_spend_for_foreign(
        all_cards, selected_ids, spend, foreign_spend_pct,
    )
    selected_cards = [c for c in all_cards if c.id in selected_ids]

    # Adjust CPP for currencies that lack a transfer enabler in the wallet.
    all_cards = _apply_transfer_enabler_cpp(all_cards, selected_cards)
    selected_cards = [c for c in all_cards if c.id in selected_ids]

    # Apply earn_bonus_factor for percentage-based annual bonuses.
    # This factor is used by allocation scoring so cards with bonuses compete
    # at their effective earn rate. For the simple path, first-year-only bonuses
    # use an amortised factor; the segmented path overrides per-segment below.
    all_cards = [
        replace(c, earn_bonus_factor=_calc_earn_bonus_factor(c, years))
        if c.annual_bonus_percent else c
        for c in all_cards
    ]
    selected_cards = [c for c in all_cards if c.id in selected_ids]

    active_wallet_currency_ids = _wallet_currency_ids(selected_cards)

    # Compute total housing spend for secondary currency conversion cap.
    # When foreign spend split is in effect, housing categories may exist as both
    # "Rent" and "__foreign__Rent" entries; both contribute to total housing.
    _housing_names = housing_category_names or set()
    _housing_lower = {n.lower() for n in _housing_names}
    def _is_housing(cat: str) -> bool:
        base = cat[len(FOREIGN_CAT_PREFIX):] if cat.startswith(FOREIGN_CAT_PREFIX) else cat
        return base.lower() in _housing_lower
    housing_spend_total = sum(
        s for cat, s in spend.items() if _is_housing(cat) and s > 0
    )

    # When the wallet has no housing spend, any card whose secondary currency
    # requires a housing-spend cap (cap_rate > 0) cannot realize that value.
    # Zero its secondary_currency_rate so allocation scoring (the LP) doesn't
    # treat it as if the secondary earn were realizable.
    if housing_spend_total <= 0:
        all_cards = [
            replace(c, secondary_currency_rate=0.0)
            if c.secondary_currency is not None and c.secondary_currency_cap_rate > 0
            else c
            for c in all_cards
        ]
        selected_cards = [c for c in all_cards if c.id in selected_ids]

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
        # Any first-year-only bonus cards need per-segment factor overrides so
        # the LP allocates categories correctly during vs. after the match year.
        has_fy_bonus = any(c.annual_bonus_percent and c.annual_bonus_first_year_only for c in selected_cards)
        for seg_start, seg_end, active in segments_for_cache:
            seg_days = (seg_end - seg_start).days
            # Override earn_bonus_factor per-segment for first-year-only cards.
            if has_fy_bonus:
                active = [
                    replace(c, earn_bonus_factor=_segment_earn_bonus_factor(c, seg_start))
                    if c.annual_bonus_percent and c.annual_bonus_first_year_only else c
                    for c in active
                ]
            seg_currency_ids = {c.currency.id for c in active}
            sub_prio = _sub_priority_ids_for_segment(active, seg_start, spend, seg_currency_ids)
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
                    sub_points=card.sub_points,
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
                housing_spend=housing_spend_total,
            )
            effective_annual_fee = round(-net_annual, 4)
            # total_points: annualized earn (default CPP) × total window years + one-time SUB bonus.
            # Uses for_balance earn so point totals are independent of wallet CPP overrides.
            # sub_spend_earn and net_opp are excluded (already captured in segment earn).
            total_years_window = (window_end - window_start).days / 365.25  # type: ignore[operator]
            sub_earnable_pts = card.sub_points if card.sub_earnable else 0
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
                housing_spend=housing_spend_total,
            )
            effective_annual_fee = round(-net_annual, 4)
            total_points = calc_total_points(
                card, selected_cards, spend, years, active_wallet_currency_ids,
                precomputed_earn=annual_point_earn_for_balance,
            )
        credit_val = calc_credit_valuation(card)
        sub_extra = calc_sub_extra_spend(card, spend, selected_cards, active_wallet_currency_ids)
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
        # First-year-only percentage bonus shown as a separate line item in the breakdown.
        if card.annual_bonus_percent and card.annual_bonus_first_year_only:
            cat_pts_for_fy = sum(pts for label, pts in cat_earn
                                if label not in ("Annual Bonus", "SUB Spend"))
            fy_bonus = _first_year_pct_bonus(card, cat_pts_for_fy)
            if fy_bonus > 0:
                cat_earn = list(cat_earn) + [(f"First Year Match ({card.annual_bonus_percent:g}%)", round(fy_bonus, 2))]
                cat_earn.sort(key=lambda x: x[1], reverse=True)

        # Merge any "__foreign__X" entries back into "X" for display
        if foreign_spend_pct > 0:
            cat_earn = _merge_foreign_breakdown(cat_earn)

        # Surface only the SUB values that were actually counted in totals.
        # When sub_earnable is False (e.g. in-wallet cards whose SUB is historical
        # or cards the user can't reach the min spend on), the calculator already
        # excluded these from total_points and effective_annual_fee — reporting
        # the raw library values here would let the UI double-subtract them.
        reported_sub = card.sub_points if card.sub_earnable else 0
        reported_sub_spend_earn = card.sub_spend_earn if card.sub_earnable else 0

        # Secondary currency result for this card
        sec_alloc = calc_annual_allocated_spend(card, selected_cards, spend, active_wallet_currency_ids)
        sec = _calc_secondary_currency(card, sec_alloc, active_wallet_currency_ids, housing_spend=housing_spend_total)
        sec_cur_name = card.secondary_currency.name if card.secondary_currency else ""
        sec_cur_id = card.secondary_currency.id if card.secondary_currency else 0
        # Total secondary pts over the projection window
        sec_gross_total = sec.gross_annual_pts * years
        sec_net_total = sec.net_annual_pts * years
        sec_cost_total = sec.cost_pts_annual * years
        sec_bonus_total = sec.bonus_pts_annual * years

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
                sub_points=reported_sub,
                annual_bonus=card.annual_bonus,
                annual_bonus_percent=card.annual_bonus_percent,
                annual_bonus_first_year_only=card.annual_bonus_first_year_only,
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
                secondary_currency_earn=round(sec_gross_total, 2),
                secondary_currency_name=sec_cur_name,
                secondary_currency_id=sec_cur_id,
                accelerator_activations=sec.activations,
                accelerator_bonus_points=round(sec_bonus_total, 2),
                accelerator_cost_points=round(sec_cost_total, 2),
                secondary_currency_net_earn=round(sec_net_total, 2),
                secondary_currency_value_dollars=round(sec.dollar_value_annual * years, 2),
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

    # Secondary currency totals (e.g. Bilt Cash across all cards)
    secondary_currency_pts: dict[str, float] = {}
    secondary_currency_pts_by_id: dict[int, float] = {}
    for r in selected_results:
        if r.secondary_currency_id and r.secondary_currency_net_earn:
            name = (r.secondary_currency_name or "").strip()
            if name:
                secondary_currency_pts[name] = secondary_currency_pts.get(name, 0.0) + r.secondary_currency_net_earn
            secondary_currency_pts_by_id[r.secondary_currency_id] = (
                secondary_currency_pts_by_id.get(r.secondary_currency_id, 0.0) + r.secondary_currency_net_earn
            )
    secondary_currency_pts = {k: round(v, 2) for k, v in secondary_currency_pts.items()}
    secondary_currency_pts_by_id = {k: round(v, 2) for k, v in secondary_currency_pts_by_id.items()}

    return WalletResult(
        years_counted=years,
        total_effective_annual_fee=total_effective_annual_fee,
        total_points_earned=total_points_earned,
        total_annual_pts=total_annual_pts,
        total_cash_reward_dollars=total_cash_reward_dollars,
        total_reward_value_usd=total_reward_value_usd,
        currency_pts=currency_pts,
        currency_pts_by_id=currency_pts_by_id,
        secondary_currency_pts=secondary_currency_pts,
        secondary_currency_pts_by_id=secondary_currency_pts_by_id,
        card_results=card_results,
    )
