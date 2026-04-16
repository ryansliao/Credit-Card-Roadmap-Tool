"""Admin endpoints for reference data: Issuers, Currencies, SpendCategories."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models import Currency, Issuer, SpendCategory
from ...schemas import (
    AdminCreateCurrencyPayload,
    AdminCreateIssuerPayload,
    AdminCreateSpendCategoryPayload,
    CurrencyRead,
    IssuerRead,
    SpendCategoryRead,
)

router = APIRouter()


@router.post(
    "/admin/issuers",
    response_model=IssuerRead,
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_issuer(
    payload: AdminCreateIssuerPayload,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(Issuer).where(Issuer.name == payload.name.strip()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Issuer '{payload.name}' already exists")
    issuer = Issuer(name=payload.name.strip())
    db.add(issuer)
    await db.commit()
    await db.refresh(issuer)
    return issuer


@router.post(
    "/admin/currencies",
    response_model=CurrencyRead,
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_currency(
    payload: AdminCreateCurrencyPayload,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(Currency).where(Currency.name == payload.name.strip()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Currency '{payload.name}' already exists")
    if payload.converts_to_currency_id is not None:
        tgt = await db.execute(select(Currency).where(Currency.id == payload.converts_to_currency_id))
        if not tgt.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"Target currency id={payload.converts_to_currency_id} not found")

    currency = Currency(
        name=payload.name.strip(),
        reward_kind=payload.reward_kind,
        cents_per_point=payload.cents_per_point,
        partner_transfer_rate=payload.partner_transfer_rate,
        cash_transfer_rate=payload.cash_transfer_rate,
        converts_to_currency_id=payload.converts_to_currency_id,
        converts_at_rate=payload.converts_at_rate,
        no_transfer_cpp=payload.no_transfer_cpp,
        no_transfer_rate=payload.no_transfer_rate,
    )
    db.add(currency)
    await db.commit()
    await db.refresh(currency)
    return currency


@router.post(
    "/admin/spend-categories",
    response_model=SpendCategoryRead,
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_spend_category(
    payload: AdminCreateSpendCategoryPayload,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(SpendCategory).where(SpendCategory.category == payload.category.strip()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"SpendCategory '{payload.category}' already exists")
    sc = SpendCategory(
        category=payload.category.strip(),
        is_housing=payload.is_housing,
        is_foreign_eligible=payload.is_foreign_eligible,
    )
    db.add(sc)
    await db.commit()
    await db.refresh(sc)
    return sc
