"""Admin endpoints for Card CRUD and card multipliers."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...schemas import (
    AdminAddCardMultiplierPayload,
    AdminCreateCardPayload,
    CardRead,
)
from ...services import (
    CardService,
    SpendCategoryService,
    get_card_service,
    get_spend_category_service,
)

router = APIRouter()


@router.post(
    "/admin/cards",
    response_model=CardRead,
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_card(
    payload: AdminCreateCardPayload,
    db: AsyncSession = Depends(get_db),
    card_service: CardService = Depends(get_card_service),
):
    card = await card_service.create(payload)
    await db.commit()
    reloaded = await card_service.get_with_opts(card.id)
    assert reloaded is not None
    return reloaded


@router.delete(
    "/admin/cards/{card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def admin_delete_card(
    card_id: int,
    db: AsyncSession = Depends(get_db),
    card_service: CardService = Depends(get_card_service),
):
    card = await card_service.get_or_404(card_id)
    await card_service.delete_card_if_unused(card)
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
    card_service: CardService = Depends(get_card_service),
    spend_service: SpendCategoryService = Depends(get_spend_category_service),
):
    await card_service.get_or_404(card_id)
    await spend_service.get_or_404(payload.category_id)
    await card_service.add_multiplier(
        card_id=card_id,
        category_id=payload.category_id,
        multiplier=payload.multiplier,
        is_portal=payload.is_portal,
        is_additive=payload.is_additive,
        cap_per_billing_cycle=payload.cap_per_billing_cycle,
        cap_period_months=payload.cap_period_months,
        multiplier_group_id=payload.multiplier_group_id,
    )
    await db.commit()
    reloaded = await card_service.get_with_opts(card_id)
    assert reloaded is not None
    return reloaded


@router.delete(
    "/admin/cards/{card_id}/multipliers/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def admin_delete_card_multiplier(
    card_id: int,
    category_id: int,
    db: AsyncSession = Depends(get_db),
    card_service: CardService = Depends(get_card_service),
):
    await card_service.delete_multiplier(card_id, category_id)
    await db.commit()
