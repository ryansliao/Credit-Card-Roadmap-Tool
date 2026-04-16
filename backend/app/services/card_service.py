"""Card library data access service."""

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
    Currency,
    RotatingCategory,
)
from .base import BaseService


# Fields that can be patched on the card library
CARD_LIBRARY_PATCH_FIELDS = frozenset({
    "sub_points", "sub_min_spend", "sub_months", "sub_cash",
    "annual_fee", "first_year_fee", "transfer_enabler",
    "annual_bonus", "annual_bonus_percent", "annual_bonus_first_year_only",
    "secondary_currency_id", "secondary_currency_rate", "secondary_currency_cap_rate",
    "accelerator_cost", "accelerator_spend_limit", "accelerator_bonus_multiplier",
    "accelerator_max_activations", "housing_tiered_enabled",
    "foreign_transaction_fee", "housing_fee_waived", "sub_secondary_points",
})


class CardService(BaseService[Card]):
    """Service for Card operations."""

    model = Card

    @staticmethod
    def load_opts():
        """Eager-load options for cards with all relationships."""
        return [
            selectinload(Card.issuer),
            selectinload(Card.co_brand),
            selectinload(Card.currency_obj),
            selectinload(Card.currency_obj).selectinload(Currency.converts_to_currency),
            selectinload(Card.secondary_currency_obj),
            selectinload(Card.secondary_currency_obj).selectinload(Currency.converts_to_currency),
            selectinload(Card.network_tier),
            selectinload(Card.multipliers).selectinload(CardCategoryMultiplier.spend_category),
            selectinload(Card.multiplier_groups).selectinload(CardMultiplierGroup.categories).selectinload(CardCategoryMultiplier.spend_category),
            selectinload(Card.rotating_categories).selectinload(RotatingCategory.spend_category),
        ]

    async def list_all_with_opts(self) -> list[Card]:
        """List all cards with full relationship loading.

        Returns:
            List of cards with all relationships eager-loaded.
        """
        result = await self.db.execute(
            select(Card).options(*self.load_opts())
        )
        return list(result.scalars().all())

    async def get_or_404(self, card_id: int, options: list | None = None) -> Card:
        """Fetch a card by ID or raise 404.

        Args:
            card_id: The card ID.
            options: Optional eager-load options.

        Returns:
            The card.

        Raises:
            HTTPException: 404 if not found.
        """
        stmt = select(Card).where(Card.id == card_id)
        if options:
            stmt = stmt.options(*options)
        result = await self.db.execute(stmt)
        card = result.scalar_one_or_none()
        if not card:
            raise HTTPException(
                status_code=404,
                detail=f"Card {card_id} not found",
            )
        return card

    async def get_with_opts(self, card_id: int) -> Optional[Card]:
        """Fetch a card with full relationship loading.

        Args:
            card_id: The card ID.

        Returns:
            The card if found, None otherwise.
        """
        result = await self.db.execute(
            select(Card)
            .where(Card.id == card_id)
            .options(*self.load_opts())
        )
        return result.scalar_one_or_none()

    async def update_library_fields(self, card: Card, **updates) -> Card:
        """Update editable library fields on a card.

        Only fields in CARD_LIBRARY_PATCH_FIELDS are updated.

        Args:
            card: The card to update.
            **updates: Field names and values to update.

        Returns:
            The updated card.
        """
        for key, value in updates.items():
            if key in CARD_LIBRARY_PATCH_FIELDS:
                setattr(card, key, value)
        return card

    async def validate_ids(self, card_ids: list[int]) -> list[int]:
        """Deduplicate and validate that each card ID exists.

        Args:
            card_ids: List of card IDs to validate.

        Returns:
            Sorted list of unique valid card IDs.

        Raises:
            HTTPException: 400 if any card ID is invalid.
        """
        unique = sorted(set(card_ids))
        if not unique:
            return []

        result = await self.db.execute(
            select(Card.id).where(Card.id.in_(unique))
        )
        found = {row[0] for row in result.all()}
        missing = [cid for cid in unique if cid not in found]

        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown card id(s): {missing}",
            )
        return unique


def get_card_service(db: AsyncSession = Depends(get_db)) -> CardService:
    """FastAPI dependency for CardService."""
    return CardService(db)
