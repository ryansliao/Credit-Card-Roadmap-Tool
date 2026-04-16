"""Wallet currency balance and CPP override endpoints."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_db
from ..models import User
from ..schemas import (
    CurrencyRead,
    WalletCurrencyBalanceRead,
    WalletCurrencyCppSet,
    WalletCurrencyInitialSet,
    WalletCurrencyTrackCreate,
    WalletSettingsCurrencyIds,
)
from ..services import (
    WalletService,
    WalletCurrencyService,
    get_wallet_service,
    get_wallet_currency_service,
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
    wallet_service: WalletService = Depends(get_wallet_service),
    currency_service: WalletCurrencyService = Depends(get_wallet_currency_service),
):
    """Currencies you track or that have projection earn from the last calculate."""
    await wallet_service.get_user_wallet(wallet_id, user)
    await currency_service.ensure_earning_currency_rows(wallet_id)
    await db.commit()
    return await currency_service.list_balances(wallet_id)


@router.get(
    "/wallets/{wallet_id}/settings-currency-ids",
    response_model=WalletSettingsCurrencyIds,
)
async def wallet_settings_currency_ids(
    wallet_id: int,
    user: User = Depends(get_current_user),
    wallet_service: WalletService = Depends(get_wallet_service),
    currency_service: WalletCurrencyService = Depends(get_wallet_currency_service),
):
    """
    IDs for currencies shown in wallet settings: earned by cards in this wallet,
    or explicitly user-tracked (added manually).
    """
    await wallet_service.get_user_wallet(wallet_id, user)
    earn = await currency_service.effective_earn_currency_ids(wallet_id)
    tracked = await currency_service.get_tracked_currency_ids(wallet_id)
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
    wallet_service: WalletService = Depends(get_wallet_service),
    currency_service: WalletCurrencyService = Depends(get_wallet_currency_service),
):
    """Start tracking a currency for this wallet (optional starting balance)."""
    await wallet_service.get_user_wallet(wallet_id, user)
    row = await currency_service.track_currency(
        wallet_id=wallet_id,
        currency_id=payload.currency_id,
        initial_balance=payload.initial_balance,
    )
    await db.commit()
    await db.refresh(row)
    return await currency_service.get_balance_with_currency(row.id)


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
    wallet_service: WalletService = Depends(get_wallet_service),
    currency_service: WalletCurrencyService = Depends(get_wallet_currency_service),
):
    """Update starting balance; total = initial + last projection earn from Calculate."""
    await wallet_service.get_user_wallet(wallet_id, user)
    row = await currency_service.set_initial_balance(
        wallet_id=wallet_id,
        currency_id=currency_id,
        initial_balance=payload.initial_balance,
    )
    await db.commit()
    return await currency_service.get_balance_with_currency(row.id)


@router.delete(
    "/wallets/{wallet_id}/currencies/{currency_id}/balance",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_wallet_currency_balance(
    wallet_id: int,
    currency_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    currency_service: WalletCurrencyService = Depends(get_wallet_currency_service),
):
    """Remove the wallet's balance record for a currency."""
    await wallet_service.get_user_wallet(wallet_id, user)
    await currency_service.delete_balance(wallet_id, currency_id)
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
    wallet_service: WalletService = Depends(get_wallet_service),
    currency_service: WalletCurrencyService = Depends(get_wallet_currency_service),
):
    """List all currencies with wallet-scoped CPP overrides applied."""
    await wallet_service.get_user_wallet(wallet_id, user)

    currencies_with_overrides = await currency_service.list_currencies_with_cpp(wallet_id)

    out = []
    for currency, override_cpp in currencies_with_overrides:
        schema = CurrencyRead.model_validate(currency)
        if override_cpp is not None:
            schema.user_cents_per_point = override_cpp
        else:
            schema.user_cents_per_point = currency.cents_per_point
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
    wallet_service: WalletService = Depends(get_wallet_service),
    currency_service: WalletCurrencyService = Depends(get_wallet_currency_service),
):
    """Set or update wallet-scoped cents-per-point for a currency."""
    await wallet_service.get_user_wallet(wallet_id, user)
    await currency_service.set_cpp(wallet_id, currency_id, payload.cents_per_point)
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
    wallet_service: WalletService = Depends(get_wallet_service),
    currency_service: WalletCurrencyService = Depends(get_wallet_currency_service),
):
    """Remove wallet-scoped CPP override (reverts to currency default)."""
    await wallet_service.get_user_wallet(wallet_id, user)
    await currency_service.delete_cpp(wallet_id, currency_id)
    await db.commit()
