"""Wallet currency balance and CPP override endpoints."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..auth import get_current_user
from ..database import get_db
from ..helpers import (
    effective_earn_currency_ids_for_wallet,
    ensure_wallet_currency_rows_for_earning_currencies,
    get_user_wallet,
)
from ..models import Currency, User, Wallet, WalletCurrencyBalance, WalletCurrencyCpp
from ..schemas import (
    CurrencyRead,
    WalletCurrencyBalanceRead,
    WalletCurrencyCppSet,
    WalletCurrencyInitialSet,
    WalletCurrencyTrackCreate,
    WalletSettingsCurrencyIds,
)

router = APIRouter(tags=["wallets"])


@router.get(
    "/wallets/{wallet_id}/currency-balances",
    response_model=list[WalletCurrencyBalanceRead],
)
async def list_wallet_currency_balances(
    wallet_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Currencies you track or that have projection earn from the last calculate."""
    await get_user_wallet(wallet_id, user, db)
    await ensure_wallet_currency_rows_for_earning_currencies(db, wallet_id)
    await db.commit()
    result = await db.execute(
        select(WalletCurrencyBalance)
        .options(selectinload(WalletCurrencyBalance.currency))
        .where(WalletCurrencyBalance.wallet_id == wallet_id)
        .order_by(WalletCurrencyBalance.currency_id)
    )
    return list(result.scalars().all())


@router.get(
    "/wallets/{wallet_id}/settings-currency-ids",
    response_model=WalletSettingsCurrencyIds,
)
async def wallet_settings_currency_ids(
    wallet_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    IDs for currencies shown in wallet settings: earned by cards in this wallet,
    or explicitly user-tracked (added manually).
    """
    await get_user_wallet(wallet_id, user, db)
    earn = await effective_earn_currency_ids_for_wallet(db, wallet_id)
    tr = await db.execute(
        select(WalletCurrencyBalance.currency_id).where(
            WalletCurrencyBalance.wallet_id == wallet_id,
            WalletCurrencyBalance.user_tracked.is_(True),
        )
    )
    tracked = set(tr.scalars().all())
    merged = earn | tracked
    return WalletSettingsCurrencyIds(currency_ids=sorted(merged))


@router.post(
    "/wallets/{wallet_id}/currency-balances",
    response_model=WalletCurrencyBalanceRead,
    status_code=status.HTTP_201_CREATED,
)
async def track_wallet_currency_balance(
    wallet_id: int,
    payload: WalletCurrencyTrackCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start tracking a currency for this wallet (optional starting balance)."""
    await get_user_wallet(wallet_id, user, db)
    currency_result = await db.execute(
        select(Currency).where(Currency.id == payload.currency_id)
    )
    if not currency_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Currency id={payload.currency_id} not found")

    existing = await db.execute(
        select(WalletCurrencyBalance).where(
            WalletCurrencyBalance.wallet_id == wallet_id,
            WalletCurrencyBalance.currency_id == payload.currency_id,
        )
    )
    row = existing.scalar_one_or_none()
    today = date.today()
    if row:
        row.user_tracked = True
        row.initial_balance = payload.initial_balance
        row.balance = round(row.initial_balance + row.projection_earn, 4)
        row.updated_date = today
    else:
        row = WalletCurrencyBalance(
            wallet_id=wallet_id,
            currency_id=payload.currency_id,
            initial_balance=payload.initial_balance,
            projection_earn=0.0,
            balance=payload.initial_balance,
            user_tracked=True,
            updated_date=today,
        )
        db.add(row)
    await db.commit()
    await db.refresh(row)
    res = await db.execute(
        select(WalletCurrencyBalance)
        .options(selectinload(WalletCurrencyBalance.currency))
        .where(WalletCurrencyBalance.id == row.id)
    )
    return res.scalar_one()


@router.put(
    "/wallets/{wallet_id}/currencies/{currency_id}/balance",
    response_model=WalletCurrencyBalanceRead,
)
async def set_wallet_currency_initial_balance(
    wallet_id: int,
    currency_id: int,
    payload: WalletCurrencyInitialSet,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update starting balance; total = initial + last projection earn from Calculate."""
    await get_user_wallet(wallet_id, user, db)
    currency_result = await db.execute(select(Currency).where(Currency.id == currency_id))
    if not currency_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Currency id={currency_id} not found")

    existing = await db.execute(
        select(WalletCurrencyBalance).where(
            WalletCurrencyBalance.wallet_id == wallet_id,
            WalletCurrencyBalance.currency_id == currency_id,
        )
    )
    row = existing.scalar_one_or_none()
    if not row:
        raise HTTPException(
            status_code=404,
            detail="Track this currency first (POST /currency-balances) before editing initial balance",
        )
    row.initial_balance = payload.initial_balance
    row.balance = round(row.initial_balance + row.projection_earn, 4)
    row.updated_date = date.today()
    await db.commit()
    res = await db.execute(
        select(WalletCurrencyBalance)
        .options(selectinload(WalletCurrencyBalance.currency))
        .where(WalletCurrencyBalance.id == row.id)
    )
    return res.scalar_one()


@router.delete(
    "/wallets/{wallet_id}/currencies/{currency_id}/balance",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_wallet_currency_balance(
    wallet_id: int,
    currency_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove the wallet's balance record for a currency."""
    await get_user_wallet(wallet_id, user, db)
    result = await db.execute(
        select(WalletCurrencyBalance).where(
            WalletCurrencyBalance.wallet_id == wallet_id,
            WalletCurrencyBalance.currency_id == currency_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(
            status_code=404,
            detail="No balance record found for this wallet and currency",
        )
    await db.delete(row)
    await db.commit()


# ---------------------------------------------------------------------------
# Wallet CPP overrides
# ---------------------------------------------------------------------------


@router.get(
    "/wallets/{wallet_id}/currencies",
    response_model=list[CurrencyRead],
    tags=["wallet-cpp"],
)
async def list_wallet_currencies_with_cpp(
    wallet_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all currencies with wallet-scoped CPP overrides applied."""
    await get_user_wallet(wallet_id, user, db)

    cpp_result = await db.execute(
        select(WalletCurrencyCpp).where(WalletCurrencyCpp.wallet_id == wallet_id)
    )
    overrides = {row.currency_id: row.cents_per_point for row in cpp_result.scalars().all()}

    cur_result = await db.execute(
        select(Currency)
        .order_by(Currency.name)
    )
    currencies = cur_result.scalars().all()
    out = []
    for c in currencies:
        schema = CurrencyRead.model_validate(c)
        if c.id in overrides:
            schema.user_cents_per_point = overrides[c.id]
        else:
            schema.user_cents_per_point = c.cents_per_point
        out.append(schema)
    return out


@router.put(
    "/wallets/{wallet_id}/currencies/{currency_id}/cpp",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["wallet-cpp"],
)
async def set_wallet_cpp(
    wallet_id: int,
    currency_id: int,
    payload: WalletCurrencyCppSet,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set or update wallet-scoped cents-per-point for a currency."""
    await get_user_wallet(wallet_id, user, db)
    cur_result = await db.execute(select(Currency).where(Currency.id == currency_id))
    if not cur_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Currency id={currency_id} not found")

    existing = await db.execute(
        select(WalletCurrencyCpp).where(
            WalletCurrencyCpp.wallet_id == wallet_id,
            WalletCurrencyCpp.currency_id == currency_id,
        )
    )
    row = existing.scalar_one_or_none()
    if row:
        row.cents_per_point = payload.cents_per_point
    else:
        db.add(WalletCurrencyCpp(
            wallet_id=wallet_id,
            currency_id=currency_id,
            cents_per_point=payload.cents_per_point,
        ))
    await db.commit()


@router.delete(
    "/wallets/{wallet_id}/currencies/{currency_id}/cpp",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["wallet-cpp"],
)
async def delete_wallet_cpp(
    wallet_id: int,
    currency_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove wallet-scoped CPP override (reverts to currency default)."""
    await get_user_wallet(wallet_id, user, db)
    result = await db.execute(
        select(WalletCurrencyCpp).where(
            WalletCurrencyCpp.wallet_id == wallet_id,
            WalletCurrencyCpp.currency_id == currency_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No CPP override for this wallet/currency")
    await db.delete(row)
    await db.commit()
