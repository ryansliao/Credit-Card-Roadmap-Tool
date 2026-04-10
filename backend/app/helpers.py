"""Shared endpoint helpers used across multiple routers."""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Literal, Optional, cast

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import (
    Card,
    CardCategoryMultiplier,
    CardCredit,
    CardMultiplierGroup,
    RotatingCategory,
    Credit,
    Currency,
    Wallet,
    WalletCard,
    WalletCurrencyBalance,
    WalletSpendItem,
    SpendCategory,
)
from .schemas import (
    CardResultSchema,
    CategoryEarnItem,
    WalletCardRead,
    WalletResultSchema,
)
from .date_utils import add_months


# ---------------------------------------------------------------------------
# 404 factories
# ---------------------------------------------------------------------------


def card_404(card_id: int) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Card {card_id} not found")


def wallet_404(wallet_id: int) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Wallet {wallet_id} not found")


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
        acquisition_type=cast(Literal["opened", "product_change"], wc.acquisition_type),
        panel=cast(Literal["in_wallet", "future", "considering"], wc.panel),
    )


# ---------------------------------------------------------------------------
# Selectinload option builders
# ---------------------------------------------------------------------------


def card_load_opts():
    return [
        selectinload(Card.issuer),
        selectinload(Card.co_brand),
        selectinload(Card.currency_obj),
        selectinload(Card.currency_obj).selectinload(Currency.converts_to_currency),
        selectinload(Card.secondary_currency_obj),
        selectinload(Card.secondary_currency_obj).selectinload(Currency.converts_to_currency),
        selectinload(Card.network_tier),
        selectinload(Card.multipliers).selectinload(CardCategoryMultiplier.spend_category),
        selectinload(Card.multiplier_groups).selectinload(CardMultiplierGroup.categories).selectinload(CardCategoryMultiplier.spend_category),
        selectinload(Card.rotating_categories).selectinload(RotatingCategory.spend_category),
    ]


def wallet_load_opts():
    return [
        selectinload(Wallet.wallet_cards).selectinload(WalletCard.card),
    ]


def load_spend_item_opts():
    return [
        selectinload(WalletSpendItem.spend_category).selectinload(SpendCategory.children).selectinload(SpendCategory.children),
    ]


# ---------------------------------------------------------------------------
# Credit library helpers
# ---------------------------------------------------------------------------


async def validate_card_ids(db: AsyncSession, card_ids: list[int]) -> list[int]:
    """Deduplicate, validate that each card exists, return a sorted list."""
    unique = sorted(set(card_ids))
    if not unique:
        return []
    result = await db.execute(select(Card.id).where(Card.id.in_(unique)))
    found = {row[0] for row in result.all()}
    missing = [cid for cid in unique if cid not in found]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown card id(s): {missing}",
        )
    return unique


async def set_credit_card_links(
    db: AsyncSession,
    credit: Credit,
    card_ids: list[int],
    card_values: dict[int, float] | None = None,
) -> None:
    """Replace this credit's card_credit_cards rows with the given card_ids.

    ``card_values`` maps card_id -> issuer-stated dollar value for that card.
    Omitted cards get NULL (inherit from ``credits.value``).
    """
    # Preserve existing per-card values for cards that remain
    existing_values: dict[int, float | None] = {}
    for link in credit.card_links:
        existing_values[link.card_id] = link.value

    await db.execute(
        delete(CardCredit).where(CardCredit.credit_id == credit.id)
    )
    merged_values = {**existing_values, **(card_values or {})}
    for cid in card_ids:
        db.add(CardCredit(
            credit_id=credit.id,
            card_id=cid,
            value=merged_values.get(cid),
        ))


# ---------------------------------------------------------------------------
# Wallet currency helpers
# ---------------------------------------------------------------------------


async def effective_earn_currency_ids_for_wallet(
    db: AsyncSession,
    wallet_id: int,
) -> set[int]:
    """
    Currency IDs this wallet's in-wallet cards effectively earn (upgrade rule
    matches calculator: e.g. UR Cash -> UR when a UR card is also in the wallet).
    Considering cards are excluded -- only in_wallet and future cards count.
    """
    result = await db.execute(
        select(WalletCard)
        .options(
            selectinload(WalletCard.card)
            .selectinload(Card.currency_obj)
            .selectinload(Currency.converts_to_currency),
        )
        .where(
            WalletCard.wallet_id == wallet_id,
            WalletCard.panel.in_(("in_wallet", "future")),
        )
    )
    wcs = list(result.scalars().all())
    if not wcs:
        return set()

    wallet_currency_ids = {wc.card.currency_id for wc in wcs}
    effective_ids: set[int] = set()
    for wc in wcs:
        cur = wc.card.currency_obj
        conv = cur.converts_to_currency
        if conv is not None and conv.id in wallet_currency_ids:
            effective_ids.add(conv.id)
        else:
            effective_ids.add(cur.id)
    return effective_ids


async def ensure_wallet_currency_rows_for_earning_currencies(
    db: AsyncSession,
    wallet_id: int,
) -> None:
    """
    Create WalletCurrencyBalance rows (if missing) for each effective earn currency
    for cards in this wallet.
    """
    effective_ids = await effective_earn_currency_ids_for_wallet(db, wallet_id)
    if not effective_ids:
        return

    today = date.today()
    for cid in effective_ids:
        ex = await db.execute(
            select(WalletCurrencyBalance).where(
                WalletCurrencyBalance.wallet_id == wallet_id,
                WalletCurrencyBalance.currency_id == cid,
            )
        )
        if ex.scalar_one_or_none():
            continue
        db.add(
            WalletCurrencyBalance(
                wallet_id=wallet_id,
                currency_id=cid,
                initial_balance=0.0,
                projection_earn=0.0,
                balance=0.0,
                user_tracked=False,
                updated_date=today,
            )
        )


async def sync_wallet_balances_from_currency_pts(
    db: AsyncSession,
    wallet_id: int,
    currency_pts_by_id: dict[int, float],
) -> None:
    """
    Persist projection-period earn per currency and set balance = initial + earn.
    """
    today = date.today()
    valid_ids = set((await db.execute(select(Currency.id))).scalars().all())
    active_currency_ids = await effective_earn_currency_ids_for_wallet(db, wallet_id)

    res = await db.execute(
        select(WalletCurrencyBalance)
        .options(selectinload(WalletCurrencyBalance.currency))
        .where(WalletCurrencyBalance.wallet_id == wallet_id)
    )
    rows = list(res.scalars().all())
    by_cid = {r.currency_id: r for r in rows}

    for row in rows:
        if row.currency_id not in active_currency_ids and not row.user_tracked:
            await db.delete(row)
            continue
        earn = float(currency_pts_by_id.get(row.currency_id, 0.0))
        row.projection_earn = earn
        row.balance = round(row.initial_balance + earn, 4)
        row.updated_date = today

    for cid, earn in currency_pts_by_id.items():
        if earn <= 0 or cid not in valid_ids:
            continue
        if cid in by_cid:
            continue
        new_row = WalletCurrencyBalance(
            wallet_id=wallet_id,
            currency_id=cid,
            initial_balance=0.0,
            projection_earn=float(earn),
            balance=float(earn),
            user_tracked=False,
            updated_date=today,
        )
        db.add(new_row)
        by_cid[cid] = new_row


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


def wallet_to_schema(wallet) -> WalletResultSchema:
    card_schemas = [
        CardResultSchema(
            card_id=cr.card_id,
            card_name=cr.card_name,
            selected=cr.selected,
            effective_annual_fee=cr.effective_annual_fee,
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
