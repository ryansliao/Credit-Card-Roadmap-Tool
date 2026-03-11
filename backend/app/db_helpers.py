"""
Helper to load cards and spend categories from the DB into calculator dataclasses.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .calculator import CardData, CurrencyData
from .models import Card, CardEcosystem, Currency, Ecosystem, EcosystemCurrency, SpendCategory

if TYPE_CHECKING:
    from .models import WalletCard


def _currency_data(orm_currency: Currency) -> CurrencyData:
    """Convert a Currency ORM object to a CurrencyData dataclass."""
    return CurrencyData(
        id=orm_currency.id,
        name=orm_currency.name,
        issuer_name=orm_currency.issuer.name if orm_currency.issuer else "",
        cents_per_point=orm_currency.cents_per_point,
        is_cashback=orm_currency.is_cashback,
        is_transferable=orm_currency.is_transferable,
    )


async def load_card_data(session: AsyncSession) -> list[CardData]:
    """Load all cards with their full relationship tree as CardData objects."""
    result = await session.execute(
        select(Card).options(
            selectinload(Card.issuer),
            selectinload(Card.currency_obj).selectinload(Currency.issuer),
            selectinload(Card.multipliers),
            selectinload(Card.credits),
            selectinload(Card.ecosystem_memberships)
            .selectinload(CardEcosystem.ecosystem)
            .selectinload(Ecosystem.points_currency)
            .selectinload(Currency.issuer),
            selectinload(Card.ecosystem_memberships)
            .selectinload(CardEcosystem.ecosystem)
            .selectinload(Ecosystem.cashback_currency),
            selectinload(Card.ecosystem_memberships)
            .selectinload(CardEcosystem.ecosystem)
            .selectinload(Ecosystem.ecosystem_currencies)
            .selectinload(EcosystemCurrency.currency),
        )
    )
    cards = result.scalars().all()

    out: list[CardData] = []
    for card in cards:
        currency = _currency_data(card.currency_obj)
        ecosystem_ids_where_key: set[int] = set()
        ecosystem_beneficiary_currency: dict[int, CurrencyData] = {}
        for m in card.ecosystem_memberships:
            eco = m.ecosystem
            # Key card = card doesn't earn cash (or other convertible currency) for this ecosystem
            earns_convertible = (
                (eco.cashback_currency_id is not None and card.currency_id == eco.cashback_currency_id)
                or (card.currency_id in {ec.currency_id for ec in eco.ecosystem_currencies})
            )
            key_card = not earns_convertible
            if key_card:
                ecosystem_ids_where_key.add(eco.id)
            else:
                # Beneficiary: earns ecosystem points when key card in wallet
                ecosystem_beneficiary_currency[eco.id] = _currency_data(eco.points_currency)

        multipliers = {m.category: m.multiplier for m in card.multipliers}
        credits = {c.credit_name: c.credit_value for c in card.credits}

        out.append(
            CardData(
                id=card.id,
                name=card.name,
                issuer_name=card.issuer.name,
                currency=currency,
                annual_fee=card.annual_fee,
                sub_points=card.sub_points,
                sub_min_spend=card.sub_min_spend,
                sub_months=card.sub_months,
                sub_spend_points=card.sub_spend_points,
                annual_bonus_points=card.annual_bonus_points,
                ecosystem_beneficiary_currency=ecosystem_beneficiary_currency,
                ecosystem_ids_where_key=ecosystem_ids_where_key,
                multipliers=multipliers,
                credits=credits,
            )
        )
    return out


async def load_spend(
    session: AsyncSession,
    overrides: dict[str, float] | None = None,
) -> dict[str, float]:
    """Load spend categories from DB, applying any overrides."""
    result = await session.execute(select(SpendCategory))
    cats = result.scalars().all()
    spend = {sc.category: sc.annual_spend for sc in cats}
    if overrides:
        spend.update(overrides)
    return spend


def apply_wallet_card_overrides(
    card_data_list: list[CardData],
    wallet_cards: list["WalletCard"],
) -> list[CardData]:
    """
    Return a new list of CardData with SUB fields overridden for cards that appear
    in wallet_cards. WalletCard sub_* and years_counted are applied when not None.
    """
    overrides_by_card_id: dict[int, dict] = {}
    for wc in wallet_cards:
        overrides_by_card_id[wc.card_id] = {
            "sub_points": wc.sub_points,
            "sub_min_spend": wc.sub_min_spend,
            "sub_months": wc.sub_months,
            "sub_spend_points": wc.sub_spend_points,
        }

    out: list[CardData] = []
    for cd in card_data_list:
        if cd.id not in overrides_by_card_id:
            out.append(cd)
            continue
        o = overrides_by_card_id[cd.id]
        out.append(
            dataclasses.replace(
                cd,
                sub_points=o["sub_points"] if o["sub_points"] is not None else cd.sub_points,
                sub_min_spend=o["sub_min_spend"] if o["sub_min_spend"] is not None else cd.sub_min_spend,
                sub_months=o["sub_months"] if o["sub_months"] is not None else cd.sub_months,
                sub_spend_points=o["sub_spend_points"] if o["sub_spend_points"] is not None else cd.sub_spend_points,
            )
        )
    return out
