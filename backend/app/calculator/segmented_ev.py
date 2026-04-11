"""Segmented (time-weighted) per-card net value.

The segmented EV path is used whenever the wallet has explicit window dates
and at least one card has a ``wallet_added_date``. It splits the window into
segments via ``_build_segments``, optimally allocates each segment's spend
via ``_solve_segment_allocation_lp`` (falling back to the per-card greedy
when scipy is unavailable), and then accumulates earn/credits/fees per day
so the total respects card open/close dates, SUB-ROS boost windows, and
cap-period boundaries.
"""
from __future__ import annotations

from datetime import date

from ..date_utils import add_months
from .allocation import (
    _effective_annual_earn_allocated,
    calc_annual_allocated_spend,
)
from .credits import _credit_annual_and_one_time_totals
from .currency import (
    _conversion_rate,
    _effective_currency,
    _wallet_currency_ids,
)
from .multipliers import _first_year_pct_bonus, _pct_bonus
from .secondary import _average_annual_net_dollars, _calc_secondary_currency
from .segments import (
    _build_segments,
    _segment_card_earn_pts_per_cat,
    _sub_priority_ids_for_segment,
)
from .types import CardData


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
    # Secondary-currency SUB (e.g. Bilt Cash): value at face via the secondary
    # currency's CPP, subject to the same housing-spend cap as earned secondary.
    if card.sub_earnable and card.sub_secondary_points > 0 and card.secondary_currency is not None:
        cap_blocks = card.secondary_currency_cap_rate > 0 and housing_spend <= 0
        if not cap_blocks:
            total_credits += card.sub_secondary_points * card.secondary_currency.cents_per_point / 100.0

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
        sec = _calc_secondary_currency(card, annual_alloc, active_wallet_currency_ids, housing_spend=housing_spend)
        total_earn_dollars += sec.dollar_value_annual * active_fraction * total_years
        # Accelerator bonus: extra primary pts valued at primary CPP
        eff_currency_sec = _effective_currency(card, active_wallet_currency_ids)
        total_earn_dollars += sec.bonus_pts_annual * eff_currency_sec.cents_per_point / 100.0 * active_fraction * total_years

    total_net = total_earn_dollars + total_credits - total_fee
    return total_net / total_years, annualized_earn_pts, annualized_earn_pts_for_balance
