"""Card library endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..helpers import card_404, card_load_opts
from ..models import Card
from ..schemas import CardRead, UpdateCardLibraryPayload

router = APIRouter(tags=["cards"])

_CARD_LIBRARY_PATCH_FIELDS = frozenset(
    {"sub_points", "sub_min_spend", "sub_months", "sub_cash", "annual_fee", "first_year_fee", "transfer_enabler",
     "annual_bonus", "annual_bonus_percent", "annual_bonus_first_year_only",
     "secondary_currency_id", "secondary_currency_rate", "secondary_currency_cap_rate",
     "accelerator_cost", "accelerator_spend_limit", "accelerator_bonus_multiplier",
     "accelerator_max_activations", "foreign_transaction_fee", "sub_secondary_points"}
)


@router.get("/cards", response_model=list[CardRead])
async def list_cards(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Card).options(*card_load_opts()))
    return result.scalars().all()


@router.patch("/cards/{card_id}", response_model=CardRead)
async def update_card_library(
    card_id: int,
    payload: UpdateCardLibraryPayload,
    db: AsyncSession = Depends(get_db),
):
    """Update editable card library fields (SUB, min spend, months, fees)."""
    result = await db.execute(select(Card).where(Card.id == card_id))
    card = result.scalar_one_or_none()
    if not card:
        raise card_404(card_id)
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    for key, value in data.items():
        if key not in _CARD_LIBRARY_PATCH_FIELDS:
            continue
        setattr(card, key, value)
    await db.commit()
    refreshed = await db.execute(
        select(Card).where(Card.id == card_id).options(*card_load_opts())
    )
    return refreshed.scalar_one()
