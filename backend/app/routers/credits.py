"""Standardized credit library endpoints (read + admin CRUD)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..helpers import validate_card_ids, set_credit_card_links
from ..models import Credit
from ..schemas import CardCreditRead, CreateCreditPayload, UpdateCreditPayload

router = APIRouter(tags=["credits"])


@router.get("/credits", response_model=list[CardCreditRead])
async def list_credits(db: AsyncSession = Depends(get_db)):
    """List the global standardized statement credit library."""
    result = await db.execute(
        select(Credit)
        .options(selectinload(Credit.card_links))
        .order_by(Credit.credit_name)
    )
    return list(result.scalars().all())


@router.post(
    "/admin/credits",
    response_model=CardCreditRead,
    status_code=status.HTTP_201_CREATED,
    tags=["admin"],
)
async def admin_create_credit(
    payload: CreateCreditPayload,
    db: AsyncSession = Depends(get_db),
):
    name = payload.credit_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="credit_name cannot be empty")
    existing = await db.execute(select(Credit).where(Credit.credit_name == name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Credit '{name}' already exists")
    card_ids = await validate_card_ids(db, payload.card_ids)
    credit = Credit(
        credit_name=name,
        value=payload.value,
        excludes_first_year=payload.excludes_first_year,
        is_one_time=payload.is_one_time,
        credit_currency_id=payload.credit_currency_id,
    )
    db.add(credit)
    await db.flush()
    await set_credit_card_links(db, credit, card_ids, payload.card_values)
    await db.commit()
    result = await db.execute(
        select(Credit)
        .options(selectinload(Credit.card_links))
        .where(Credit.id == credit.id)
    )
    return result.scalar_one()


@router.patch(
    "/admin/credits/{credit_id}",
    response_model=CardCreditRead,
    tags=["admin"],
)
async def admin_update_credit(
    credit_id: int,
    payload: UpdateCreditPayload,
    db: AsyncSession = Depends(get_db),
):
    """Update default value, rename, or update card links for a library credit."""
    result = await db.execute(
        select(Credit)
        .options(selectinload(Credit.card_links))
        .where(Credit.id == credit_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail=f"Credit {credit_id} not found")
    if "value" in payload.model_fields_set:
        row.value = payload.value
    if payload.excludes_first_year is not None:
        row.excludes_first_year = payload.excludes_first_year
    if payload.is_one_time is not None:
        row.is_one_time = payload.is_one_time
    if "credit_currency_id" in payload.model_fields_set:
        row.credit_currency_id = payload.credit_currency_id
    if payload.credit_name is not None:
        new_name = payload.credit_name.strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="credit_name cannot be empty")
        if new_name != row.credit_name:
            clash = await db.execute(
                select(Credit).where(
                    Credit.credit_name == new_name,
                    Credit.id != credit_id,
                )
            )
            if clash.scalar_one_or_none():
                raise HTTPException(
                    status_code=409,
                    detail=f"Credit name {new_name!r} already exists",
                )
        row.credit_name = new_name
    if payload.card_ids is not None:
        card_ids = await validate_card_ids(db, payload.card_ids)
        await set_credit_card_links(db, row, card_ids, payload.card_values)
    elif payload.card_values is not None:
        # Update per-card values without changing the card list
        for link in row.card_links:
            if link.card_id in payload.card_values:
                link.value = payload.card_values[link.card_id]
    await db.commit()
    result = await db.execute(
        select(Credit)
        .options(selectinload(Credit.card_links))
        .where(Credit.id == credit_id)
    )
    return result.scalar_one()


@router.delete(
    "/admin/credits/{credit_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["admin"],
)
async def admin_delete_credit(
    credit_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Credit).where(Credit.id == credit_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail=f"Credit {credit_id} not found")
    await db.delete(row)
    await db.commit()
