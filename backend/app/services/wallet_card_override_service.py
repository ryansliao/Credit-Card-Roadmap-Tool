"""Wallet card override data access service.

Handles WalletCardCredit (per-wallet-card statement credit valuations).
"""

from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models import (
    Credit,
    WalletCardCredit,
)
from .base import BaseService


class WalletCardOverrideService(BaseService[WalletCardCredit]):
    """Service for wallet card credit-override operations."""

    model = WalletCardCredit

    # -------------------------------------------------------------------------
    # Credit Override methods
    # -------------------------------------------------------------------------

    async def list_credits(self, wallet_card_id: int) -> list[WalletCardCredit]:
        """List credit overrides for a wallet card.

        Args:
            wallet_card_id: The WalletCard ID.

        Returns:
            List of credit overrides with library_credit eager-loaded.
        """
        result = await self.db.execute(
            select(WalletCardCredit)
            .options(selectinload(WalletCardCredit.library_credit))
            .where(WalletCardCredit.wallet_card_id == wallet_card_id)
            .order_by(WalletCardCredit.library_credit_id)
        )
        return list(result.scalars().all())

    async def get_library_credit_or_404(self, credit_id: int) -> Credit:
        """Fetch a library credit or raise 404.

        Args:
            credit_id: The credit ID.

        Returns:
            The credit.

        Raises:
            HTTPException: 404 if not found.
        """
        result = await self.db.execute(
            select(Credit).where(Credit.id == credit_id)
        )
        credit = result.scalar_one_or_none()
        if not credit:
            raise HTTPException(
                status_code=404,
                detail=f"Credit id={credit_id} not found in library",
            )
        return credit

    async def get_credit(
        self,
        wallet_card_id: int,
        library_credit_id: int,
    ) -> Optional[WalletCardCredit]:
        """Get a credit override row.

        Args:
            wallet_card_id: The WalletCard ID.
            library_credit_id: The library credit ID.

        Returns:
            The credit override if found, None otherwise.
        """
        result = await self.db.execute(
            select(WalletCardCredit).where(
                WalletCardCredit.wallet_card_id == wallet_card_id,
                WalletCardCredit.library_credit_id == library_credit_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_credit(
        self,
        wallet_card_id: int,
        library_credit_id: int,
        value: float,
    ) -> WalletCardCredit:
        """Create or update a credit override.

        Args:
            wallet_card_id: The WalletCard ID.
            library_credit_id: The library credit ID.
            value: The override value.

        Returns:
            The credit override row.
        """
        await self.get_library_credit_or_404(library_credit_id)

        row = await self.get_credit(wallet_card_id, library_credit_id)
        if row:
            row.value = value
        else:
            row = WalletCardCredit(
                wallet_card_id=wallet_card_id,
                library_credit_id=library_credit_id,
                value=value,
            )
            self.db.add(row)
            await self.db.flush()

        return row

    async def get_credit_with_library(
        self,
        credit_id: int,
    ) -> Optional[WalletCardCredit]:
        """Fetch a credit override with library_credit eager-loaded.

        Args:
            credit_id: The credit override ID.

        Returns:
            The credit override if found, None otherwise.
        """
        result = await self.db.execute(
            select(WalletCardCredit)
            .options(selectinload(WalletCardCredit.library_credit))
            .where(WalletCardCredit.id == credit_id)
        )
        return result.scalar_one_or_none()

    async def delete_credit(
        self,
        wallet_card_id: int,
        library_credit_id: int,
    ) -> None:
        """Delete a credit override.

        Args:
            wallet_card_id: The WalletCard ID.
            library_credit_id: The library credit ID.

        Raises:
            HTTPException: 404 if not found.
        """
        row = await self.get_credit(wallet_card_id, library_credit_id)
        if not row:
            raise HTTPException(status_code=404, detail="No credit override found")
        await self.db.delete(row)


def get_wallet_card_override_service(
    db: AsyncSession = Depends(get_db),
) -> WalletCardOverrideService:
    """FastAPI dependency for WalletCardOverrideService."""
    return WalletCardOverrideService(db)
