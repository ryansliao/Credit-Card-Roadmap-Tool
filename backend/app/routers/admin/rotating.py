"""Admin endpoints for rotating category history."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...database import get_db
from ...models import Card, RotatingCategory, SpendCategory
from ...schemas import AdminAddRotatingHistoryPayload, RotatingCategoryRead

router = APIRouter()


@router.get(
    "/admin/cards/{card_id}/rotating-history",
    response_model=list[RotatingCategoryRead],
)
async def admin_list_card_rotating_history(
    card_id: int,
    db: AsyncSession = Depends(get_db),
):
    card_result = await db.execute(select(Card).where(Card.id == card_id))
    if not card_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Card {card_id} not found")
    result = await db.execute(
        select(RotatingCategory)
        .options(selectinload(RotatingCategory.spend_category))
        .where(RotatingCategory.card_id == card_id)
        .order_by(RotatingCategory.year.desc(), RotatingCategory.quarter.desc())
    )
    return result.scalars().all()


@router.post(
    "/admin/cards/{card_id}/rotating-history",
    response_model=RotatingCategoryRead,
    status_code=status.HTTP_201_CREATED,
)
async def admin_add_card_rotating_history(
    card_id: int,
    payload: AdminAddRotatingHistoryPayload,
    db: AsyncSession = Depends(get_db),
):
    card_result = await db.execute(select(Card).where(Card.id == card_id))
    if not card_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Card {card_id} not found")
    sc_result = await db.execute(
        select(SpendCategory).where(SpendCategory.id == payload.spend_category_id)
    )
    if not sc_result.scalar_one_or_none():
        raise HTTPException(
            status_code=404,
            detail=f"SpendCategory id={payload.spend_category_id} not found",
        )
    existing = await db.execute(
        select(RotatingCategory).where(
            RotatingCategory.card_id == card_id,
            RotatingCategory.year == payload.year,
            RotatingCategory.quarter == payload.quarter,
            RotatingCategory.spend_category_id == payload.spend_category_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Rotating history already exists for card {card_id} {payload.year}Q{payload.quarter} cat={payload.spend_category_id}",
        )
    row = RotatingCategory(
        card_id=card_id,
        year=payload.year,
        quarter=payload.quarter,
        spend_category_id=payload.spend_category_id,
    )
    db.add(row)
    await db.commit()
    result = await db.execute(
        select(RotatingCategory)
        .options(selectinload(RotatingCategory.spend_category))
        .where(RotatingCategory.id == row.id)
    )
    return result.scalar_one()


@router.delete(
    "/admin/cards/{card_id}/rotating-history/{history_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def admin_delete_card_rotating_history(
    card_id: int,
    history_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RotatingCategory).where(
            RotatingCategory.id == history_id,
            RotatingCategory.card_id == card_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"Rotating history id={history_id} not found for card {card_id}",
        )
    await db.delete(row)
    await db.commit()
