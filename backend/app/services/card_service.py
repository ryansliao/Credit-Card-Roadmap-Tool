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
    CardInstance,
    CardMultiplierGroup,
    CoBrand,
    Currency,
    Issuer,
    NetworkTier,
    RotatingCategory,
    SpendCategory,
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
    "takeoff15_enabled",
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
            # Eager-load spend_category.children (two levels) so CardRead's
            # portal_premiums validator can expand Travel → Hotels/Airlines/…
            # without issuing per-row queries.
            selectinload(Card.multipliers)
            .selectinload(CardCategoryMultiplier.spend_category)
            .selectinload(SpendCategory.children)
            .selectinload(SpendCategory.children),
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

    async def _exists(self, model, id_: int) -> bool:
        result = await self.db.execute(select(model.id).where(model.id == id_))
        return result.scalar_one_or_none() is not None

    async def _validate_card_refs(
        self,
        *,
        issuer_id: int,
        currency_id: int,
        co_brand_id: int | None,
        network_tier_id: int | None,
        secondary_currency_id: int | None,
    ) -> None:
        if not await self._exists(Issuer, issuer_id):
            raise HTTPException(
                status_code=404, detail=f"Issuer id={issuer_id} not found"
            )
        if not await self._exists(Currency, currency_id):
            raise HTTPException(
                status_code=404, detail=f"Currency id={currency_id} not found"
            )
        if co_brand_id is not None and not await self._exists(CoBrand, co_brand_id):
            raise HTTPException(
                status_code=404, detail=f"CoBrand id={co_brand_id} not found"
            )
        if network_tier_id is not None and not await self._exists(
            NetworkTier, network_tier_id
        ):
            raise HTTPException(
                status_code=404, detail=f"NetworkTier id={network_tier_id} not found"
            )
        if secondary_currency_id is not None and not await self._exists(
            Currency, secondary_currency_id
        ):
            raise HTTPException(
                status_code=404,
                detail=f"Secondary currency id={secondary_currency_id} not found",
            )

    async def create(self, payload) -> Card:
        """Create a Card, validating name uniqueness and FK targets."""
        name = payload.name.strip()
        existing = await self.db.execute(select(Card).where(Card.name == name))
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=409, detail=f"Card '{payload.name}' already exists"
            )
        await self._validate_card_refs(
            issuer_id=payload.issuer_id,
            currency_id=payload.currency_id,
            co_brand_id=payload.co_brand_id,
            network_tier_id=payload.network_tier_id,
            secondary_currency_id=payload.secondary_currency_id,
        )
        card = Card(
            name=name,
            issuer_id=payload.issuer_id,
            co_brand_id=payload.co_brand_id,
            currency_id=payload.currency_id,
            annual_fee=payload.annual_fee,
            first_year_fee=payload.first_year_fee,
            business=payload.business,
            network_tier_id=payload.network_tier_id,
            sub_points=payload.sub_points,
            sub_min_spend=payload.sub_min_spend,
            sub_months=payload.sub_months,
            sub_spend_earn=payload.sub_spend_earn,
            annual_bonus=payload.annual_bonus,
            annual_bonus_percent=payload.annual_bonus_percent,
            annual_bonus_first_year_only=payload.annual_bonus_first_year_only,
            transfer_enabler=payload.transfer_enabler,
            secondary_currency_id=payload.secondary_currency_id,
            secondary_currency_rate=payload.secondary_currency_rate,
            secondary_currency_cap_rate=payload.secondary_currency_cap_rate,
            accelerator_cost=payload.accelerator_cost,
            accelerator_spend_limit=payload.accelerator_spend_limit,
            accelerator_bonus_multiplier=payload.accelerator_bonus_multiplier,
            accelerator_max_activations=payload.accelerator_max_activations,
            housing_tiered_enabled=payload.housing_tiered_enabled,
            housing_fee_waived=getattr(payload, "housing_fee_waived", False),
            takeoff15_enabled=getattr(payload, "takeoff15_enabled", False),
            sub_recurrence_months=payload.sub_recurrence_months,
            sub_family=payload.sub_family,
        )
        self.db.add(card)
        return card

    async def delete_card_if_unused(self, card: Card) -> None:
        """Delete a card after ensuring it isn't referenced by any
        CardInstance (owned or scenario-scoped). PC chains link
        ``pc_from_instance_id`` (instance-to-instance), so the library
        ``card_id`` only appears via the instance's ``card_id`` column.
        Returns a clean 409 if the card is still in use.
        """
        used = await self.db.execute(
            select(CardInstance.id).where(CardInstance.card_id == card.id)
        )
        if used.scalars().first() is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Cannot delete card — it is held by one or more card "
                    "instances (owned or scenario-scoped). Remove all "
                    "references first."
                ),
            )
        await self.delete(card)

    async def add_multiplier(
        self,
        *,
        card_id: int,
        category_id: int,
        multiplier: float,
        is_portal: bool,
        is_additive: bool,
        cap_per_billing_cycle: float | None,
        cap_period_months: int | None,
        multiplier_group_id: int | None,
    ) -> CardCategoryMultiplier:
        existing = await self.db.execute(
            select(CardCategoryMultiplier).where(
                CardCategoryMultiplier.card_id == card_id,
                CardCategoryMultiplier.category_id == category_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail="Multiplier for this card/category already exists",
            )
        if multiplier_group_id is not None:
            grp = await self.db.execute(
                select(CardMultiplierGroup).where(
                    CardMultiplierGroup.id == multiplier_group_id,
                    CardMultiplierGroup.card_id == card_id,
                )
            )
            if not grp.scalar_one_or_none():
                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"MultiplierGroup id={multiplier_group_id} "
                        f"not found for card {card_id}"
                    ),
                )
        mult = CardCategoryMultiplier(
            card_id=card_id,
            category_id=category_id,
            multiplier=multiplier,
            is_portal=is_portal,
            is_additive=is_additive,
            cap_per_billing_cycle=cap_per_billing_cycle,
            cap_period_months=cap_period_months,
            multiplier_group_id=multiplier_group_id,
        )
        self.db.add(mult)
        return mult

    async def delete_multiplier(self, card_id: int, category_id: int) -> None:
        result = await self.db.execute(
            select(CardCategoryMultiplier).where(
                CardCategoryMultiplier.card_id == card_id,
                CardCategoryMultiplier.category_id == category_id,
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(
                status_code=404,
                detail="Multiplier not found for this card/category",
            )
        await self.delete(row)

    async def list_rotating_history(self, card_id: int) -> list[RotatingCategory]:
        """List a card's rotating category history (spend_category eager-loaded)."""
        result = await self.db.execute(
            select(RotatingCategory)
            .options(selectinload(RotatingCategory.spend_category))
            .where(RotatingCategory.card_id == card_id)
            .order_by(RotatingCategory.year.desc(), RotatingCategory.quarter.desc())
        )
        return list(result.scalars().all())

    async def add_rotating_history(
        self,
        *,
        card_id: int,
        year: int,
        quarter: int,
        spend_category_id: int,
    ) -> RotatingCategory:
        """Insert a rotating-history row with a conflict check."""
        existing = await self.db.execute(
            select(RotatingCategory).where(
                RotatingCategory.card_id == card_id,
                RotatingCategory.year == year,
                RotatingCategory.quarter == quarter,
                RotatingCategory.spend_category_id == spend_category_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Rotating history already exists for card {card_id} "
                    f"{year}Q{quarter} cat={spend_category_id}"
                ),
            )
        row = RotatingCategory(
            card_id=card_id,
            year=year,
            quarter=quarter,
            spend_category_id=spend_category_id,
        )
        self.db.add(row)
        return row

    async def get_rotating_history_row(
        self, card_id: int, history_id: int
    ) -> RotatingCategory:
        """Fetch a specific rotating-history row or 404."""
        result = await self.db.execute(
            select(RotatingCategory).where(
                RotatingCategory.id == history_id,
                RotatingCategory.card_id == card_id,
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"Rotating history id={history_id} not found for card {card_id}",
            )
        return row

    async def get_rotating_history_row_with_category(
        self, row_id: int
    ) -> RotatingCategory:
        """Fetch a rotating-history row with spend_category eager-loaded."""
        result = await self.db.execute(
            select(RotatingCategory)
            .options(selectinload(RotatingCategory.spend_category))
            .where(RotatingCategory.id == row_id)
        )
        return result.scalar_one()

    # ------------------------------------------------------------------
    # CardMultiplierGroup operations
    # ------------------------------------------------------------------

    @staticmethod
    def _multiplier_group_load_opts():
        return [
            selectinload(CardMultiplierGroup.categories).selectinload(
                CardCategoryMultiplier.spend_category
            ),
            selectinload(CardMultiplierGroup.card)
            .selectinload(Card.rotating_categories)
            .selectinload(RotatingCategory.spend_category),
        ]

    async def list_multiplier_groups(
        self, card_id: int
    ) -> list[CardMultiplierGroup]:
        result = await self.db.execute(
            select(CardMultiplierGroup)
            .options(*self._multiplier_group_load_opts())
            .where(CardMultiplierGroup.card_id == card_id)
        )
        return list(result.scalars().all())

    async def get_multiplier_group_or_404(
        self, card_id: int, group_id: int
    ) -> CardMultiplierGroup:
        result = await self.db.execute(
            select(CardMultiplierGroup).where(
                CardMultiplierGroup.id == group_id,
                CardMultiplierGroup.card_id == card_id,
            )
        )
        grp = result.scalar_one_or_none()
        if not grp:
            raise HTTPException(
                status_code=404,
                detail=f"MultiplierGroup id={group_id} not found for card {card_id}",
            )
        return grp

    async def load_multiplier_group_full(self, group_id: int) -> CardMultiplierGroup:
        result = await self.db.execute(
            select(CardMultiplierGroup)
            .options(*self._multiplier_group_load_opts())
            .where(CardMultiplierGroup.id == group_id)
        )
        return result.scalar_one()

    async def _assert_category_multiplier_free(
        self,
        *,
        card_id: int,
        category_id: int,
        exclude_group_id: int | None = None,
    ) -> None:
        stmt = select(CardCategoryMultiplier).where(
            CardCategoryMultiplier.card_id == card_id,
            CardCategoryMultiplier.category_id == category_id,
        )
        if exclude_group_id is not None:
            stmt = stmt.where(
                CardCategoryMultiplier.multiplier_group_id != exclude_group_id
            )
        existing = await self.db.execute(stmt)
        if existing.scalar_one_or_none():
            where = (
                f"already exists outside group {exclude_group_id}"
                if exclude_group_id is not None
                else "already exists"
            )
            raise HTTPException(
                status_code=409,
                detail=f"Multiplier for card {card_id} / category {category_id} {where}",
            )

    async def create_multiplier_group(
        self, *, card_id: int, payload
    ) -> CardMultiplierGroup:
        grp = CardMultiplierGroup(
            card_id=card_id,
            multiplier=payload.multiplier,
            cap_per_billing_cycle=payload.cap_per_billing_cycle,
            cap_period_months=payload.cap_period_months,
            top_n_categories=payload.top_n_categories,
            is_rotating=payload.is_rotating,
            is_additive=payload.is_additive,
        )
        self.db.add(grp)
        await self.db.flush()

        for cat_id in payload.category_ids:
            await self._assert_category_multiplier_free(
                card_id=card_id, category_id=cat_id
            )
            self.db.add(
                CardCategoryMultiplier(
                    card_id=card_id,
                    category_id=cat_id,
                    multiplier=payload.multiplier,
                    multiplier_group_id=grp.id,
                )
            )
        return grp

    async def update_multiplier_group(
        self,
        *,
        grp: CardMultiplierGroup,
        card_id: int,
        payload,
    ) -> CardMultiplierGroup:
        if payload.multiplier is not None:
            grp.multiplier = payload.multiplier
        if payload.cap_per_billing_cycle is not None:
            grp.cap_per_billing_cycle = payload.cap_per_billing_cycle
        if payload.cap_period_months is not None:
            grp.cap_period_months = payload.cap_period_months
        if payload.top_n_categories is not None:
            grp.top_n_categories = payload.top_n_categories
        if payload.is_rotating is not None:
            grp.is_rotating = payload.is_rotating
        if payload.is_additive is not None:
            grp.is_additive = payload.is_additive

        if payload.category_ids is not None:
            existing = await self.db.execute(
                select(CardCategoryMultiplier).where(
                    CardCategoryMultiplier.multiplier_group_id == grp.id
                )
            )
            for row in existing.scalars().all():
                await self.db.delete(row)

            mult = (
                payload.multiplier
                if payload.multiplier is not None
                else grp.multiplier
            )
            for cat_id in payload.category_ids:
                await self._assert_category_multiplier_free(
                    card_id=card_id,
                    category_id=cat_id,
                    exclude_group_id=grp.id,
                )
                self.db.add(
                    CardCategoryMultiplier(
                        card_id=card_id,
                        category_id=cat_id,
                        multiplier=mult,
                        multiplier_group_id=grp.id,
                    )
                )
        elif payload.multiplier is not None:
            existing = await self.db.execute(
                select(CardCategoryMultiplier).where(
                    CardCategoryMultiplier.multiplier_group_id == grp.id
                )
            )
            for row in existing.scalars().all():
                row.multiplier = payload.multiplier

        return grp

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
