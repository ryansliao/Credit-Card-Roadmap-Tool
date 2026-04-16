"""Card library endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import CardRead, UpdateCardLibraryPayload
from ..services import CardService, get_card_service

router = APIRouter(tags=["cards"])


@router.get("/cards", response_model=list[CardRead])
async def list_cards(
    card_service: CardService = Depends(get_card_service),
):
    return await card_service.list_all_with_opts()


@router.patch("/cards/{card_id}", response_model=CardRead)
async def update_card_library(
    card_id: int,
    payload: UpdateCardLibraryPayload,
    db: AsyncSession = Depends(get_db),
    card_service: CardService = Depends(get_card_service),
):
    """Update editable card library fields (SUB, min spend, months, fees)."""
    card = await card_service.get_or_404(card_id)

    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    await card_service.update_library_fields(card, **data)
    await db.commit()

    return await card_service.get_with_opts(card_id)
