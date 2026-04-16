"""Travel portal data access service."""

from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models import Card, TravelPortal
from .base import BaseService


class TravelPortalService(BaseService[TravelPortal]):
    """Service for TravelPortal operations."""

    model = TravelPortal

    async def list_all_with_cards(self) -> list[TravelPortal]:
        """List all travel portals with cards eager-loaded.

        Returns:
            List of travel portals ordered by name.
        """
        result = await self.db.execute(
            select(TravelPortal)
            .options(selectinload(TravelPortal.cards))
            .order_by(TravelPortal.name)
        )
        return list(result.scalars().all())

    async def get_with_cards(self, portal_id: int) -> Optional[TravelPortal]:
        """Fetch a travel portal with cards eager-loaded.

        Args:
            portal_id: The portal ID.

        Returns:
            The portal if found, None otherwise.
        """
        result = await self.db.execute(
            select(TravelPortal)
            .options(selectinload(TravelPortal.cards))
            .where(TravelPortal.id == portal_id)
        )
        return result.scalar_one_or_none()

    async def get_or_404(self, portal_id: int) -> TravelPortal:
        """Fetch a travel portal or raise 404.

        Args:
            portal_id: The portal ID.

        Returns:
            The portal.

        Raises:
            HTTPException: 404 if not found.
        """
        result = await self.db.execute(
            select(TravelPortal)
            .options(selectinload(TravelPortal.cards))
            .where(TravelPortal.id == portal_id)
        )
        portal = result.scalar_one_or_none()
        if not portal:
            raise HTTPException(
                status_code=404,
                detail=f"Travel portal id={portal_id} not found",
            )
        return portal

    async def get_by_name(self, name: str) -> Optional[TravelPortal]:
        """Find a travel portal by name.

        Args:
            name: The portal name.

        Returns:
            The portal if found, None otherwise.
        """
        result = await self.db.execute(
            select(TravelPortal).where(TravelPortal.name == name)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        name: str,
        card_ids: Optional[list[int]] = None,
    ) -> TravelPortal:
        """Create a new travel portal.

        Args:
            name: The portal name.
            card_ids: Optional list of card IDs to link.

        Returns:
            The newly created portal.

        Raises:
            HTTPException: 409 if name exists, 404 if any card ID is invalid.
        """
        name = name.strip()
        existing = await self.get_by_name(name)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Travel portal '{name}' already exists",
            )

        portal = TravelPortal(name=name)

        if card_ids:
            cards = await self._validate_and_get_cards(card_ids)
            portal.cards = cards

        self.db.add(portal)
        await self.db.flush()
        return portal

    async def update(
        self,
        portal: TravelPortal,
        name: Optional[str] = None,
        card_ids: Optional[list[int]] = None,
    ) -> TravelPortal:
        """Update a travel portal.

        Args:
            portal: The portal to update.
            name: New name (optional).
            card_ids: New list of card IDs (optional, replaces existing).

        Returns:
            The updated portal.

        Raises:
            HTTPException: 409 if name conflicts, 404 if any card ID is invalid.
        """
        if name is not None:
            new_name = name.strip()
            if new_name != portal.name:
                clash = await self.get_by_name(new_name)
                if clash:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Travel portal '{new_name}' already exists",
                    )
                portal.name = new_name

        if card_ids is not None:
            if card_ids:
                cards = await self._validate_and_get_cards(card_ids)
                portal.cards = cards
            else:
                portal.cards = []

        return portal

    async def _validate_and_get_cards(self, card_ids: list[int]) -> list[Card]:
        """Validate card IDs and return the Card objects.

        Args:
            card_ids: List of card IDs.

        Returns:
            List of Card objects.

        Raises:
            HTTPException: 404 if any card ID is invalid.
        """
        result = await self.db.execute(
            select(Card).where(Card.id.in_(card_ids))
        )
        cards = list(result.scalars().all())
        found_ids = {c.id for c in cards}
        missing = [cid for cid in card_ids if cid not in found_ids]

        if missing:
            raise HTTPException(
                status_code=404,
                detail=f"Card ids not found: {missing}",
            )
        return cards


def get_travel_portal_service(db: AsyncSession = Depends(get_db)) -> TravelPortalService:
    """FastAPI dependency for TravelPortalService."""
    return TravelPortalService(db)
