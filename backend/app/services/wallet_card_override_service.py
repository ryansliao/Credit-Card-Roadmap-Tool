"""Wallet card override data access service.

Handles WalletCardCredit, WalletCardMultiplier, and WalletCardGroupSelection.
"""

from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models import (
    Card,
    CardCategoryMultiplier,
    CardMultiplierGroup,
    Credit,
    RotatingCategory,
    SpendCategory,
    WalletCard,
    WalletCardCredit,
    WalletCardGroupSelection,
    WalletCardMultiplier,
)
from .base import BaseService


class WalletCardOverrideService(BaseService[WalletCardCredit]):
    """Service for wallet card override operations.

    Handles credits, multipliers, and group selections for wallet cards.
    """

    model = WalletCardCredit

    async def get_wallet_card_or_404(
        self,
        wallet_id: int,
        card_id: int,
    ) -> WalletCard:
        """Fetch a wallet card by wallet and card ID.

        Args:
            wallet_id: The wallet ID.
            card_id: The card ID.

        Returns:
            The WalletCard.

        Raises:
            HTTPException: 404 if not found.
        """
        result = await self.db.execute(
            select(WalletCard).where(
                WalletCard.wallet_id == wallet_id,
                WalletCard.card_id == card_id,
            )
        )
        wc = result.scalar_one_or_none()
        if not wc:
            raise HTTPException(status_code=404, detail="Wallet card not found")
        return wc

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

    # -------------------------------------------------------------------------
    # Multiplier Override methods
    # -------------------------------------------------------------------------

    async def list_multipliers(self, wallet_id: int) -> list[WalletCardMultiplier]:
        """List all multiplier overrides for a wallet.

        Args:
            wallet_id: The wallet ID.

        Returns:
            List of multiplier overrides.
        """
        result = await self.db.execute(
            select(WalletCardMultiplier)
            .options(selectinload(WalletCardMultiplier.spend_category))
            .where(WalletCardMultiplier.wallet_id == wallet_id)
            .order_by(WalletCardMultiplier.card_id, WalletCardMultiplier.category_id)
        )
        return list(result.scalars().all())

    async def get_card_or_404(self, card_id: int) -> Card:
        """Fetch a card or raise 404.

        Args:
            card_id: The card ID.

        Returns:
            The card.

        Raises:
            HTTPException: 404 if not found.
        """
        result = await self.db.execute(select(Card).where(Card.id == card_id))
        card = result.scalar_one_or_none()
        if not card:
            raise HTTPException(status_code=404, detail=f"Card {card_id} not found")
        return card

    async def get_spend_category_or_404(self, category_id: int) -> SpendCategory:
        """Fetch a spend category or raise 404.

        Args:
            category_id: The spend category ID.

        Returns:
            The spend category.

        Raises:
            HTTPException: 404 if not found.
        """
        result = await self.db.execute(
            select(SpendCategory).where(SpendCategory.id == category_id)
        )
        sc = result.scalar_one_or_none()
        if not sc:
            raise HTTPException(
                status_code=404,
                detail=f"SpendCategory id={category_id} not found",
            )
        return sc

    async def get_multiplier(
        self,
        wallet_id: int,
        card_id: int,
        category_id: int,
    ) -> Optional[WalletCardMultiplier]:
        """Get a multiplier override row.

        Args:
            wallet_id: The wallet ID.
            card_id: The card ID.
            category_id: The category ID.

        Returns:
            The multiplier override if found, None otherwise.
        """
        result = await self.db.execute(
            select(WalletCardMultiplier).where(
                WalletCardMultiplier.wallet_id == wallet_id,
                WalletCardMultiplier.card_id == card_id,
                WalletCardMultiplier.category_id == category_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_multiplier(
        self,
        wallet_id: int,
        card_id: int,
        category_id: int,
        multiplier: float,
    ) -> WalletCardMultiplier:
        """Create or update a multiplier override.

        Args:
            wallet_id: The wallet ID.
            card_id: The card ID.
            category_id: The category ID.
            multiplier: The override multiplier value.

        Returns:
            The multiplier override row.
        """
        await self.get_card_or_404(card_id)
        await self.get_spend_category_or_404(category_id)

        row = await self.get_multiplier(wallet_id, card_id, category_id)
        if row:
            row.multiplier = multiplier
        else:
            row = WalletCardMultiplier(
                wallet_id=wallet_id,
                card_id=card_id,
                category_id=category_id,
                multiplier=multiplier,
            )
            self.db.add(row)
            await self.db.flush()

        return row

    async def get_multiplier_with_category(
        self,
        multiplier_id: int,
    ) -> Optional[WalletCardMultiplier]:
        """Fetch a multiplier override with spend_category eager-loaded.

        Args:
            multiplier_id: The multiplier override ID.

        Returns:
            The multiplier override if found, None otherwise.
        """
        result = await self.db.execute(
            select(WalletCardMultiplier)
            .options(selectinload(WalletCardMultiplier.spend_category))
            .where(WalletCardMultiplier.id == multiplier_id)
        )
        return result.scalar_one_or_none()

    async def delete_multiplier(
        self,
        wallet_id: int,
        card_id: int,
        category_id: int,
    ) -> None:
        """Delete a multiplier override.

        Args:
            wallet_id: The wallet ID.
            card_id: The card ID.
            category_id: The category ID.

        Raises:
            HTTPException: 404 if not found.
        """
        row = await self.get_multiplier(wallet_id, card_id, category_id)
        if not row:
            raise HTTPException(
                status_code=404,
                detail="No multiplier override found",
            )
        await self.db.delete(row)

    # -------------------------------------------------------------------------
    # Group Selection methods
    # -------------------------------------------------------------------------

    async def list_group_selections(
        self,
        wallet_card_id: int,
    ) -> list[WalletCardGroupSelection]:
        """List group selections for a wallet card.

        Args:
            wallet_card_id: The WalletCard ID.

        Returns:
            List of group selections.
        """
        result = await self.db.execute(
            select(WalletCardGroupSelection)
            .options(selectinload(WalletCardGroupSelection.spend_category))
            .where(WalletCardGroupSelection.wallet_card_id == wallet_card_id)
        )
        return list(result.scalars().all())

    async def get_multiplier_group_or_404(
        self,
        group_id: int,
        card_id: int,
    ) -> CardMultiplierGroup:
        """Fetch a multiplier group for a card.

        Args:
            group_id: The group ID.
            card_id: The card ID.

        Returns:
            The multiplier group with categories loaded.

        Raises:
            HTTPException: 404 if not found.
        """
        result = await self.db.execute(
            select(CardMultiplierGroup)
            .options(
                selectinload(CardMultiplierGroup.categories).selectinload(
                    CardCategoryMultiplier.spend_category
                ),
                selectinload(CardMultiplierGroup.card)
                .selectinload(Card.rotating_categories)
                .selectinload(RotatingCategory.spend_category),
            )
            .where(
                CardMultiplierGroup.id == group_id,
                CardMultiplierGroup.card_id == card_id,
            )
        )
        grp = result.scalar_one_or_none()
        if not grp:
            raise HTTPException(
                status_code=404,
                detail="Multiplier group not found for this card",
            )
        return grp

    async def set_group_selections(
        self,
        wallet_card_id: int,
        group_id: int,
        card_id: int,
        spend_category_ids: list[int],
    ) -> list[WalletCardGroupSelection]:
        """Set group selections for a wallet card.

        Replaces any existing selections for this group.

        Args:
            wallet_card_id: The WalletCard ID.
            group_id: The multiplier group ID.
            card_id: The card ID (for validation).
            spend_category_ids: List of category IDs to select.

        Returns:
            The new list of group selections.

        Raises:
            HTTPException: 422 if wrong number of categories or invalid category.
        """
        grp = await self.get_multiplier_group_or_404(group_id, card_id)

        # Delete existing selections
        existing = await self.db.execute(
            select(WalletCardGroupSelection).where(
                WalletCardGroupSelection.wallet_card_id == wallet_card_id,
                WalletCardGroupSelection.multiplier_group_id == group_id,
            )
        )
        for row in existing.scalars().all():
            await self.db.delete(row)
        await self.db.flush()

        if not spend_category_ids:
            return []

        # Validate count
        top_n = grp.top_n_categories
        if top_n and len(spend_category_ids) != top_n:
            raise HTTPException(
                status_code=422,
                detail=f"Must select exactly {top_n} categories, got {len(spend_category_ids)}",
            )

        # Validate category IDs
        valid_cat_ids = {c.category_id for c in grp.categories}
        for cat_id in spend_category_ids:
            if cat_id not in valid_cat_ids:
                raise HTTPException(
                    status_code=422,
                    detail=f"Category {cat_id} is not in this multiplier group",
                )

        # Create new selections
        for cat_id in spend_category_ids:
            self.db.add(
                WalletCardGroupSelection(
                    wallet_card_id=wallet_card_id,
                    multiplier_group_id=group_id,
                    spend_category_id=cat_id,
                )
            )

        await self.db.flush()

        # Return the new selections
        result = await self.db.execute(
            select(WalletCardGroupSelection)
            .options(selectinload(WalletCardGroupSelection.spend_category))
            .where(
                WalletCardGroupSelection.wallet_card_id == wallet_card_id,
                WalletCardGroupSelection.multiplier_group_id == group_id,
            )
        )
        return list(result.scalars().all())

    async def delete_group_selections(
        self,
        wallet_card_id: int,
        group_id: int,
    ) -> None:
        """Delete all group selections for a wallet card and group.

        Args:
            wallet_card_id: The WalletCard ID.
            group_id: The multiplier group ID.
        """
        existing = await self.db.execute(
            select(WalletCardGroupSelection).where(
                WalletCardGroupSelection.wallet_card_id == wallet_card_id,
                WalletCardGroupSelection.multiplier_group_id == group_id,
            )
        )
        for row in existing.scalars().all():
            await self.db.delete(row)


def get_wallet_card_override_service(
    db: AsyncSession = Depends(get_db),
) -> WalletCardOverrideService:
    """FastAPI dependency for WalletCardOverrideService."""
    return WalletCardOverrideService(db)
