"""Wallet spend item data access service."""

from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..constants import ALL_OTHER_CATEGORY
from ..database import get_db
from ..models import SpendCategory, Wallet, WalletSpendItem
from .base import BaseService


class WalletSpendService(BaseService[WalletSpendItem]):
    """Service for WalletSpendItem operations."""

    model = WalletSpendItem

    @staticmethod
    def load_opts():
        """Eager-load options for spend items with category hierarchy."""
        return [
            selectinload(WalletSpendItem.spend_category)
            .selectinload(SpendCategory.children)
            .selectinload(SpendCategory.children),
        ]

    async def list_for_wallet(self, wallet_id: int) -> list[WalletSpendItem]:
        """List spend items for a wallet, ordered by amount desc then category name.

        Args:
            wallet_id: The wallet ID.

        Returns:
            List of spend items with spend_category eager-loaded.
        """
        result = await self.db.execute(
            select(WalletSpendItem)
            .options(*self.load_opts())
            .where(WalletSpendItem.wallet_id == wallet_id)
            .join(WalletSpendItem.spend_category)
            .order_by(WalletSpendItem.amount.desc(), SpendCategory.category)
        )
        return list(result.scalars().all())

    async def get_by_wallet_and_category(
        self,
        wallet_id: int,
        spend_category_id: int,
    ) -> Optional[WalletSpendItem]:
        """Find a spend item by wallet and category.

        Args:
            wallet_id: The wallet ID.
            spend_category_id: The spend category ID.

        Returns:
            The spend item if found, None otherwise.
        """
        result = await self.db.execute(
            select(WalletSpendItem).where(
                WalletSpendItem.wallet_id == wallet_id,
                WalletSpendItem.spend_category_id == spend_category_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_spend_category_or_422(self, category_id: int) -> SpendCategory:
        """Fetch a spend category or raise 422.

        Args:
            category_id: The spend category ID.

        Returns:
            The spend category.

        Raises:
            HTTPException: 422 if not found.
        """
        result = await self.db.execute(
            select(SpendCategory).where(SpendCategory.id == category_id)
        )
        sc = result.scalar_one_or_none()
        if not sc:
            raise HTTPException(
                status_code=422,
                detail=f"SpendCategory id={category_id} not found",
            )
        return sc

    async def create(
        self,
        wallet_id: int,
        spend_category_id: int,
        amount: float,
    ) -> WalletSpendItem:
        """Create a new spend item.

        Args:
            wallet_id: The wallet ID.
            spend_category_id: The spend category ID.
            amount: The annual spend amount.

        Returns:
            The newly created spend item.

        Raises:
            HTTPException: 403 if category is system, 409 if already exists.
        """
        sc = await self.get_spend_category_or_422(spend_category_id)

        if sc.is_system:
            raise HTTPException(
                status_code=403,
                detail=f"'{sc.category}' is a system category; update its amount via PUT instead",
            )

        existing = await self.get_by_wallet_and_category(wallet_id, spend_category_id)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"A spend item for '{sc.category}' already exists in this wallet",
            )

        item = WalletSpendItem(
            wallet_id=wallet_id,
            spend_category_id=spend_category_id,
            amount=amount,
        )
        self.db.add(item)
        await self.db.flush()
        return item

    async def get_with_opts(self, item_id: int) -> Optional[WalletSpendItem]:
        """Fetch a spend item with eager-loaded relationships.

        Args:
            item_id: The spend item ID.

        Returns:
            The spend item if found, None otherwise.
        """
        result = await self.db.execute(
            select(WalletSpendItem)
            .options(*self.load_opts())
            .where(WalletSpendItem.id == item_id)
        )
        return result.scalar_one_or_none()

    async def get_for_wallet_or_404(
        self,
        wallet_id: int,
        item_id: int,
    ) -> WalletSpendItem:
        """Fetch a spend item belonging to a wallet or raise 404.

        Args:
            wallet_id: The wallet ID.
            item_id: The spend item ID.

        Returns:
            The spend item.

        Raises:
            HTTPException: 404 if not found.
        """
        result = await self.db.execute(
            select(WalletSpendItem)
            .options(selectinload(WalletSpendItem.spend_category))
            .where(
                WalletSpendItem.id == item_id,
                WalletSpendItem.wallet_id == wallet_id,
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise HTTPException(
                status_code=404,
                detail=f"Spend item {item_id} not found",
            )
        return item

    async def update_amount(self, item: WalletSpendItem, amount: float) -> WalletSpendItem:
        """Update the amount of a spend item.

        Args:
            item: The spend item to update.
            amount: The new amount.

        Returns:
            The updated spend item.
        """
        item.amount = amount
        return item

    async def delete(self, item: WalletSpendItem) -> None:
        """Delete a spend item.

        Args:
            item: The spend item to delete.

        Raises:
            HTTPException: 403 if the item is for a system category.
        """
        if item.spend_category and item.spend_category.is_system:
            raise HTTPException(
                status_code=403,
                detail=f"The '{item.spend_category.category}' item cannot be deleted",
            )
        await self.db.delete(item)

    async def ensure_all_other_item(self, wallet_id: int) -> None:
        """Ensure the wallet has a WalletSpendItem for the 'All Other' category.

        Creates one with amount=0 if missing. Idempotent.

        Args:
            wallet_id: The wallet ID.
        """
        # Verify wallet exists
        wallet_row = await self.db.execute(
            select(Wallet).where(Wallet.id == wallet_id)
        )
        if wallet_row.scalar_one_or_none() is None:
            return

        # Find 'All Other' category
        sc_result = await self.db.execute(
            select(SpendCategory).where(SpendCategory.category == ALL_OTHER_CATEGORY)
        )
        sc = sc_result.scalar_one_or_none()
        if sc is None:
            return

        # Check if item already exists
        existing = await self.db.execute(
            select(WalletSpendItem).where(
                WalletSpendItem.wallet_id == wallet_id,
                WalletSpendItem.spend_category_id == sc.id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            return

        # Create the item
        self.db.add(
            WalletSpendItem(wallet_id=wallet_id, spend_category_id=sc.id, amount=0.0)
        )


def get_wallet_spend_service(db: AsyncSession = Depends(get_db)) -> WalletSpendService:
    """FastAPI dependency for WalletSpendService."""
    return WalletSpendService(db)
