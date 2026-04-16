"""Standardized credit library endpoints (read + admin CRUD)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import CardCreditRead, CreateCreditPayload, UpdateCreditPayload
from ..services import CreditService, get_credit_service

router = APIRouter(tags=["credits"])


@router.get("/credits", response_model=list[CardCreditRead])
async def list_credits(
    credit_service: CreditService = Depends(get_credit_service),
):
    """List the global standardized statement credit library."""
    return await credit_service.list_all_with_links()


@router.post(
    "/admin/credits",
    response_model=CardCreditRead,
    status_code=status.HTTP_201_CREATED,
    tags=["admin"],
)
async def admin_create_credit(
    payload: CreateCreditPayload,
    db: AsyncSession = Depends(get_db),
    credit_service: CreditService = Depends(get_credit_service),
):
    credit = await credit_service.create(
        credit_name=payload.credit_name,
        value=payload.value,
        card_ids=payload.card_ids,
        excludes_first_year=payload.excludes_first_year,
        is_one_time=payload.is_one_time,
        credit_currency_id=payload.credit_currency_id,
        card_values=payload.card_values,
    )
    await db.commit()
    return await credit_service.get_with_links(credit.id)


@router.patch(
    "/admin/credits/{credit_id}",
    response_model=CardCreditRead,
    tags=["admin"],
)
async def admin_update_credit(
    credit_id: int,
    payload: UpdateCreditPayload,
    db: AsyncSession = Depends(get_db),
    credit_service: CreditService = Depends(get_credit_service),
):
    """Update default value, rename, or update card links for a library credit."""
    credit = await credit_service.get_or_404(credit_id)

    await credit_service.update(
        credit,
        credit_name=payload.credit_name,
        value=payload.value,
        excludes_first_year=payload.excludes_first_year,
        is_one_time=payload.is_one_time,
        credit_currency_id=payload.credit_currency_id,
        card_ids=payload.card_ids,
        card_values=payload.card_values,
        value_is_set="value" in payload.model_fields_set,
        credit_currency_id_is_set="credit_currency_id" in payload.model_fields_set,
    )
    await db.commit()
    return await credit_service.get_with_links(credit_id)


@router.delete(
    "/admin/credits/{credit_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["admin"],
)
async def admin_delete_credit(
    credit_id: int,
    db: AsyncSession = Depends(get_db),
    credit_service: CreditService = Depends(get_credit_service),
):
    credit = await credit_service.get_or_404(credit_id)
    await credit_service.delete(credit)
    await db.commit()
