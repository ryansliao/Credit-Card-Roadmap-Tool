"""Wallet portal share data access service."""

from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models import TravelPortal, WalletPortalShare
from .base import BaseService


class WalletPortalService(BaseService[WalletPortalShare]):
    """Service for WalletPortalShare operations."""

    model = WalletPortalShare

    async def list_for_wallet(self, wallet_id: int) -> list[WalletPortalShare]:
        """List portal shares for a wallet.

        Args:
            wallet_id: The wallet ID.

        Returns:
            List of portal shares with travel_portal eager-loaded.
        """
        result = await self.db.execute(
            select(WalletPortalShare)
            .options(selectinload(WalletPortalShare.travel_portal))
            .where(WalletPortalShare.wallet_id == wallet_id)
            .order_by(WalletPortalShare.travel_portal_id)
        )
        return list(result.scalars().all())

    async def get_travel_portal_or_404(self, portal_id: int) -> TravelPortal:
        """Fetch a travel portal or raise 404.

        Args:
            portal_id: The travel portal ID.

        Returns:
            The travel portal.

        Raises:
            HTTPException: 404 if not found.
        """
        result = await self.db.execute(
            select(TravelPortal).where(TravelPortal.id == portal_id)
        )
        portal = result.scalar_one_or_none()
        if not portal:
            raise HTTPException(
                status_code=404,
                detail=f"Travel portal id={portal_id} not found",
            )
        return portal

    async def get_share(
        self,
        wallet_id: int,
        travel_portal_id: int,
    ) -> Optional[WalletPortalShare]:
        """Get a portal share row.

        Args:
            wallet_id: The wallet ID.
            travel_portal_id: The travel portal ID.

        Returns:
            The portal share if found, None otherwise.
        """
        result = await self.db.execute(
            select(WalletPortalShare).where(
                WalletPortalShare.wallet_id == wallet_id,
                WalletPortalShare.travel_portal_id == travel_portal_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_share(
        self,
        wallet_id: int,
        travel_portal_id: int,
        share: float,
    ) -> WalletPortalShare:
        """Create or update a portal share.

        Args:
            wallet_id: The wallet ID.
            travel_portal_id: The travel portal ID.
            share: The share percentage.

        Returns:
            The portal share row.
        """
        await self.get_travel_portal_or_404(travel_portal_id)

        row = await self.get_share(wallet_id, travel_portal_id)
        if row:
            row.share = share
        else:
            row = WalletPortalShare(
                wallet_id=wallet_id,
                travel_portal_id=travel_portal_id,
                share=share,
            )
            self.db.add(row)
            await self.db.flush()

        return row

    async def get_share_with_portal(
        self,
        share_id: int,
    ) -> Optional[WalletPortalShare]:
        """Fetch a portal share with travel_portal eager-loaded.

        Args:
            share_id: The portal share ID.

        Returns:
            The portal share if found, None otherwise.
        """
        result = await self.db.execute(
            select(WalletPortalShare)
            .options(selectinload(WalletPortalShare.travel_portal))
            .where(WalletPortalShare.id == share_id)
        )
        return result.scalar_one_or_none()

    async def delete_share(
        self,
        wallet_id: int,
        travel_portal_id: int,
    ) -> None:
        """Delete a portal share.

        Args:
            wallet_id: The wallet ID.
            travel_portal_id: The travel portal ID.

        Raises:
            HTTPException: 404 if not found.
        """
        row = await self.get_share(wallet_id, travel_portal_id)
        if not row:
            raise HTTPException(status_code=404, detail="Portal share not found")
        await self.db.delete(row)


def get_wallet_portal_service(db: AsyncSession = Depends(get_db)) -> WalletPortalService:
    """FastAPI dependency for WalletPortalService."""
    return WalletPortalService(db)
