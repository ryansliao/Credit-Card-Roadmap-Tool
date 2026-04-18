"""Admin endpoints for reference data: Issuers, Currencies, SpendCategories."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...schemas import (
    AdminCreateCurrencyPayload,
    AdminCreateIssuerPayload,
    AdminCreateSpendCategoryPayload,
    CurrencyRead,
    IssuerRead,
    SpendCategoryRead,
)
from ...services import (
    CurrencyService,
    IssuerService,
    SpendCategoryService,
    get_currency_service,
    get_issuer_service,
    get_spend_category_service,
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
    issuer_service: IssuerService = Depends(get_issuer_service),
):
    issuer = await issuer_service.create(payload.name)
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
    currency_service: CurrencyService = Depends(get_currency_service),
):
    currency = await currency_service.create(
        name=payload.name,
        reward_kind=payload.reward_kind,
        cents_per_point=payload.cents_per_point,
        partner_transfer_rate=payload.partner_transfer_rate,
        cash_transfer_rate=payload.cash_transfer_rate,
        converts_to_currency_id=payload.converts_to_currency_id,
        converts_at_rate=payload.converts_at_rate,
        no_transfer_cpp=payload.no_transfer_cpp,
        no_transfer_rate=payload.no_transfer_rate,
    )
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
    spend_service: SpendCategoryService = Depends(get_spend_category_service),
):
    sc = await spend_service.create(
        category=payload.category,
        is_housing=payload.is_housing,
        is_foreign_eligible=payload.is_foreign_eligible,
    )
    await db.commit()
    await db.refresh(sc)
    return sc
