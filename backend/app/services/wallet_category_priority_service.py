"""Wallet card category priority data access service."""

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models import WalletCard, WalletCardCategoryPriority


class WalletCategoryPriorityService:
    """Service for wallet card category priority operations.

    Category priorities pin a spend category to a specific wallet card,
    forcing allocation regardless of normal scoring.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_for_wallet(self, wallet_id: int) -> list[WalletCardCategoryPriority]:
        """List all category priorities for a wallet.

        Args:
            wallet_id: The wallet ID.

        Returns:
            List of category priority rows with spend_category eager-loaded.
        """
        result = await self.db.execute(
            select(WalletCardCategoryPriority)
            .options(selectinload(WalletCardCategoryPriority.spend_category))
            .where(WalletCardCategoryPriority.wallet_id == wallet_id)
        )
        return list(result.scalars().all())

    async def get_wallet_card(
        self, wallet_id: int, card_id: int
    ) -> WalletCard | None:
        """Get a wallet card by wallet_id and card_id.

        Args:
            wallet_id: The wallet ID.
            card_id: The card ID.

        Returns:
            The wallet card if found, None otherwise.
        """
        result = await self.db.execute(
            select(WalletCard).where(
                WalletCard.wallet_id == wallet_id,
                WalletCard.card_id == card_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_wallet_card_or_404(
        self, wallet_id: int, card_id: int
    ) -> WalletCard:
        """Get a wallet card or raise 404.

        Args:
            wallet_id: The wallet ID.
            card_id: The card ID.

        Returns:
            The wallet card.

        Raises:
            HTTPException: 404 if not found.
        """
        wc = await self.get_wallet_card(wallet_id, card_id)
        if not wc:
            raise HTTPException(status_code=404, detail="Wallet card not found")
        return wc

    async def check_conflicts(
        self,
        wallet_id: int,
        wallet_card_id: int,
        category_ids: set[int],
    ) -> list[int]:
        """Check for categories already claimed by other cards in the wallet.

        Args:
            wallet_id: The wallet ID.
            wallet_card_id: The wallet card ID requesting these categories.
            category_ids: Set of spend category IDs to check.

        Returns:
            List of conflicting category IDs (claimed by other cards).
        """
        if not category_ids:
            return []

        result = await self.db.execute(
            select(WalletCardCategoryPriority).where(
                WalletCardCategoryPriority.wallet_id == wallet_id,
                WalletCardCategoryPriority.spend_category_id.in_(category_ids),
                WalletCardCategoryPriority.wallet_card_id != wallet_card_id,
            )
        )
        conflict_rows = result.scalars().all()
        return sorted({r.spend_category_id for r in conflict_rows})

    async def replace_for_wallet_card(
        self,
        wallet_id: int,
        wallet_card_id: int,
        category_ids: set[int],
    ) -> list[WalletCardCategoryPriority]:
        """Replace all category priorities for a wallet card.

        Deletes existing priorities and inserts new ones. This is idempotent.

        Args:
            wallet_id: The wallet ID.
            wallet_card_id: The wallet card ID.
            category_ids: Set of spend category IDs to pin to this card.

        Returns:
            List of newly created priority rows with spend_category loaded.
        """
        # Delete existing priorities for this wallet card
        existing = await self.db.execute(
            select(WalletCardCategoryPriority).where(
                WalletCardCategoryPriority.wallet_card_id == wallet_card_id
            )
        )
        for row in existing.scalars().all():
            await self.db.delete(row)
        await self.db.flush()

        # Insert new priorities
        for cat_id in category_ids:
            self.db.add(
                WalletCardCategoryPriority(
                    wallet_id=wallet_id,
                    wallet_card_id=wallet_card_id,
                    spend_category_id=cat_id,
                )
            )

        # Return the new rows with relationships loaded
        result = await self.db.execute(
            select(WalletCardCategoryPriority)
            .options(selectinload(WalletCardCategoryPriority.spend_category))
            .where(WalletCardCategoryPriority.wallet_card_id == wallet_card_id)
        )
        return list(result.scalars().all())

    async def delete_for_wallet_card(self, wallet_card_id: int) -> None:
        """Delete all category priorities for a wallet card.

        Args:
            wallet_card_id: The wallet card ID.
        """
        existing = await self.db.execute(
            select(WalletCardCategoryPriority).where(
                WalletCardCategoryPriority.wallet_card_id == wallet_card_id
            )
        )
        for row in existing.scalars().all():
            await self.db.delete(row)


def get_wallet_category_priority_service(
    db: AsyncSession = Depends(get_db),
) -> WalletCategoryPriorityService:
    """FastAPI dependency for WalletCategoryPriorityService."""
    return WalletCategoryPriorityService(db)
