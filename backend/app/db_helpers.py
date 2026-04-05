"""
Runtime DB -> calculator projection helpers.

These helpers do not own reference data or seed content; they only read the
current database state produced by the workbook sync and the running app.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .calculator import CardData, CreditLine, CurrencyData
from .constants import ALL_OTHER_CATEGORY
from .models import (
    Card,
    CardCategoryMultiplier,
    CardMultiplierGroup,
    Currency,
    SpendCategory,
    Wallet,
    WalletCardCredit,
    WalletCardMultiplier,
    WalletCurrencyCpp,
    WalletSpendCategory,
    WalletSpendCategoryMapping,
    WalletSpendItem,
)

# Re-export for callers that import this name from db_helpers.
ALL_OTHER_SPEND_NAME = ALL_OTHER_CATEGORY

if TYPE_CHECKING:
    from .models import WalletCard


def _currency_data(
    orm_currency: Currency,
    cpp_overrides: dict[int, float] | None = None,
) -> CurrencyData:
    """Convert a Currency ORM object to a CurrencyData (optional CPP overrides by currency id).

    Overrides apply to this row and any nested ``converts_to_currency`` (same as the calculator's
    effective-currency CPP when a card upgrades).
    """
    oid = orm_currency.id
    cpp_override = cpp_overrides.get(oid) if cpp_overrides else None
    rk = getattr(orm_currency, "reward_kind", None) or "points"
    default_cpp = float(orm_currency.cents_per_point)
    if rk == "cash":
        cpp = default_cpp
    else:
        cpp = (
            float(cpp_override)
            if cpp_override is not None
            else default_cpp
        )
    converts_to: CurrencyData | None = None
    if orm_currency.converts_to_currency is not None:
        converts_to = _currency_data(orm_currency.converts_to_currency, cpp_overrides)
    converts_at_rate = getattr(orm_currency, "converts_at_rate", None)
    return CurrencyData(
        id=orm_currency.id,
        name=orm_currency.name,
        reward_kind=rk,
        cents_per_point=cpp,
        comparison_cpp=default_cpp,
        cash_transfer_rate=orm_currency.cash_transfer_rate if orm_currency.cash_transfer_rate is not None else 1.0,
        partner_transfer_rate=orm_currency.partner_transfer_rate,
        converts_to_currency=converts_to,
        converts_at_rate=converts_at_rate if converts_at_rate is not None else 1.0,
    )


async def load_wallet_cpp_overrides(
    session: AsyncSession, wallet_id: int
) -> dict[int, float]:
    """Load wallet-scoped cents-per-point overrides: currency_id -> cents_per_point."""
    result = await session.execute(
        select(WalletCurrencyCpp).where(WalletCurrencyCpp.wallet_id == wallet_id)
    )
    rows = result.scalars().all()
    return {row.currency_id: row.cents_per_point for row in rows}


async def load_card_data(
    session: AsyncSession, cpp_overrides: dict[int, float] | None = None
) -> list[CardData]:
    """Load all cards with their full relationship tree as CardData objects.
    If cpp_overrides is provided, those values override each card's currency CPP.
    """
    result = await session.execute(
        select(Card).options(
            selectinload(Card.issuer),
            selectinload(Card.currency_obj)
            .selectinload(Currency.converts_to_currency),
            selectinload(Card.multipliers).selectinload(CardCategoryMultiplier.spend_category),
            selectinload(Card.multiplier_groups).selectinload(CardMultiplierGroup.categories).selectinload(CardCategoryMultiplier.spend_category),
            selectinload(Card.credits),
        )
    )
    cards = result.scalars().all()

    out: list[CardData] = []
    for card in cards:
        currency = _currency_data(card.currency_obj, cpp_overrides)

        multipliers = {m.category: m.multiplier for m in card.multipliers}
        portal_categories: set[str] = {
            m.category for m in card.multipliers if getattr(m, "is_portal", False)
        }
        # Group metadata for top-N: (multiplier, categories list, top_n_categories or None)
        multiplier_groups_list: list[tuple[float, list[str], int | None]] = []
        for grp in getattr(card, "multiplier_groups", []) or []:
            top_n = getattr(grp, "top_n_categories", None)
            if top_n is None and getattr(grp, "top_category_only", False):
                top_n = 1
            cats = [c.category for c in getattr(grp, "categories", []) if getattr(c, "category", None)]
            multiplier_groups_list.append((grp.multiplier, cats, top_n))
        credit_lines = [
            CreditLine(
                library_credit_id=c.id,
                name=c.credit_name,
                value=c.credit_value,
                one_time=bool(getattr(c, "is_one_time", False)),
            )
            for c in card.credits
        ]

        out.append(
            CardData(
                id=card.id,
                name=card.name,
                issuer_name=card.issuer.name,
                currency=currency,
                annual_fee=card.annual_fee,
                first_year_fee=card.first_year_fee,
                sub=card.sub if card.sub is not None else 0,
                sub_min_spend=card.sub_min_spend,
                sub_months=card.sub_months,
                sub_spend_earn=card.sub_spend_earn if card.sub_spend_earn is not None else 0,
                annual_bonus=card.annual_bonus if card.annual_bonus is not None else 0,
                multipliers=multipliers,
                multiplier_groups=multiplier_groups_list,
                credit_lines=credit_lines,
                portal_categories=portal_categories,
            )
        )
    return out


async def ensure_all_other_wallet_spend_category(session: AsyncSession, wallet_id: int) -> None:
    """
    If the wallet has no spend category named 'All Other', create one with amount 0
    and a single mapping: 100% to the global SpendCategory 'All Other'.
    """
    wallet_row = await session.execute(select(Wallet).where(Wallet.id == wallet_id))
    if wallet_row.scalar_one_or_none() is None:
        return
    sc_result = await session.execute(
        select(SpendCategory).where(SpendCategory.category == ALL_OTHER_SPEND_NAME)
    )
    sc = sc_result.scalar_one_or_none()
    if sc is None:
        return
    existing = await session.execute(
        select(WalletSpendCategory).where(
            WalletSpendCategory.wallet_id == wallet_id,
            WalletSpendCategory.name == ALL_OTHER_SPEND_NAME,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return
    wsc = WalletSpendCategory(
        wallet_id=wallet_id, name=ALL_OTHER_SPEND_NAME, amount=0.0
    )
    session.add(wsc)
    await session.flush()
    session.add(
        WalletSpendCategoryMapping(
            wallet_spend_category_id=wsc.id,
            spend_category_id=sc.id,
            allocation=0.0,
        )
    )


async def load_wallet_spend(
    session: AsyncSession,
    wallet_id: int,
) -> dict[str, float]:
    """
    Load spend dict for a wallet by summing WalletSpendCategoryMapping allocations per card category.
    Legacy function for backward compatibility with old WalletSpendCategory rows.
    """
    result = await session.execute(
        select(WalletSpendCategory)
        .options(
            selectinload(WalletSpendCategory.mappings).selectinload(WalletSpendCategoryMapping.spend_category)
        )
        .where(WalletSpendCategory.wallet_id == wallet_id)
    )
    wallet_spend_categories = result.scalars().all()
    spend: dict[str, float] = {}
    for wsc in wallet_spend_categories:
        for mapping in wsc.mappings:
            if mapping.spend_category:
                cat_name = mapping.spend_category.category
                spend[cat_name] = spend.get(cat_name, 0.0) + mapping.allocation
    return spend


async def ensure_all_other_wallet_spend_item(session: AsyncSession, wallet_id: int) -> None:
    """
    Ensure the wallet has a WalletSpendItem for the 'All Other' SpendCategory.
    Creates one with amount=0 if missing.
    """
    wallet_row = await session.execute(select(Wallet).where(Wallet.id == wallet_id))
    if wallet_row.scalar_one_or_none() is None:
        return
    sc_result = await session.execute(
        select(SpendCategory).where(SpendCategory.category == ALL_OTHER_SPEND_NAME)
    )
    sc = sc_result.scalar_one_or_none()
    if sc is None:
        return
    existing = await session.execute(
        select(WalletSpendItem).where(
            WalletSpendItem.wallet_id == wallet_id,
            WalletSpendItem.spend_category_id == sc.id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return
    session.add(WalletSpendItem(wallet_id=wallet_id, spend_category_id=sc.id, amount=0.0))


async def load_wallet_spend_items(
    session: AsyncSession,
    wallet_id: int,
) -> dict[str, float]:
    """
    Load spend dict for a wallet from WalletSpendItem rows.
    SpendCategory.category is directly the card multiplier category name.
    """
    result = await session.execute(
        select(WalletSpendItem)
        .options(selectinload(WalletSpendItem.spend_category))
        .where(WalletSpendItem.wallet_id == wallet_id)
    )
    items = result.scalars().all()
    spend: dict[str, float] = {}
    for item in items:
        cat_name = item.spend_category.category if item.spend_category else ALL_OTHER_SPEND_NAME
        spend[cat_name] = spend.get(cat_name, 0.0) + item.amount
    return spend


async def load_wallet_card_credits(
    session: AsyncSession,
    wallet_id: int,
) -> dict[int, list[WalletCardCredit]]:
    """
    Load all WalletCardCredit rows for cards in the given wallet.
    Returns dict keyed by wallet_card_id.
    """
    from .models import WalletCard as WalletCardModel
    result = await session.execute(
        select(WalletCardCredit)
        .join(WalletCardModel, WalletCardModel.id == WalletCardCredit.wallet_card_id)
        .where(WalletCardModel.wallet_id == wallet_id)
    )
    rows = result.scalars().all()
    out: dict[int, list[WalletCardCredit]] = {}
    for row in rows:
        out.setdefault(row.wallet_card_id, []).append(row)
    return out


async def load_wallet_card_multipliers(
    session: AsyncSession,
    wallet_id: int,
) -> list[WalletCardMultiplier]:
    """Load all WalletCardMultiplier rows for the given wallet."""
    result = await session.execute(
        select(WalletCardMultiplier)
        .options(selectinload(WalletCardMultiplier.spend_category))
        .where(WalletCardMultiplier.wallet_id == wallet_id)
    )
    return list(result.scalars().all())


def apply_wallet_card_overrides(
    card_data_list: list[CardData],
    wallet_cards: list["WalletCard"],
    library_cards_by_id: dict[int, Card] | None = None,
    wallet_credit_rows: dict[int, list[WalletCardCredit]] | None = None,
) -> list[CardData]:
    """
    Return CardData copies with wallet-level overrides: SUB fields, fees, statement credits.
    Null wallet fields keep the library Card value.
    wallet_credit_rows: dict keyed by wallet_card_id -> list of WalletCardCredit rows.
    """
    wc_by_card_id: dict[int, "WalletCard"] = {wc.card_id: wc for wc in wallet_cards}
    # Build credit override lookup: (wallet_card_id, library_credit_id) -> (value, is_one_time)
    credit_lookup: dict[tuple[int, int], tuple[float, bool]] = {}
    if wallet_credit_rows:
        for wc_id, rows in wallet_credit_rows.items():
            for row in rows:
                credit_lookup[(wc_id, row.library_credit_id)] = (row.value, row.is_one_time)

    out: list[CardData] = []
    for cd in card_data_list:
        wc = wc_by_card_id.get(cd.id)
        if not wc:
            out.append(cd)
            continue

        annual_fee = (
            wc.annual_fee if wc.annual_fee is not None else cd.annual_fee
        )
        first_year_fee = (
            wc.first_year_fee if wc.first_year_fee is not None else cd.first_year_fee
        )

        lib = library_cards_by_id.get(wc.card_id) if library_cards_by_id else None
        lib_by_id = {cr.id: cr for cr in lib.credits} if lib is not None else {}
        merged_lines: list[CreditLine] = []
        for line in cd.credit_lines:
            cr = lib_by_id.get(line.library_credit_id)
            # Check wallet-level credit row first, then fall back to library
            override_key = (wc.id, line.library_credit_id)
            if override_key in credit_lookup:
                val, one_time = credit_lookup[override_key]
            else:
                val = line.value
                one_time = bool(cr.is_one_time) if cr is not None else line.one_time
            merged_lines.append(
                CreditLine(
                    library_credit_id=line.library_credit_id,
                    name=line.name,
                    value=val,
                    one_time=one_time,
                )
            )

        out.append(
            dataclasses.replace(
                cd,
                sub=wc.sub if wc.sub is not None else cd.sub,
                sub_min_spend=(
                    wc.sub_min_spend
                    if wc.sub_min_spend is not None
                    else cd.sub_min_spend
                ),
                sub_months=(
                    wc.sub_months if wc.sub_months is not None else cd.sub_months
                ),
                sub_spend_earn=(
                    wc.sub_spend_earn
                    if wc.sub_spend_earn is not None
                    else cd.sub_spend_earn
                ),
                annual_bonus=(
                    wc.annual_bonus if wc.annual_bonus is not None else cd.annual_bonus
                ),
                annual_fee=annual_fee,
                first_year_fee=first_year_fee,
                credit_lines=merged_lines,
                wallet_added_date=wc.added_date,
                wallet_closed_date=wc.closed_date,
                sub_earned_date=wc.sub_earned_date,
                sub_projected_earn_date=wc.sub_projected_earn_date,
            )
        )
    return out


def apply_wallet_card_multiplier_overrides(
    card_data_list: list[CardData],
    wallet_multipliers: list[WalletCardMultiplier],
) -> list[CardData]:
    """
    Return CardData copies with wallet-level multiplier overrides applied.
    For each WalletCardMultiplier row, patches card_data.multipliers[category] = override_multiplier.
    Applied before the calculator runs, so top-N group logic sees the patched values.
    """
    if not wallet_multipliers:
        return card_data_list

    # Build lookup: card_id -> {category_name: multiplier}
    overrides_by_card: dict[int, dict[str, float]] = {}
    for wm in wallet_multipliers:
        cat = wm.category
        if cat:
            overrides_by_card.setdefault(wm.card_id, {})[cat] = wm.multiplier

    out: list[CardData] = []
    for cd in card_data_list:
        card_overrides = overrides_by_card.get(cd.id)
        if not card_overrides:
            out.append(cd)
            continue
        patched_multipliers = dict(cd.multipliers)
        patched_multipliers.update(card_overrides)
        out.append(dataclasses.replace(cd, multipliers=patched_multipliers))
    return out
