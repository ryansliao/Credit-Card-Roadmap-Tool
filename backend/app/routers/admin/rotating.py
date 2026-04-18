"""Admin endpoints for rotating category history."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...schemas import AdminAddRotatingHistoryPayload, RotatingCategoryRead
from ...services import (
    CardService,
    SpendCategoryService,
    get_card_service,
    get_spend_category_service,
)

router = APIRouter()


@router.get(
    "/admin/cards/{card_id}/rotating-history",
    response_model=list[RotatingCategoryRead],
)
async def admin_list_card_rotating_history(
    card_id: int,
    card_service: CardService = Depends(get_card_service),
):
    await card_service.get_or_404(card_id)
    return await card_service.list_rotating_history(card_id)


@router.post(
    "/admin/cards/{card_id}/rotating-history",
    response_model=RotatingCategoryRead,
    status_code=status.HTTP_201_CREATED,
)
async def admin_add_card_rotating_history(
    card_id: int,
    payload: AdminAddRotatingHistoryPayload,
    db: AsyncSession = Depends(get_db),
    card_service: CardService = Depends(get_card_service),
    spend_service: SpendCategoryService = Depends(get_spend_category_service),
):
    await card_service.get_or_404(card_id)
    await spend_service.get_or_404(payload.spend_category_id)
    row = await card_service.add_rotating_history(
        card_id=card_id,
        year=payload.year,
        quarter=payload.quarter,
        spend_category_id=payload.spend_category_id,
    )
    await db.commit()
    return await card_service.get_rotating_history_row_with_category(row.id)


@router.delete(
    "/admin/cards/{card_id}/rotating-history/{history_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def admin_delete_card_rotating_history(
    card_id: int,
    history_id: int,
    db: AsyncSession = Depends(get_db),
    card_service: CardService = Depends(get_card_service),
):
    row = await card_service.get_rotating_history_row(card_id, history_id)
    await card_service.delete(row)
    await db.commit()
