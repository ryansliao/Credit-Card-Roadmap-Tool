"""Wallet-scoped cents-per-point override endpoints."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth import get_current_user
from ...database import get_db
from ...models import User
from ...schemas import CurrencyRead, WalletCurrencyCppSet
from ...services import (
    WalletService,
    WalletCurrencyService,
    get_wallet_service,
    get_wallet_currency_service,
)

router = APIRouter(tags=["wallets"])


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
