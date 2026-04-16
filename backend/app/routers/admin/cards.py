"""Admin endpoints for Card CRUD and card multipliers."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models import (
    Card,
    CardCategoryMultiplier,
    CardMultiplierGroup,
    CoBrand,
    Currency,
    Issuer,
    NetworkTier,
    SpendCategory,
    WalletCard,
)
from ...schemas import (
    AdminAddCardMultiplierPayload,
    AdminCreateCardPayload,
    CardRead,
)
from ...services import CardService

router = APIRouter()


@router.post(
    "/admin/cards",
    response_model=CardRead,
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_card(
    payload: AdminCreateCardPayload,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(Card).where(Card.name == payload.name.strip()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Card '{payload.name}' already exists")
    iss = await db.execute(select(Issuer).where(Issuer.id == payload.issuer_id))
    if not iss.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Issuer id={payload.issuer_id} not found")
    cur = await db.execute(select(Currency).where(Currency.id == payload.currency_id))
    if not cur.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Currency id={payload.currency_id} not found")
    if payload.co_brand_id is not None:
        cb = await db.execute(select(CoBrand).where(CoBrand.id == payload.co_brand_id))
        if not cb.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"CoBrand id={payload.co_brand_id} not found")
    if payload.network_tier_id is not None:
        nt = await db.execute(select(NetworkTier).where(NetworkTier.id == payload.network_tier_id))
        if not nt.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"NetworkTier id={payload.network_tier_id} not found")

    if payload.secondary_currency_id is not None:
        sec_cur = await db.execute(select(Currency).where(Currency.id == payload.secondary_currency_id))
        if not sec_cur.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"Secondary currency id={payload.secondary_currency_id} not found")

    card = Card(
        name=payload.name.strip(),
        issuer_id=payload.issuer_id,
        co_brand_id=payload.co_brand_id,
        currency_id=payload.currency_id,
        annual_fee=payload.annual_fee,
        first_year_fee=payload.first_year_fee,
        business=payload.business,
        network_tier_id=payload.network_tier_id,
        sub_points=payload.sub_points,
        sub_min_spend=payload.sub_min_spend,
        sub_months=payload.sub_months,
        sub_spend_earn=payload.sub_spend_earn,
        annual_bonus=payload.annual_bonus,
        annual_bonus_percent=payload.annual_bonus_percent,
        annual_bonus_first_year_only=payload.annual_bonus_first_year_only,
        transfer_enabler=payload.transfer_enabler,
        secondary_currency_id=payload.secondary_currency_id,
        secondary_currency_rate=payload.secondary_currency_rate,
        secondary_currency_cap_rate=payload.secondary_currency_cap_rate,
        accelerator_cost=payload.accelerator_cost,
        accelerator_spend_limit=payload.accelerator_spend_limit,
        accelerator_bonus_multiplier=payload.accelerator_bonus_multiplier,
        accelerator_max_activations=payload.accelerator_max_activations,
        housing_tiered_enabled=payload.housing_tiered_enabled,
        housing_fee_waived=getattr(payload, "housing_fee_waived", False),
        sub_recurrence_months=payload.sub_recurrence_months,
        sub_family=payload.sub_family,
    )
    db.add(card)
    await db.commit()
    res = await db.execute(
        select(Card).options(*CardService.load_opts()).where(Card.id == card.id)
    )
    return res.scalar_one()


@router.delete(
    "/admin/cards/{card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def admin_delete_card(
    card_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Card).where(Card.id == card_id))
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail=f"Card {card_id} not found")
    wc_count = await db.execute(select(WalletCard.id).where(WalletCard.card_id == card_id))
    if wc_count.scalars().first() is not None:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete card — it is used in one or more wallets. Remove it from all wallets first.",
        )
    await db.delete(card)
    await db.commit()


@router.post(
    "/admin/cards/{card_id}/multipliers",
    response_model=CardRead,
    status_code=status.HTTP_201_CREATED,
)
async def admin_add_card_multiplier(
    card_id: int,
    payload: AdminAddCardMultiplierPayload,
    db: AsyncSession = Depends(get_db),
):
    card_result = await db.execute(select(Card).where(Card.id == card_id))
    if not card_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Card {card_id} not found")
    sc_result = await db.execute(select(SpendCategory).where(SpendCategory.id == payload.category_id))
    if not sc_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"SpendCategory id={payload.category_id} not found")

    existing = await db.execute(
        select(CardCategoryMultiplier).where(
            CardCategoryMultiplier.card_id == card_id,
            CardCategoryMultiplier.category_id == payload.category_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Multiplier for this card/category already exists")

    if payload.multiplier_group_id is not None:
        grp = await db.execute(
            select(CardMultiplierGroup).where(
                CardMultiplierGroup.id == payload.multiplier_group_id,
                CardMultiplierGroup.card_id == card_id,
            )
        )
        if not grp.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"MultiplierGroup id={payload.multiplier_group_id} not found for card {card_id}")

    mult = CardCategoryMultiplier(
        card_id=card_id,
        category_id=payload.category_id,
        multiplier=payload.multiplier,
        is_portal=payload.is_portal,
        is_additive=payload.is_additive,
        cap_per_billing_cycle=payload.cap_per_billing_cycle,
        cap_period_months=payload.cap_period_months,
        multiplier_group_id=payload.multiplier_group_id,
    )
    db.add(mult)
    await db.commit()
    res = await db.execute(select(Card).options(*CardService.load_opts()).where(Card.id == card_id))
    return res.scalar_one()


@router.delete(
    "/admin/cards/{card_id}/multipliers/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def admin_delete_card_multiplier(
    card_id: int,
    category_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CardCategoryMultiplier).where(
            CardCategoryMultiplier.card_id == card_id,
            CardCategoryMultiplier.category_id == category_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Multiplier not found for this card/category")
    await db.delete(row)
    await db.commit()
