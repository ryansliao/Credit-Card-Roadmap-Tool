"""Credits, SUB opportunity cost, and total-points helpers.

All per-card dollar/point aggregation that isn't straight category
allocation: credit valuation, SUB extra-spend feasibility, best alternative
earn rate, opportunity cost, and total points over the projection window.
"""
from __future__ import annotations

from typing import Optional

from .allocation import (
    _effective_annual_earn_allocated,
    _portal_blended_multiplier,
    _tied_cards_for_category,
)
from .currency import (
    _comparison_cpp,
    _conversion_rate,
    _effective_currency,
)
from .multipliers import (
    _all_other_multiplier,
    _build_effective_multipliers,
    _first_year_pct_bonus,
    _multiplier_for_category,
)
from .types import CardData


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
            _portal_blended_multiplier(c, cat, _multiplier_for_category(c, cat, spend))
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
