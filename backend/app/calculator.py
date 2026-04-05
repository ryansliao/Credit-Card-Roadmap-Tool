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
from dataclasses import dataclass, field
from datetime import date
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
    one_time: bool = False


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

    # category -> multiplier (standalone + group categories; top-N applied at calc time via multiplier_groups)
    multipliers: dict[str, float] = field(default_factory=dict)
    # Group metadata for top-N: (multiplier, categories list, top_n_categories or None)
    multiplier_groups: list[tuple[float, list[str], Optional[int]]] = field(default_factory=list)
    credit_lines: list[CreditLine] = field(default_factory=list)
    # Set of category names where the multiplier only applies via the card's booking portal
    portal_categories: set[str] = field(default_factory=set)

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

    for group_mult, group_cats, top_n in card.multiplier_groups:
        if top_n is None or top_n <= 0:
            continue
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
    sub_ros_by_card_id: dict[int, float] | None = None,
    for_balance: bool = False,
) -> list[CardData]:
    """
    All selected cards tied for the best multiplier × effective CPP on this category.
    Category dollars are split evenly across them; each card applies its own multiplier
    to its share (see calc_annual_point_earn_allocated).

    sub_ros_by_card_id: optional per-card SUB return-on-spend boost (dollars per dollar),
    added to the score so SUB cards naturally attract spend during their SUB window.

    for_balance: when True, uses default (non-overridden) CPP for scoring so that
    balance point totals are independent of wallet CPP overrides.
    """
    scored: list[tuple[float, CardData]] = []
    for c in selected_cards:
        m = _multiplier_for_category(c, category, spend)
        cpp = _comparison_cpp(c, wallet_currency_ids, for_balance=for_balance)
        base_score = m * cpp
        # SUB ROS boost: convert $/$ to cents/$ to match base_score units (cpp is in cents)
        sub_boost = (sub_ros_by_card_id.get(c.id, 0.0) * 100.0) if sub_ros_by_card_id else 0.0
        scored.append((base_score + sub_boost, c))
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
    sub_ros_by_card_id: dict[int, float] | None = None,
    for_balance: bool = False,
) -> float:
    """
    Points from spend: each category is assigned to the card(s) with the best
    multiplier × effective CPP; tied cards split category dollars evenly, each
    earning (share × own multiplier). Annual bonus still applies in full to every card.

    sub_ros_by_card_id: optional SUB ROS boosts passed to the category scorer.

    for_balance: when True, uses default (non-overridden) CPP for scoring so that
    balance point totals are independent of wallet CPP overrides.
    """
    if len(selected_cards) <= 1:
        return calc_annual_point_earn(card, spend)
    total = float(card.annual_bonus)
    for cat, s in spend.items():
        if s <= 0:
            continue
        tied = _tied_cards_for_category(selected_cards, spend, cat, wallet_currency_ids, sub_ros_by_card_id, for_balance=for_balance)
        if not tied or card.id not in {c.id for c in tied}:
            continue
        n = len(tied)
        m = _multiplier_for_category(card, cat, spend)
        total += (s / n) * m
    return total


def calc_category_earn_breakdown(
    card: CardData,
    selected_cards: list[CardData],
    spend: dict[str, float],
    wallet_currency_ids: set[int],
    sub_ros_by_card_id: dict[int, float] | None = None,
) -> list[tuple[str, float]]:
    """
    Per-category annual earn breakdown: list of (category_name, points) sorted by points desc.
    Mirrors the allocation logic in calc_annual_point_earn_allocated.
    Includes spend categories with positive earn, plus annual bonus.
    Points are in raw (pre-conversion) currency units, consistent with category spend items.
    sub_ros_by_card_id: optional SUB ROS boosts, passed through to _tied_cards_for_category.
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
            tied = _tied_cards_for_category(selected_cards, spend, cat, wallet_currency_ids, sub_ros_by_card_id)
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
) -> list[tuple[str, float]]:
    """
    Time-weighted per-category earn breakdown for the segmented calculation path.
    Mirrors the segment/active-card/SUB-ROS logic used in _time_weighted_annual_earn so
    the breakdown is consistent with annual_point_earn from _segmented_card_net_per_year.
    Points are accumulated as (seg_fraction × per-category-pts) across all segments where
    this card is active.
    """
    total_days = (window_end - window_start).days
    if total_days <= 0:
        return calc_category_earn_breakdown(
            card, selected_cards, spend, _wallet_currency_ids(selected_cards)
        )

    segments = _build_segments(window_start, window_end, selected_cards)
    cat_totals: dict[str, float] = {}

    for seg_start, seg_end, active in segments:
        if card not in active:
            continue
        seg_days = (seg_end - seg_start).days
        seg_fraction = seg_days / total_days
        seg_currency_ids = {c.currency.id for c in active}
        sub_ros = {c.id: _sub_ros_for_segment(c, seg_start, seg_currency_ids) for c in active}

        if len(active) <= 1:
            for cat, s in spend.items():
                if s <= 0:
                    continue
                m = _multiplier_for_category(card, cat, spend)
                pts = s * m * seg_fraction
                if pts > 0:
                    cat_totals[cat] = cat_totals.get(cat, 0) + pts
        else:
            for cat, s in spend.items():
                if s <= 0:
                    continue
                tied = _tied_cards_for_category(active, spend, cat, seg_currency_ids, sub_ros)
                if not tied or card.id not in {c.id for c in tied}:
                    continue
                n = len(tied)
                m = _multiplier_for_category(card, cat, spend)
                pts = (s / n) * m * seg_fraction
                if pts > 0:
                    cat_totals[cat] = cat_totals.get(cat, 0) + pts

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
    sub_ros_by_card_id: dict[int, float] | None = None,
    for_balance: bool = False,
) -> float:
    """Like _effective_annual_earn but category spend is wallet-allocated (see above).

    for_balance: when True, uses default (non-overridden) CPP for allocation scoring so
    that point totals used for balance display are independent of wallet CPP overrides.
    """
    return (
        calc_annual_point_earn_allocated(card, selected_cards, spend, wallet_currency_ids, sub_ros_by_card_id, for_balance=for_balance)
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
    annual = 0.0
    one_time = 0.0
    for line in card.credit_lines:
        if line.one_time:
            one_time += line.value
        else:
            annual += line.value
    return annual, one_time


def calc_credit_valuation(card: CardData) -> float:
    """Sum of credit dollar values (annual + one-time face amounts) for display."""
    a, o = _credit_annual_and_one_time_totals(card)
    return a + o


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



def _build_segments(
    window_start: date,
    window_end: date,
    selected_cards: list[CardData],
) -> list[tuple[date, date, list[CardData]]]:
    """
    Split [window_start, window_end) into contiguous segments at every card
    open/close/sub-earn boundary.  Returns list of (seg_start, seg_end, active_cards).

    When all cards have wallet_added_date=None, returns a single segment covering
    the full window with all selected cards active — identical to the non-segmented path.
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


def _sub_ros_for_segment(
    card: CardData,
    seg_start: date,
    wallet_currency_ids: set[int],
    for_balance: bool = False,
) -> float:
    """
    Dollar-per-dollar SUB return-on-spend bonus for this card in the given segment.
    Non-zero only when: card has an earnable SUB, is in its SUB window,
    and the SUB has not yet been earned before this segment starts.

    for_balance: when True, uses comparison_cpp (default, non-overridden CPP) so that
    point totals used for balance display are independent of wallet CPP overrides.
    """
    if (
        not card.sub
        or not card.sub_min_spend
        or not card.sub_earnable
        or not card.wallet_added_date
        or card.sub_already_earned
    ):
        return 0.0
    # Safety: boost must never apply before the card's wallet opening date
    if seg_start < card.wallet_added_date:
        return 0.0
    earned = card.sub_projected_earn_date
    if earned is not None and earned <= seg_start:
        return 0.0  # SUB already earned before this segment
    sub_window_end = (
        add_months(card.wallet_added_date, card.sub_months)
        if card.sub_months
        else None
    )
    if sub_window_end is not None and seg_start >= sub_window_end:
        return 0.0  # Past the SUB spending window
    if for_balance:
        sub_value_dollars = card.sub * _effective_currency(card, wallet_currency_ids).comparison_cpp / 100.0
    else:
        sub_value_dollars = card.sub * _effective_cpp(card, wallet_currency_ids) / 100.0
    return sub_value_dollars / card.sub_min_spend


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

    For each segment, the active card set and their SUB ROS boosts may differ.
    Cards only contribute earn for segments where they are active.

    for_balance: when True, uses default (non-overridden) CPP for allocation scoring and
    SUB ROS computation so that point totals used for balance display are CPP-independent.
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
        sub_ros = {c.id: _sub_ros_for_segment(c, seg_start, seg_currency_ids, for_balance=for_balance) for c in active}
        earn = _effective_annual_earn_allocated(
            card, spend, active, seg_currency_ids, sub_ros_by_card_id=sub_ros, for_balance=for_balance
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

    for seg_start, seg_end, active in segments:
        if card not in active:
            continue
        card_ever_active = True
        seg_days = (seg_end - seg_start).days
        seg_currency_ids = {c.currency.id for c in active}
        sub_ros = {c.id: _sub_ros_for_segment(c, seg_start, seg_currency_ids) for c in active}
        sub_ros_for_balance = {c.id: _sub_ros_for_segment(c, seg_start, seg_currency_ids, for_balance=True) for c in active}
        annual_pts = _effective_annual_earn_allocated(
            card, spend, active, seg_currency_ids, sub_ros_by_card_id=sub_ros
        )
        annual_pts_for_balance = _effective_annual_earn_allocated(
            card, spend, active, seg_currency_ids, sub_ros_by_card_id=sub_ros_for_balance, for_balance=True
        )
        eff_currency = _effective_currency(card, seg_currency_ids)
        total_earn_dollars += annual_pts * eff_currency.cents_per_point / 100.0 * seg_days / 365.25
        annualized_earn_pts += annual_pts * seg_days / total_days
        annualized_earn_pts_for_balance += annual_pts_for_balance * seg_days / total_days

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
) -> WalletResult:
    """
    Compute results for every card in `all_cards`.
    Only cards with id in `selected_ids` contribute to totals and currency points.

    window_start / window_end: when provided and any selected card has date info,
    the earn calculation is time-weighted across segments based on card open/close
    and SUB earn boundaries (per-day optimisation).
    """
    selected_cards = [c for c in all_cards if c.id in selected_ids]
    active_wallet_currency_ids = _wallet_currency_ids(selected_cards)

    # Use segmented calculation when window dates are available and any card has date context.
    use_segmentation = (
        window_start is not None
        and window_end is not None
        and any(
            c.wallet_added_date is not None or c.wallet_closed_date is not None
            for c in selected_cards
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
                card, spend, selected_cards, active_wallet_currency_ids
            )
            annual_point_earn_for_balance = _effective_annual_earn_allocated(
                card, spend, selected_cards, active_wallet_currency_ids, for_balance=True
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
            # Time-weighted breakdown: uses the same segment/active-card/SUB-ROS logic as
            # annual_point_earn so categories reflect what the card actually wins per period.
            cat_earn = _segmented_category_earn_breakdown(
                card, selected_cards, spend, window_start, window_end  # type: ignore[arg-type]
            )
        else:
            cat_earn = calc_category_earn_breakdown(card, selected_cards, spend, active_wallet_currency_ids)
            # sub_spend_earn is a separate one-time contribution not captured in annual_point_earn
            # on the simple path; add it explicitly. On the segmented path it is already embedded
            # in segment category earn via the SUB ROS boost.
            if card.sub_earnable and card.sub_spend_earn > 0:
                cat_earn = list(cat_earn) + [("SUB Spend", float(card.sub_spend_earn))]
                cat_earn.sort(key=lambda x: x[1], reverse=True)

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
                sub=card.sub,
                annual_bonus=card.annual_bonus,
                sub_extra_spend=round(sub_extra, 2),
                sub_spend_earn=card.sub_spend_earn,
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
