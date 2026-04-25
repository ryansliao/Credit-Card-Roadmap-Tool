"""Wallet data access service (singular wallet per user).

Owned-card CRUD lives in :class:`CardInstanceService`. Calc-config /
snapshot persistence lives on :class:`ScenarioService`. This service is
intentionally minimal: get-or-create the wallet, fetch by id, partial
update.
"""

from datetime import date
from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import User, Wallet
from .base import BaseService


class WalletService(BaseService[Wallet]):
    """Wallet CRUD (one wallet per user)."""

    model = Wallet

    async def get_user_wallet(self, wallet_id: int, user: User) -> Wallet:
        """Load a wallet by ID and verify ownership.

        Raises HTTPException 404 if not found, 403 if owned by another user.
        """
        wallet = await self.get_by_id(wallet_id)
        if not wallet:
            raise HTTPException(
                status_code=404,
                detail=f"Wallet {wallet_id} not found",
            )
        if wallet.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not your wallet")
        return wallet

    async def get_for_user(self, user_id: int) -> Optional[Wallet]:
        """Return the user's single wallet, or None if not yet created."""
        result = await self.db.execute(
            select(Wallet).where(Wallet.user_id == user_id).limit(1)
        )
        return result.scalar_one_or_none()

    async def user_has_wallet(self, user_id: int) -> bool:
        result = await self.db.execute(
            select(Wallet.id).where(Wallet.user_id == user_id).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def create(
        self,
        user_id: int,
        name: str,
        description: Optional[str] = None,
        as_of_date: Optional[date] = None,
    ) -> Wallet:
        """Create a new wallet for the user. Routers should use the
        get-or-create pattern (see ``routers/wallet/wallets.py``) rather
        than calling this directly outside of first-time wallet creation."""
        wallet = Wallet(
            user_id=user_id,
            name=name,
            description=description,
        )
        if as_of_date is not None and hasattr(wallet, "as_of_date"):
            wallet.as_of_date = as_of_date
        self.db.add(wallet)
        await self.db.flush()
        return wallet

    async def update(self, wallet: Wallet, **updates) -> Wallet:
        """Partial update — None values are skipped."""
        for field, value in updates.items():
            if value is not None and hasattr(wallet, field):
                setattr(wallet, field, value)
        return wallet


def get_wallet_service(db: AsyncSession = Depends(get_db)) -> WalletService:
    """FastAPI dependency for WalletService."""
    return WalletService(db)
