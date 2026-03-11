"""
Credit card value calculation engine.

Terminology
-----------
- CardData    : all static data for a card, including nested CurrencyData
- CurrencyData: issuer currency with its CPP, transferability, and comparison factor
- spend       : dict of {category: annual_spend_dollars}
- cpp         : cents per point (from the effective currency, accounting for boost)
- EV          : expected value (dollars)
- SUB         : sign-up bonus
- years       : years_counted
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data containers (plain dataclasses — no DB dependency)
# ---------------------------------------------------------------------------


@dataclass
class CurrencyData:
    """Snapshot of a reward currency for use in the calculator engine."""

    id: int
    name: str
    issuer_name: str
    cents_per_point: float
    is_cashback: bool
    is_transferable: bool


@dataclass
class CardData:
    """All static data for one card, ready for the calculator engine."""

    id: int
    name: str
    issuer_name: str              # denormalised for display

    # Default currency this card earns (may be a cashback currency)
    currency: CurrencyData

    annual_fee: float
    sub_points: int
    sub_min_spend: Optional[int]
    sub_months: Optional[int]
    sub_spend_points: int
    annual_bonus_points: int

    # Ecosystem-based conversion: when a key card for one of these ecosystems is in the wallet,
    # this card earns the given points currency instead of its default.
    # Map ecosystem_id -> CurrencyData (beneficiary conversion target).
    ecosystem_beneficiary_currency: dict[int, CurrencyData] = field(default_factory=dict)

    # Ecosystem ids for which this card is a key card (unlocks conversion when in wallet).
    ecosystem_ids_where_key: set[int] = field(default_factory=set)

    # category -> multiplier
    multipliers: dict[str, float] = field(default_factory=dict)
    # credit_name -> value in dollars
    credits: dict[str, float] = field(default_factory=dict)


@dataclass
class CardResult:
    """Per-card outputs from the calculator, zeroed when card is not selected."""

    card_id: int
    card_name: str
    selected: bool
    annual_ev: float = 0.0
    second_year_ev: float = 0.0
    total_points: float = 0.0
    annual_point_earn: float = 0.0
    credit_valuation: float = 0.0
    annual_fee: float = 0.0
    sub_points: int = 0
    annual_bonus_points: int = 0
    sub_extra_spend: float = 0.0
    sub_spend_points: int = 0
    # Opportunity cost: net dollar value foregone on the rest of the wallet
    # to cover the SUB extra spend (gross opp cost minus sub_spend_points value)
    sub_opp_cost_dollars: float = 0.0
    # Gross dollar opportunity cost (best alternative earn on the extra spend,
    # before crediting back the sub_spend_points earned on the target card)
    sub_opp_cost_gross_dollars: float = 0.0
    avg_spend_multiplier: float = 0.0
    cents_per_point: float = 0.0
    # Effective currency name (may differ from default when boost is active)
    effective_currency_name: str = ""


@dataclass
class WalletResult:
    """Aggregated wallet outputs."""

    years_counted: int
    total_annual_ev: float
    total_points_earned: float
    total_annual_pts: float
    # Dynamic map of currency_name -> annual points earned in that currency.
    # Cashback cards whose boost is active will accumulate under the boosted
    # currency name (e.g. "Chase UR"), not their default ("Chase UR Cash").
    currency_pts: dict[str, float] = field(default_factory=dict)
    card_results: list[CardResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Ecosystem conversion helpers
# ---------------------------------------------------------------------------


def _ecosystems_with_key_card(selected_cards: list[CardData]) -> set[int]:
    """Ecosystem ids that have at least one selected card that is a key card for that ecosystem."""
    out: set[int] = set()
    for c in selected_cards:
        out |= c.ecosystem_ids_where_key
    return out


def _effective_currency(
    card: CardData, ecosystems_with_key: set[int]
) -> CurrencyData:
    """
    Return the currency this card actually earns in, given the wallet state.
    When this card is a beneficiary in an ecosystem that has a key card in the wallet,
    return that ecosystem's points currency; otherwise return primary currency.
    """
    for eco_id, points_currency in card.ecosystem_beneficiary_currency.items():
        if eco_id in ecosystems_with_key:
            return points_currency
    return card.currency


def _effective_cpp(card: CardData, ecosystems_with_key: set[int]) -> float:
    return _effective_currency(card, ecosystems_with_key).cents_per_point


# ---------------------------------------------------------------------------
# Core per-card calculations
# ---------------------------------------------------------------------------


def calc_annual_point_earn(
    card: CardData,
    spend: dict[str, float],
) -> float:
    """Total points earned per year from category spend plus any annual bonus."""
    cat_pts = sum(spend.get(cat, 0.0) * mult for cat, mult in card.multipliers.items())
    return float(card.annual_bonus_points) + cat_pts


def calc_credit_valuation(card: CardData) -> float:
    """Total dollar value of all annual credits / perks."""
    return sum(card.credits.values())


def calc_2nd_year_ev(
    card: CardData,
    spend: dict[str, float],
    ecosystems_with_key: set[int],
) -> float:
    """
    Steady-state annual EV (no SUB amortisation).
    Formula: annual_earn / 100 * cpp + credits - fee
    """
    currency = _effective_currency(card, ecosystems_with_key)
    annual_earn = calc_annual_point_earn(card, spend)
    credits = calc_credit_valuation(card)
    return annual_earn / 100 * currency.cents_per_point + credits - card.annual_fee


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
    natural_spend = sum(v for cat, v in spend.items() if card.multipliers.get(cat, 0) > 0)
    return max(0.0, card.sub_min_spend - natural_spend)


def _best_wallet_earn_rate_dollars(
    card: CardData,
    selected_cards: list[CardData],
    spend: dict[str, float],
    ecosystems_with_key: set[int],
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
            c.multipliers.get(cat, 1.0) * _effective_cpp(c, ecosystems_with_key) / 100.0
            for c in others
        )
        total_spend += s
        total_best_earn += s * best_rate

    return total_best_earn / total_spend if total_spend > 0 else 0.0


def calc_sub_opportunity_cost(
    card: CardData,
    selected_cards: list[CardData],
    spend: dict[str, float],
    ecosystems_with_key: set[int],
) -> tuple[float, float]:
    """
    Dollar opportunity cost of redirecting extra SUB spend from the rest of
    the wallet to this card.

    Returns (gross_opp_cost_dollars, net_opp_cost_dollars):
      gross = extra_spend × best_wallet_earn_rate
      net   = gross − value_of_sub_spend_points_earned_on_this_card
              (i.e. what you truly lose after accounting for what the new card
               earns on that same spend)
    """
    extra_spend = calc_sub_extra_spend(card, spend)
    if extra_spend <= 0:
        return 0.0, 0.0

    best_rate = _best_wallet_earn_rate_dollars(card, selected_cards, spend, ecosystems_with_key)
    gross = extra_spend * best_rate

    currency = _effective_currency(card, ecosystems_with_key)
    sub_spend_value = card.sub_spend_points * currency.cents_per_point / 100.0
    net = max(0.0, gross - sub_spend_value)

    return round(gross, 4), round(net, 4)


def calc_avg_spend_multiplier(
    card: CardData,
    spend: dict[str, float],
) -> float:
    """Spend-weighted average multiplier across categories with positive spend."""
    total_spend = 0.0
    total_pts = 0.0
    for cat, s in spend.items():
        mult = card.multipliers.get(cat, 1.0)
        if s > 0:
            total_spend += s
            total_pts += s * mult
    return total_pts / total_spend if total_spend > 0 else 0.0


def calc_total_points(
    card: CardData,
    spend: dict[str, float],
    years: int,
    ecosystems_with_key: set[int],
) -> float:
    """
    Total points over `years` including SUB and annual bonuses.
    """
    currency = _effective_currency(card, ecosystems_with_key)
    annual_earn = calc_annual_point_earn(card, spend)
    _, net_opp = calc_sub_opportunity_cost(card, [card], spend, ecosystems_with_key)

    # Convert net opp cost back to a points deduction in the card's currency
    cpp = currency.cents_per_point
    net_opp_pts = (net_opp / (cpp / 100.0)) if cpp > 0 else 0.0

    total = (
        annual_earn
        + card.sub_spend_points
        + card.sub_points
        - net_opp_pts
    ) + annual_earn * (years - 1)
    return total


def calc_annual_ev(
    card: CardData,
    spend: dict[str, float],
    years: int,
    ecosystems_with_key: set[int],
) -> float:
    """
    Annual EV over `years`, amortising the SUB.

    Formula:
      ( (annual_earn + sub_spend_pts) / 100 * cpp * years
        + sub_pts / 100
        + annual_bonus_pts * (years - 1)
        + credits
        - fee
      ) / years
    """
    currency = _effective_currency(card, ecosystems_with_key)
    cpp = currency.cents_per_point
    annual_earn = calc_annual_point_earn(card, spend)
    credits = calc_credit_valuation(card)

    value = (
        ((annual_earn + card.sub_spend_points) / 100 * cpp) * years
        + card.sub_points / 100
        + card.annual_bonus_points * (years - 1)
        + credits
        - card.annual_fee
    ) / years
    return value


# ---------------------------------------------------------------------------
# Wallet-level aggregation
# ---------------------------------------------------------------------------


def compute_wallet(
    all_cards: list[CardData],
    selected_ids: set[int],
    spend: dict[str, float],
    years: int,
) -> WalletResult:
    """
    Compute results for every card in `all_cards`.
    Only cards with id in `selected_ids` contribute to EV and currency totals.
    """
    selected_cards = [c for c in all_cards if c.id in selected_ids]
    active_ecosystems = _ecosystems_with_key_card(selected_cards)

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
                    sub_points=card.sub_points,
                    cents_per_point=card.currency.cents_per_point,
                    effective_currency_name=card.currency.name,
                )
            )
            continue

        eff_currency = _effective_currency(card, active_ecosystems)
        annual_ev = calc_annual_ev(card, spend, years, active_ecosystems)
        second_year_ev = calc_2nd_year_ev(card, spend, active_ecosystems)
        annual_point_earn = calc_annual_point_earn(card, spend)
        total_points = calc_total_points(card, spend, years, active_ecosystems)
        credit_val = calc_credit_valuation(card)
        sub_extra = calc_sub_extra_spend(card, spend)
        gross_opp, net_opp = calc_sub_opportunity_cost(card, selected_cards, spend, active_ecosystems)
        avg_mult = calc_avg_spend_multiplier(card, spend)

        card_results.append(
            CardResult(
                card_id=card.id,
                card_name=card.name,
                selected=True,
                annual_ev=round(annual_ev, 4),
                second_year_ev=round(second_year_ev, 4),
                total_points=round(total_points, 2),
                annual_point_earn=round(annual_point_earn, 2),
                credit_valuation=round(credit_val, 2),
                annual_fee=card.annual_fee,
                sub_points=card.sub_points,
                annual_bonus_points=card.annual_bonus_points,
                sub_extra_spend=round(sub_extra, 2),
                sub_spend_points=card.sub_spend_points,
                sub_opp_cost_dollars=net_opp,
                sub_opp_cost_gross_dollars=gross_opp,
                avg_spend_multiplier=round(avg_mult, 4),
                cents_per_point=eff_currency.cents_per_point,
                effective_currency_name=eff_currency.name,
            )
        )

    selected_results = [r for r in card_results if r.selected]
    total_annual_ev = round(sum(r.annual_ev for r in selected_results), 4)
    total_points_earned = round(sum(r.total_points for r in selected_results), 2)
    total_annual_pts = round(sum(r.annual_point_earn for r in selected_results), 2)

    # Dynamic currency totals — grouped by effective currency name
    currency_pts: dict[str, float] = {}
    for card in selected_cards:
        eff = _effective_currency(card, active_ecosystems)
        earn = calc_annual_point_earn(card, spend)
        currency_pts[eff.name] = currency_pts.get(eff.name, 0.0) + earn

    return WalletResult(
        years_counted=years,
        total_annual_ev=total_annual_ev,
        total_points_earned=total_points_earned,
        total_annual_pts=total_annual_pts,
        currency_pts=currency_pts,
        card_results=card_results,
    )
