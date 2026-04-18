"""Admin endpoints for CardMultiplierGroup CRUD."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...schemas import (
    AdminCreateCardMultiplierGroupPayload,
    AdminUpdateCardMultiplierGroupPayload,
    CardMultiplierGroupRead,
)
from ...services import (
    CardService,
    SpendCategoryService,
    get_card_service,
    get_spend_category_service,
)

router = APIRouter()


@router.get(
    "/admin/cards/{card_id}/multiplier-groups",
    response_model=list[CardMultiplierGroupRead],
)
async def admin_list_card_multiplier_groups(
    card_id: int,
    card_service: CardService = Depends(get_card_service),
):
    await card_service.get_or_404(card_id)
    return await card_service.list_multiplier_groups(card_id)


@router.post(
    "/admin/cards/{card_id}/multiplier-groups",
    response_model=CardMultiplierGroupRead,
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_card_multiplier_group(
    card_id: int,
    payload: AdminCreateCardMultiplierGroupPayload,
    db: AsyncSession = Depends(get_db),
    card_service: CardService = Depends(get_card_service),
    spend_service: SpendCategoryService = Depends(get_spend_category_service),
):
    await card_service.get_or_404(card_id)
    for cat_id in payload.category_ids:
        await spend_service.get_or_404(cat_id)
    grp = await card_service.create_multiplier_group(
        card_id=card_id, payload=payload
    )
    await db.commit()
    return await card_service.load_multiplier_group_full(grp.id)


@router.patch(
    "/admin/cards/{card_id}/multiplier-groups/{group_id}",
    response_model=CardMultiplierGroupRead,
)
async def admin_update_card_multiplier_group(
    card_id: int,
    group_id: int,
    payload: AdminUpdateCardMultiplierGroupPayload,
    db: AsyncSession = Depends(get_db),
    card_service: CardService = Depends(get_card_service),
    spend_service: SpendCategoryService = Depends(get_spend_category_service),
):
    grp = await card_service.get_multiplier_group_or_404(card_id, group_id)
    if payload.category_ids is not None:
        for cat_id in payload.category_ids:
            await spend_service.get_or_404(cat_id)
    await card_service.update_multiplier_group(
        grp=grp, card_id=card_id, payload=payload
    )
    await db.commit()
    return await card_service.load_multiplier_group_full(group_id)


@router.delete(
    "/admin/cards/{card_id}/multiplier-groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def admin_delete_card_multiplier_group(
    card_id: int,
    group_id: int,
    db: AsyncSession = Depends(get_db),
    card_service: CardService = Depends(get_card_service),
):
    grp = await card_service.get_multiplier_group_or_404(card_id, group_id)
    await card_service.delete(grp)
    await db.commit()
