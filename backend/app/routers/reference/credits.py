"""Statement credit endpoints (per-user library + admin CRUD)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth import get_current_user, require_admin_user
from ...database import get_db
from ...models import User
from ...schemas import CardCreditRead, CreateCreditPayload, UpdateCreditPayload
from ...services import CreditService, get_credit_service

router = APIRouter(tags=["credits"])


@router.get("/credits", response_model=list[CardCreditRead])
async def list_credits(
    user: User = Depends(get_current_user),
    credit_service: CreditService = Depends(get_credit_service),
):
    """List credits visible to this user: system credits + the user's own."""
    return await credit_service.list_visible_to_user(user.id)


@router.post(
    "/credits",
    response_model=CardCreditRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_credit(
    payload: CreateCreditPayload,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    credit_service: CreditService = Depends(get_credit_service),
):
    """Create a credit owned by the current user.

    User-scoped: visible only to the creator. Names must be unique within the
    user's own credits but can collide with system credits or other users.
    """
    credit = await credit_service.create(
        credit_name=payload.credit_name,
        value=payload.value,
        card_ids=payload.card_ids,
        excludes_first_year=payload.excludes_first_year,
        is_one_time=payload.is_one_time,
        credit_currency_id=payload.credit_currency_id,
        card_values=payload.card_values,
        owner_user_id=user.id,
    )
    await db.commit()
    return await credit_service.get_with_links(credit.id)


@router.patch(
    "/credits/{credit_id}",
    response_model=CardCreditRead,
)
async def update_user_credit(
    credit_id: int,
    payload: UpdateCreditPayload,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    credit_service: CreditService = Depends(get_credit_service),
):
    """Update a user-owned credit. Cannot modify system credits."""
    credit = await credit_service.get_or_404(credit_id)
    if credit.owner_user_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="Cannot modify system credits or another user's credit",
        )

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
    "/credits/{credit_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_user_credit(
    credit_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    credit_service: CreditService = Depends(get_credit_service),
):
    """Delete a user-owned credit. Cannot delete system credits."""
    credit = await credit_service.get_or_404(credit_id)
    if credit.owner_user_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="Cannot delete system credits or another user's credit",
        )
    await credit_service.delete(credit)
    await db.commit()


@router.post(
    "/admin/credits",
    response_model=CardCreditRead,
    status_code=status.HTTP_201_CREATED,
    tags=["admin"],
)
async def admin_create_credit(
    payload: CreateCreditPayload,
    _admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
    credit_service: CreditService = Depends(get_credit_service),
):
    """Create a system credit (NULL owner) — admin / seed path."""
    credit = await credit_service.create(
        credit_name=payload.credit_name,
        value=payload.value,
        card_ids=payload.card_ids,
        excludes_first_year=payload.excludes_first_year,
        is_one_time=payload.is_one_time,
        credit_currency_id=payload.credit_currency_id,
        card_values=payload.card_values,
        owner_user_id=None,
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
    _admin: User = Depends(require_admin_user),
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
    _admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
    credit_service: CreditService = Depends(get_credit_service),
):
    credit = await credit_service.get_or_404(credit_id)
    await credit_service.delete(credit)
    await db.commit()
