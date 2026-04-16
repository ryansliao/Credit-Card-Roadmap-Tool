"""Shared endpoint helpers used across multiple routers.

Note: Data access functions have been moved to the services layer.
This module retains only schema builders, 404 factories, and pure utility functions.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Literal, Optional, cast

from .models import Card, WalletCard
from .schemas import (
    CardResultSchema,
    CategoryEarnItem,
    WalletCardRead,
    WalletResultSchema,
)
from .date_utils import add_months


# ---------------------------------------------------------------------------
# WalletCard -> WalletCardRead builder
# ---------------------------------------------------------------------------


def wc_read(wc: WalletCard, card: Card) -> WalletCardRead:
    """
    Build a WalletCardRead for API responses.

    SUB and fee fields fall back to the library Card when the wallet row stores
    null (inherit defaults). The database row is unchanged; only the read model
    exposes effective values for clients.
    """
    def _inh(wv, cv):
        return wv if wv is not None else cv

    return WalletCardRead(
        id=wc.id,
        wallet_id=wc.wallet_id,
        card_id=wc.card_id,
        card_name=card.name,
        transfer_enabler=bool(getattr(card, "transfer_enabler", False)),
        photo_slug=getattr(card, "photo_slug", None),
        issuer_name=card.issuer.name if card.issuer else None,
        network_tier_name=card.network_tier.name if getattr(card, "network_tier", None) else None,
        added_date=wc.added_date,
        sub_points=_inh(wc.sub_points, card.sub_points),
        sub_min_spend=_inh(wc.sub_min_spend, card.sub_min_spend),
        sub_months=_inh(wc.sub_months, card.sub_months),
        sub_spend_earn=_inh(wc.sub_spend_earn, card.sub_spend_earn),
        annual_bonus=_inh(wc.annual_bonus, card.annual_bonus),
        annual_bonus_percent=_inh(wc.annual_bonus_percent, card.annual_bonus_percent),
        annual_bonus_first_year_only=_inh(wc.annual_bonus_first_year_only, card.annual_bonus_first_year_only),
        years_counted=wc.years_counted,
        annual_fee=_inh(wc.annual_fee, card.annual_fee),
        first_year_fee=_inh(wc.first_year_fee, card.first_year_fee),
        sub_earned_date=wc.sub_earned_date,
        sub_projected_earn_date=wc.sub_projected_earn_date,
        closed_date=wc.closed_date,
        product_changed_date=wc.product_changed_date,
        acquisition_type=cast(Literal["opened", "product_change"], wc.acquisition_type),
        pc_from_card_id=wc.pc_from_card_id,
        panel=cast(Literal["in_wallet", "future_cards", "considering"], wc.panel),
        credit_total=sum(c.value for c in wc.credit_overrides_rows) if wc.credit_overrides_rows else 0,
    )


# ---------------------------------------------------------------------------
# SUB date helpers
# ---------------------------------------------------------------------------


def is_sub_earnable(
    sub_min_spend: Optional[int],
    sub_months: Optional[int],
    daily_spend_rate: float,
) -> bool:
    """Return True if the SUB min spend can be reached within the SUB window."""
    if not sub_min_spend:
        return True
    if daily_spend_rate <= 0:
        return False
    if not sub_months:
        return True
    reachable = daily_spend_rate * (sub_months * 30.44)
    return reachable >= sub_min_spend


def projected_sub_earn_date(
    added_date: date,
    sub_min_spend: Optional[int],
    sub_months: Optional[int],
    daily_spend_rate: float,
) -> Optional[date]:
    """Project the date when the SUB will be earned based on daily spend rate."""
    if not sub_min_spend or daily_spend_rate <= 0:
        return None
    days_to_earn = math.ceil(sub_min_spend / daily_spend_rate)
    projected = added_date + timedelta(days=days_to_earn)
    if sub_months:
        window_end = add_months(added_date, sub_months)
        if projected > window_end:
            return None
    return projected


def months_in_half_open_interval(start: date, end: date) -> int:
    """Number of calendar months spanned by [start, end)."""
    if end <= start:
        raise ValueError("end must be after start")
    total = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        total -= 1
    return max(1, total)


def years_counted_from_total_months(total_months: int) -> int:
    full = total_months // 12
    rem = total_months % 12
    return max(1, full + (1 if rem >= 6 else 0))


# ---------------------------------------------------------------------------
# Schema conversion helper
# ---------------------------------------------------------------------------


def wallet_to_schema(wallet, photo_slugs: dict[int, str | None] | None = None) -> WalletResultSchema:
    card_schemas = [
        CardResultSchema(
            card_id=cr.card_id,
            card_name=cr.card_name,
            selected=cr.selected,
            effective_annual_fee=cr.effective_annual_fee,
            card_effective_annual_fee=cr.card_effective_annual_fee,
            card_active_years=cr.card_active_years,
            total_points=cr.total_points,
            annual_point_earn=cr.annual_point_earn,
            credit_valuation=cr.credit_valuation,
            annual_fee=cr.annual_fee,
            first_year_fee=cr.first_year_fee,
            sub_points=cr.sub_points,
            annual_bonus=cr.annual_bonus,
            annual_bonus_percent=cr.annual_bonus_percent,
            annual_bonus_first_year_only=cr.annual_bonus_first_year_only,
            sub_extra_spend=cr.sub_extra_spend,
            sub_spend_earn=cr.sub_spend_earn,
            sub_opp_cost_dollars=cr.sub_opp_cost_dollars,
            sub_opp_cost_gross_dollars=cr.sub_opp_cost_gross_dollars,
            avg_spend_multiplier=cr.avg_spend_multiplier,
            cents_per_point=cr.cents_per_point,
            effective_currency_name=cr.effective_currency_name,
            effective_currency_id=cr.effective_currency_id,
            effective_reward_kind=cr.effective_reward_kind,
            category_earn=[
                CategoryEarnItem(category=cat, points=pts)
                for cat, pts in cr.category_earn
            ],
            secondary_currency_earn=cr.secondary_currency_earn,
            secondary_currency_name=cr.secondary_currency_name,
            secondary_currency_id=cr.secondary_currency_id,
            accelerator_activations=cr.accelerator_activations,
            accelerator_bonus_points=cr.accelerator_bonus_points,
            accelerator_cost_points=cr.accelerator_cost_points,
            secondary_currency_net_earn=cr.secondary_currency_net_earn,
            secondary_currency_value_dollars=cr.secondary_currency_value_dollars,
            photo_slug=photo_slugs.get(cr.card_id) if photo_slugs else None,
        )
        for cr in wallet.card_results
    ]

    return WalletResultSchema(
        years_counted=wallet.years_counted,
        total_effective_annual_fee=wallet.total_effective_annual_fee,
        total_points_earned=wallet.total_points_earned,
        total_annual_pts=wallet.total_annual_pts,
        total_cash_reward_dollars=wallet.total_cash_reward_dollars,
        total_reward_value_usd=wallet.total_reward_value_usd,
        currency_pts=wallet.currency_pts,
        currency_pts_by_id=wallet.currency_pts_by_id,
        card_results=card_schemas,
    )
