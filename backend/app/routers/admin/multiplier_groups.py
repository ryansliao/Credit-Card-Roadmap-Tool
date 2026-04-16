"""Admin endpoints for CardMultiplierGroup CRUD."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...database import get_db
from ...models import (
    Card,
    CardCategoryMultiplier,
    CardMultiplierGroup,
    RotatingCategory,
    SpendCategory,
)
from ...schemas import (
    AdminCreateCardMultiplierGroupPayload,
    AdminUpdateCardMultiplierGroupPayload,
    CardMultiplierGroupRead,
)

router = APIRouter()


def _multiplier_group_load_opts():
    """Eager-load options for multiplier group queries."""
    return [
        selectinload(CardMultiplierGroup.categories).selectinload(
            CardCategoryMultiplier.spend_category
        ),
        selectinload(CardMultiplierGroup.card)
        .selectinload(Card.rotating_categories)
        .selectinload(RotatingCategory.spend_category),
    ]


@router.get(
    "/admin/cards/{card_id}/multiplier-groups",
    response_model=list[CardMultiplierGroupRead],
)
async def admin_list_card_multiplier_groups(
    card_id: int,
    db: AsyncSession = Depends(get_db),
):
    card_result = await db.execute(select(Card).where(Card.id == card_id))
    if not card_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Card {card_id} not found")
    result = await db.execute(
        select(CardMultiplierGroup)
        .options(*_multiplier_group_load_opts())
        .where(CardMultiplierGroup.card_id == card_id)
    )
    return result.scalars().all()


@router.post(
    "/admin/cards/{card_id}/multiplier-groups",
    response_model=CardMultiplierGroupRead,
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_card_multiplier_group(
    card_id: int,
    payload: AdminCreateCardMultiplierGroupPayload,
    db: AsyncSession = Depends(get_db),
):
    card_result = await db.execute(select(Card).where(Card.id == card_id))
    if not card_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Card {card_id} not found")

    grp = CardMultiplierGroup(
        card_id=card_id,
        multiplier=payload.multiplier,
        cap_per_billing_cycle=payload.cap_per_billing_cycle,
        cap_period_months=payload.cap_period_months,
        top_n_categories=payload.top_n_categories,
        is_rotating=payload.is_rotating,
        is_additive=payload.is_additive,
    )
    db.add(grp)
    await db.flush()

    for cat_id in payload.category_ids:
        sc_result = await db.execute(
            select(SpendCategory).where(SpendCategory.id == cat_id)
        )
        if not sc_result.scalar_one_or_none():
            raise HTTPException(
                status_code=404, detail=f"SpendCategory id={cat_id} not found"
            )
        existing = await db.execute(
            select(CardCategoryMultiplier).where(
                CardCategoryMultiplier.card_id == card_id,
                CardCategoryMultiplier.category_id == cat_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail=f"Multiplier for card {card_id} / category {cat_id} already exists",
            )
        db.add(
            CardCategoryMultiplier(
                card_id=card_id,
                category_id=cat_id,
                multiplier=payload.multiplier,
                multiplier_group_id=grp.id,
            )
        )

    await db.commit()
    result = await db.execute(
        select(CardMultiplierGroup)
        .options(*_multiplier_group_load_opts())
        .where(CardMultiplierGroup.id == grp.id)
    )
    return result.scalar_one()


@router.patch(
    "/admin/cards/{card_id}/multiplier-groups/{group_id}",
    response_model=CardMultiplierGroupRead,
)
async def admin_update_card_multiplier_group(
    card_id: int,
    group_id: int,
    payload: AdminUpdateCardMultiplierGroupPayload,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CardMultiplierGroup).where(
            CardMultiplierGroup.id == group_id,
            CardMultiplierGroup.card_id == card_id,
        )
    )
    grp = result.scalar_one_or_none()
    if not grp:
        raise HTTPException(
            status_code=404,
            detail=f"MultiplierGroup id={group_id} not found for card {card_id}",
        )

    if payload.multiplier is not None:
        grp.multiplier = payload.multiplier
    if payload.cap_per_billing_cycle is not None:
        grp.cap_per_billing_cycle = payload.cap_per_billing_cycle
    if payload.cap_period_months is not None:
        grp.cap_period_months = payload.cap_period_months
    if payload.top_n_categories is not None:
        grp.top_n_categories = payload.top_n_categories
    if payload.is_rotating is not None:
        grp.is_rotating = payload.is_rotating
    if payload.is_additive is not None:
        grp.is_additive = payload.is_additive

    if payload.category_ids is not None:
        existing = await db.execute(
            select(CardCategoryMultiplier).where(
                CardCategoryMultiplier.multiplier_group_id == group_id
            )
        )
        for row in existing.scalars().all():
            await db.delete(row)

        mult = payload.multiplier if payload.multiplier is not None else grp.multiplier
        for cat_id in payload.category_ids:
            sc_result = await db.execute(
                select(SpendCategory).where(SpendCategory.id == cat_id)
            )
            if not sc_result.scalar_one_or_none():
                raise HTTPException(
                    status_code=404, detail=f"SpendCategory id={cat_id} not found"
                )
            conflict = await db.execute(
                select(CardCategoryMultiplier).where(
                    CardCategoryMultiplier.card_id == card_id,
                    CardCategoryMultiplier.category_id == cat_id,
                    CardCategoryMultiplier.multiplier_group_id != group_id,
                )
            )
            if conflict.scalar_one_or_none():
                raise HTTPException(
                    status_code=409,
                    detail=f"Multiplier for card {card_id} / category {cat_id} already exists outside this group",
                )
            db.add(
                CardCategoryMultiplier(
                    card_id=card_id,
                    category_id=cat_id,
                    multiplier=mult,
                    multiplier_group_id=group_id,
                )
            )
    elif payload.multiplier is not None:
        existing = await db.execute(
            select(CardCategoryMultiplier).where(
                CardCategoryMultiplier.multiplier_group_id == group_id
            )
        )
        for row in existing.scalars().all():
            row.multiplier = payload.multiplier

    await db.commit()
    result = await db.execute(
        select(CardMultiplierGroup)
        .options(*_multiplier_group_load_opts())
        .where(CardMultiplierGroup.id == group_id)
    )
    return result.scalar_one()


@router.delete(
    "/admin/cards/{card_id}/multiplier-groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def admin_delete_card_multiplier_group(
    card_id: int,
    group_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CardMultiplierGroup).where(
            CardMultiplierGroup.id == group_id,
            CardMultiplierGroup.card_id == card_id,
        )
    )
    grp = result.scalar_one_or_none()
    if not grp:
        raise HTTPException(
            status_code=404,
            detail=f"MultiplierGroup id={group_id} not found for card {card_id}",
        )
    await db.delete(grp)
    await db.commit()
