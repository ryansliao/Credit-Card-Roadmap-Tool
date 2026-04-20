"""Wallet-scoped cents-per-point override data access service."""

from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Currency, WalletCurrencyCpp
from .base import BaseService


class WalletCurrencyService(BaseService[WalletCurrencyCpp]):
    """Service for WalletCurrencyCpp (wallet-scoped CPP override) operations."""

    model = WalletCurrencyCpp

    async def get_currency_or_404(self, currency_id: int) -> Currency:
        """Fetch a currency or raise 404."""
        result = await self.db.execute(
            select(Currency).where(Currency.id == currency_id)
        )
        currency = result.scalar_one_or_none()
        if not currency:
            raise HTTPException(
                status_code=404,
                detail=f"Currency id={currency_id} not found",
            )
        return currency

    async def list_currencies_with_cpp(self, wallet_id: int) -> list[tuple[Currency, Optional[float]]]:
        """List all currencies with wallet-scoped CPP overrides.

        Returns list of (Currency, override_cpp) tuples. override_cpp is None if no override.
        """
        cpp_result = await self.db.execute(
            select(WalletCurrencyCpp).where(WalletCurrencyCpp.wallet_id == wallet_id)
        )
        overrides = {
            row.currency_id: row.cents_per_point
            for row in cpp_result.scalars().all()
        }

        cur_result = await self.db.execute(
            select(Currency).order_by(Currency.name)
        )
        currencies = cur_result.scalars().all()

        return [(c, overrides.get(c.id)) for c in currencies]

    async def get_cpp_override(
        self,
        wallet_id: int,
        currency_id: int,
    ) -> Optional[WalletCurrencyCpp]:
        """Get a CPP override row."""
        result = await self.db.execute(
            select(WalletCurrencyCpp).where(
                WalletCurrencyCpp.wallet_id == wallet_id,
                WalletCurrencyCpp.currency_id == currency_id,
            )
        )
        return result.scalar_one_or_none()

    async def set_cpp(
        self,
        wallet_id: int,
        currency_id: int,
        cents_per_point: float,
    ) -> None:
        """Set or update a CPP override."""
        await self.get_currency_or_404(currency_id)

        row = await self.get_cpp_override(wallet_id, currency_id)
        if row:
            row.cents_per_point = cents_per_point
        else:
            self.db.add(
                WalletCurrencyCpp(
                    wallet_id=wallet_id,
                    currency_id=currency_id,
                    cents_per_point=cents_per_point,
                )
            )

    async def delete_cpp(self, wallet_id: int, currency_id: int) -> None:
        """Delete a CPP override."""
        row = await self.get_cpp_override(wallet_id, currency_id)
        if not row:
            raise HTTPException(
                status_code=404,
                detail="No CPP override for this wallet/currency",
            )
        await self.db.delete(row)


def get_wallet_currency_service(db: AsyncSession = Depends(get_db)) -> WalletCurrencyService:
    """FastAPI dependency for WalletCurrencyService."""
    return WalletCurrencyService(db)
