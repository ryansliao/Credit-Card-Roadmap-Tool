"""Secondary currency (Bilt-style) and simple-path average annual EV.

- ``_calc_secondary_currency``: per-card secondary-currency earn + accelerator
  net value, honoring the housing-spend conversion cap.
- ``_average_annual_net_dollars``: simple-path per-card EV formula. The
  segmented path lives in ``segmented_ev.py`` and uses a different
  time-weighted LP-backed earn instead.
"""
from __future__ import annotations

from typing import Optional

from .allocation import (
    _effective_annual_earn_allocated,
    calc_annual_allocated_spend,
)
from .credits import _credit_annual_and_one_time_totals
from .currency import _conversion_rate, _effective_currency
from .multipliers import _first_year_pct_bonus
from .types import CardData, _SecondaryResult


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

    # Secondary currency earn: rate is a fraction (e.g. 0.04 for 4%). One
    # secondary-currency "unit" is valued at ``secondary_currency.cents_per_point``
    # cents, so rate × spend gives the unit count directly (e.g. Bilt Cash at
    # CPP=100 means 1 unit = $1, and $100 spend × 0.04 = 4 units = $4).
    annual_secondary_pts = allocated_annual_spend * card.secondary_currency_rate

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
    convertible_pts = convertible_spend * card.secondary_currency_rate

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
    # Secondary-currency SUB (e.g. Bilt Cash): valued at the secondary currency's
    # cents_per_point. Honors the housing-spend cap — if the card has a positive
    # cap_rate and the wallet has no housing spend, the SUB is not redeemable.
    effective_sub_secondary_dollars = 0.0
    if card.sub_earnable and card.sub_secondary_points > 0 and card.secondary_currency is not None:
        cap_blocks = card.secondary_currency_cap_rate > 0 and housing_spend <= 0
        if not cap_blocks:
            effective_sub_secondary_dollars = card.sub_secondary_points * card.secondary_currency.cents_per_point / 100.0
    fee_y1 = card.first_year_fee if card.first_year_fee is not None else card.annual_fee
    # Fees hit at month 13 after opening, then every 12 months.
    total_months = years * 12
    if total_months < 13:
        total_fees = 0.0
    else:
        num_fees = (total_months - 13) // 12 + 1
        total_fees = fee_y1 + (num_fees - 1) * card.annual_fee
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
    allocated_spend = calc_annual_allocated_spend(
        card, selected_cards, spend, wallet_currency_ids,
        exclude_categories=card.secondary_ineligible_categories or None,
    )
    sec = _calc_secondary_currency(card, allocated_spend, wallet_currency_ids, housing_spend=housing_spend)
    # Accelerator bonus points are primary currency points; value them at primary CPP.
    accel_bonus_dollars_annual = sec.bonus_pts_annual * cpp / 100.0

    value = (
        (effective_earn / 100 * cpp) * years
        + effective_sub / 100 * cpp
        + effective_sub_pts * cpp / 100
        + effective_sub_cash
        + effective_sub_secondary_dollars
        + fy_bonus_eff / 100 * cpp
        + annual_credits * years
        + annual_credits_skip * max(years - 1, 0)
        + one_time_credits
        + sec.dollar_value_annual * years
        + accel_bonus_dollars_annual * years
        - total_fees
    ) / years
    return value
