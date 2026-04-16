"""Wallet currency balance and CPP override data access service."""

from datetime import date
from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models import (
    Card,
    Currency,
    WalletCard,
    WalletCurrencyBalance,
    WalletCurrencyCpp,
)
from .base import BaseService


class WalletCurrencyService(BaseService[WalletCurrencyBalance]):
    """Service for WalletCurrencyBalance and WalletCurrencyCpp operations."""

    model = WalletCurrencyBalance

    async def effective_earn_currency_ids(self, wallet_id: int) -> set[int]:
        """Get currency IDs this wallet's cards effectively earn.

        Includes upgrade rule matching (e.g. UR Cash -> UR when a UR card is
        also in the wallet) and secondary currencies (e.g. Bilt Cash).
        Only in_wallet and future_cards panels are considered.

        Args:
            wallet_id: The wallet ID.

        Returns:
            Set of effective currency IDs.
        """
        result = await self.db.execute(
            select(WalletCard)
            .options(
                selectinload(WalletCard.card)
                .selectinload(Card.currency_obj)
                .selectinload(Currency.converts_to_currency),
            )
            .where(
                WalletCard.wallet_id == wallet_id,
                WalletCard.panel.in_(("in_wallet", "future_cards")),
            )
        )
        wcs = list(result.scalars().all())
        if not wcs:
            return set()

        wallet_currency_ids = {wc.card.currency_id for wc in wcs}
        effective_ids: set[int] = set()

        for wc in wcs:
            cur = wc.card.currency_obj
            conv = cur.converts_to_currency
            if conv is not None and conv.id in wallet_currency_ids:
                effective_ids.add(conv.id)
            else:
                effective_ids.add(cur.id)
            # Include secondary currencies (e.g. Bilt Cash)
            sec_id = wc.card.secondary_currency_id
            if sec_id is not None:
                effective_ids.add(sec_id)

        return effective_ids

    async def ensure_earning_currency_rows(self, wallet_id: int) -> None:
        """Create WalletCurrencyBalance rows for each effective earn currency.

        Only creates rows that don't already exist.

        Args:
            wallet_id: The wallet ID.
        """
        effective_ids = await self.effective_earn_currency_ids(wallet_id)
        if not effective_ids:
            return

        today = date.today()
        for cid in effective_ids:
            existing = await self.db.execute(
                select(WalletCurrencyBalance).where(
                    WalletCurrencyBalance.wallet_id == wallet_id,
                    WalletCurrencyBalance.currency_id == cid,
                )
            )
            if existing.scalar_one_or_none():
                continue

            self.db.add(
                WalletCurrencyBalance(
                    wallet_id=wallet_id,
                    currency_id=cid,
                    initial_balance=0.0,
                    projection_earn=0.0,
                    balance=0.0,
                    user_tracked=False,
                    updated_date=today,
                )
            )

    async def sync_balances_from_currency_pts(
        self,
        wallet_id: int,
        currency_pts_by_id: dict[int, float],
    ) -> None:
        """Update projection earn per currency and recalculate balances.

        Args:
            wallet_id: The wallet ID.
            currency_pts_by_id: Map of currency_id to projected points.
        """
        today = date.today()
        valid_ids_result = await self.db.execute(select(Currency.id))
        valid_ids = set(valid_ids_result.scalars().all())
        active_currency_ids = await self.effective_earn_currency_ids(wallet_id)

        res = await self.db.execute(
            select(WalletCurrencyBalance)
            .options(selectinload(WalletCurrencyBalance.currency))
            .where(WalletCurrencyBalance.wallet_id == wallet_id)
        )
        rows = list(res.scalars().all())
        by_cid = {r.currency_id: r for r in rows}

        # Update existing rows, remove orphans
        for row in rows:
            if row.currency_id not in active_currency_ids and not row.user_tracked:
                await self.db.delete(row)
                by_cid.pop(row.currency_id, None)
                continue

            earn = float(currency_pts_by_id.get(row.currency_id, 0.0))
            row.projection_earn = earn
            row.balance = round(row.initial_balance + earn, 4)
            row.updated_date = today

        # Create new rows for currencies with earn
        for cid, earn in currency_pts_by_id.items():
            if earn <= 0 or cid not in valid_ids:
                continue
            if cid in by_cid:
                continue

            new_row = WalletCurrencyBalance(
                wallet_id=wallet_id,
                currency_id=cid,
                initial_balance=0.0,
                projection_earn=float(earn),
                balance=float(earn),
                user_tracked=False,
                updated_date=today,
            )
            self.db.add(new_row)
            by_cid[cid] = new_row

    async def list_balances(self, wallet_id: int) -> list[WalletCurrencyBalance]:
        """List currency balances for a wallet.

        Args:
            wallet_id: The wallet ID.

        Returns:
            List of currency balances with currency eager-loaded.
        """
        result = await self.db.execute(
            select(WalletCurrencyBalance)
            .options(selectinload(WalletCurrencyBalance.currency))
            .where(WalletCurrencyBalance.wallet_id == wallet_id)
            .order_by(WalletCurrencyBalance.currency_id)
        )
        return list(result.scalars().all())

    async def get_tracked_currency_ids(self, wallet_id: int) -> set[int]:
        """Get IDs of user-tracked currencies for a wallet.

        Args:
            wallet_id: The wallet ID.

        Returns:
            Set of tracked currency IDs.
        """
        result = await self.db.execute(
            select(WalletCurrencyBalance.currency_id).where(
                WalletCurrencyBalance.wallet_id == wallet_id,
                WalletCurrencyBalance.user_tracked.is_(True),
            )
        )
        return set(result.scalars().all())

    async def get_currency_or_404(self, currency_id: int) -> Currency:
        """Fetch a currency or raise 404.

        Args:
            currency_id: The currency ID.

        Returns:
            The currency.

        Raises:
            HTTPException: 404 if not found.
        """
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

    async def get_balance(
        self,
        wallet_id: int,
        currency_id: int,
    ) -> Optional[WalletCurrencyBalance]:
        """Get a currency balance row for a wallet.

        Args:
            wallet_id: The wallet ID.
            currency_id: The currency ID.

        Returns:
            The balance row if found, None otherwise.
        """
        result = await self.db.execute(
            select(WalletCurrencyBalance).where(
                WalletCurrencyBalance.wallet_id == wallet_id,
                WalletCurrencyBalance.currency_id == currency_id,
            )
        )
        return result.scalar_one_or_none()

    async def track_currency(
        self,
        wallet_id: int,
        currency_id: int,
        initial_balance: float,
    ) -> WalletCurrencyBalance:
        """Start tracking a currency for a wallet.

        If the currency is already tracked, updates it.

        Args:
            wallet_id: The wallet ID.
            currency_id: The currency ID.
            initial_balance: The starting balance.

        Returns:
            The balance row.
        """
        await self.get_currency_or_404(currency_id)

        row = await self.get_balance(wallet_id, currency_id)
        today = date.today()

        if row:
            row.user_tracked = True
            row.initial_balance = initial_balance
            row.balance = round(row.initial_balance + row.projection_earn, 4)
            row.updated_date = today
        else:
            row = WalletCurrencyBalance(
                wallet_id=wallet_id,
                currency_id=currency_id,
                initial_balance=initial_balance,
                projection_earn=0.0,
                balance=initial_balance,
                user_tracked=True,
                updated_date=today,
            )
            self.db.add(row)
            await self.db.flush()

        return row

    async def set_initial_balance(
        self,
        wallet_id: int,
        currency_id: int,
        initial_balance: float,
    ) -> WalletCurrencyBalance:
        """Update the initial balance for a tracked currency.

        Args:
            wallet_id: The wallet ID.
            currency_id: The currency ID.
            initial_balance: The new initial balance.

        Returns:
            The updated balance row.

        Raises:
            HTTPException: 404 if the currency is not tracked.
        """
        await self.get_currency_or_404(currency_id)

        row = await self.get_balance(wallet_id, currency_id)
        if not row:
            raise HTTPException(
                status_code=404,
                detail="Track this currency first (POST /currency-balances) before editing initial balance",
            )

        row.initial_balance = initial_balance
        row.balance = round(row.initial_balance + row.projection_earn, 4)
        row.updated_date = date.today()
        return row

    async def delete_balance(self, wallet_id: int, currency_id: int) -> None:
        """Delete a currency balance record.

        Args:
            wallet_id: The wallet ID.
            currency_id: The currency ID.

        Raises:
            HTTPException: 404 if not found.
        """
        row = await self.get_balance(wallet_id, currency_id)
        if not row:
            raise HTTPException(
                status_code=404,
                detail="No balance record found for this wallet and currency",
            )
        await self.db.delete(row)

    async def delete_orphan_balances(
        self,
        wallet_id: int,
        keep_currency_ids: set[int],
    ) -> None:
        """Delete currency balance rows not in the keep set.

        Args:
            wallet_id: The wallet ID.
            keep_currency_ids: Set of currency IDs to keep.
        """
        query = select(WalletCurrencyBalance).where(
            WalletCurrencyBalance.wallet_id == wallet_id,
        )
        if keep_currency_ids:
            query = query.where(
                WalletCurrencyBalance.currency_id.not_in(keep_currency_ids)
            )

        result = await self.db.execute(query)
        for row in result.scalars().all():
            await self.db.delete(row)

    async def get_balance_with_currency(
        self,
        balance_id: int,
    ) -> Optional[WalletCurrencyBalance]:
        """Fetch a balance row with currency eager-loaded.

        Args:
            balance_id: The balance row ID.

        Returns:
            The balance row if found, None otherwise.
        """
        result = await self.db.execute(
            select(WalletCurrencyBalance)
            .options(selectinload(WalletCurrencyBalance.currency))
            .where(WalletCurrencyBalance.id == balance_id)
        )
        return result.scalar_one_or_none()

    # -------------------------------------------------------------------------
    # CPP Override methods
    # -------------------------------------------------------------------------

    async def list_currencies_with_cpp(self, wallet_id: int) -> list[tuple[Currency, Optional[float]]]:
        """List all currencies with wallet-scoped CPP overrides.

        Args:
            wallet_id: The wallet ID.

        Returns:
            List of (Currency, override_cpp) tuples. override_cpp is None if no override.
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
        """Get a CPP override row.

        Args:
            wallet_id: The wallet ID.
            currency_id: The currency ID.

        Returns:
            The CPP override row if found, None otherwise.
        """
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
        """Set or update a CPP override.

        Args:
            wallet_id: The wallet ID.
            currency_id: The currency ID.
            cents_per_point: The CPP value.
        """
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
        """Delete a CPP override.

        Args:
            wallet_id: The wallet ID.
            currency_id: The currency ID.

        Raises:
            HTTPException: 404 if not found.
        """
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
