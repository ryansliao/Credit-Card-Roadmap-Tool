"""Per-scenario, per-card-instance override services.

Covers the four card-instance-keyed override tables:
  - ScenarioCardMultiplier   (per-category multiplier override)
  - ScenarioCardCredit       (per-credit valuation override)
  - ScenarioCardCategoryPriority (manual category pin)
  - ScenarioCardGroupSelection (manual top-N picks for a multiplier group)
"""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models import (
    CardInstance,
    Credit,
    ScenarioCardCategoryPriority,
    ScenarioCardCredit,
    ScenarioCardGroupSelection,
    ScenarioCardMultiplier,
    SpendCategory,
)
from .base import BaseService


def _validate_target_instance(
    instance: CardInstance, scenario_id: int
) -> None:
    """Enforce: an override row may target an OWNED instance (scenario_id
    IS NULL) OR a future instance from the same scenario."""
    if instance.scenario_id is not None and instance.scenario_id != scenario_id:
        raise HTTPException(
            status_code=409,
            detail=(
                "Card instance is scoped to a different scenario; cannot "
                "override from this scenario"
            ),
        )


class ScenarioCardMultiplierService(BaseService[ScenarioCardMultiplier]):
    """Per-scenario multiplier overrides keyed by card_instance + category."""

    model = ScenarioCardMultiplier

    async def list_for_scenario(
        self, scenario_id: int
    ) -> list[ScenarioCardMultiplier]:
        result = await self.db.execute(
            select(ScenarioCardMultiplier)
            .options(selectinload(ScenarioCardMultiplier.spend_category))
            .where(ScenarioCardMultiplier.scenario_id == scenario_id)
        )
        return list(result.scalars().all())

    async def get(
        self, scenario_id: int, card_instance_id: int, category_id: int
    ) -> Optional[ScenarioCardMultiplier]:
        result = await self.db.execute(
            select(ScenarioCardMultiplier).where(
                ScenarioCardMultiplier.scenario_id == scenario_id,
                ScenarioCardMultiplier.card_instance_id == card_instance_id,
                ScenarioCardMultiplier.category_id == category_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        scenario_id: int,
        card_instance: CardInstance,
        category_id: int,
        multiplier: float,
    ) -> ScenarioCardMultiplier:
        _validate_target_instance(card_instance, scenario_id)
        row = await self.get(scenario_id, card_instance.id, category_id)
        if row is None:
            row = ScenarioCardMultiplier(
                scenario_id=scenario_id,
                card_instance_id=card_instance.id,
                category_id=category_id,
                multiplier=multiplier,
            )
            self.db.add(row)
        else:
            row.multiplier = multiplier
        await self.db.flush()
        return row

    async def delete(
        self, scenario_id: int, card_instance_id: int, category_id: int
    ) -> None:
        row = await self.get(scenario_id, card_instance_id, category_id)
        if row is None:
            raise HTTPException(status_code=404, detail="No multiplier override")
        await self.db.delete(row)


class ScenarioCardCreditService(BaseService[ScenarioCardCredit]):
    """Per-scenario, per-instance credit valuation overrides."""

    model = ScenarioCardCredit

    async def list_for_instance(
        self, scenario_id: int, card_instance_id: int
    ) -> list[ScenarioCardCredit]:
        result = await self.db.execute(
            select(ScenarioCardCredit)
            .options(selectinload(ScenarioCardCredit.library_credit))
            .where(
                ScenarioCardCredit.scenario_id == scenario_id,
                ScenarioCardCredit.card_instance_id == card_instance_id,
            )
            .order_by(ScenarioCardCredit.library_credit_id)
        )
        return list(result.scalars().all())

    async def list_for_scenario(
        self, scenario_id: int
    ) -> list[ScenarioCardCredit]:
        result = await self.db.execute(
            select(ScenarioCardCredit)
            .options(selectinload(ScenarioCardCredit.library_credit))
            .where(ScenarioCardCredit.scenario_id == scenario_id)
        )
        return list(result.scalars().all())

    async def get(
        self,
        scenario_id: int,
        card_instance_id: int,
        library_credit_id: int,
    ) -> Optional[ScenarioCardCredit]:
        result = await self.db.execute(
            select(ScenarioCardCredit).where(
                ScenarioCardCredit.scenario_id == scenario_id,
                ScenarioCardCredit.card_instance_id == card_instance_id,
                ScenarioCardCredit.library_credit_id == library_credit_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_library_credit_or_404(self, credit_id: int) -> Credit:
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

    async def upsert(
        self,
        scenario_id: int,
        card_instance: CardInstance,
        library_credit_id: int,
        value: float,
    ) -> ScenarioCardCredit:
        _validate_target_instance(card_instance, scenario_id)
        await self.get_library_credit_or_404(library_credit_id)

        row = await self.get(scenario_id, card_instance.id, library_credit_id)
        if row is None:
            row = ScenarioCardCredit(
                scenario_id=scenario_id,
                card_instance_id=card_instance.id,
                library_credit_id=library_credit_id,
                value=value,
            )
            self.db.add(row)
        else:
            row.value = value
        await self.db.flush()
        return row

    async def get_with_library(
        self, credit_id: int
    ) -> Optional[ScenarioCardCredit]:
        result = await self.db.execute(
            select(ScenarioCardCredit)
            .options(selectinload(ScenarioCardCredit.library_credit))
            .where(ScenarioCardCredit.id == credit_id)
        )
        return result.scalar_one_or_none()

    async def delete(
        self,
        scenario_id: int,
        card_instance_id: int,
        library_credit_id: int,
    ) -> None:
        row = await self.get(scenario_id, card_instance_id, library_credit_id)
        if row is None:
            raise HTTPException(status_code=404, detail="No credit override")
        await self.db.delete(row)


class ScenarioCategoryPriorityService(BaseService[ScenarioCardCategoryPriority]):
    """Per-scenario manual category pins.

    The unique (scenario_id, spend_category_id) constraint guarantees at
    most one card per category per scenario.
    """

    model = ScenarioCardCategoryPriority

    async def list_for_scenario(
        self, scenario_id: int
    ) -> list[ScenarioCardCategoryPriority]:
        result = await self.db.execute(
            select(ScenarioCardCategoryPriority)
            .options(selectinload(ScenarioCardCategoryPriority.spend_category))
            .where(ScenarioCardCategoryPriority.scenario_id == scenario_id)
        )
        return list(result.scalars().all())

    async def list_for_instance(
        self, scenario_id: int, card_instance_id: int
    ) -> list[ScenarioCardCategoryPriority]:
        result = await self.db.execute(
            select(ScenarioCardCategoryPriority)
            .options(selectinload(ScenarioCardCategoryPriority.spend_category))
            .where(
                ScenarioCardCategoryPriority.scenario_id == scenario_id,
                ScenarioCardCategoryPriority.card_instance_id == card_instance_id,
            )
        )
        return list(result.scalars().all())

    async def set_for_instance(
        self,
        scenario_id: int,
        card_instance: CardInstance,
        spend_category_ids: list[int],
    ) -> list[ScenarioCardCategoryPriority]:
        """Replace the priority set for a card instance. Empty list clears
        all pins for the card. Raises 409 on conflict — another card in
        the same scenario already pins one of these categories."""
        _validate_target_instance(card_instance, scenario_id)

        # Validate categories exist
        if spend_category_ids:
            existing = await self.db.execute(
                select(SpendCategory.id).where(
                    SpendCategory.id.in_(spend_category_ids)
                )
            )
            valid_ids = {row[0] for row in existing.all()}
            for sc_id in spend_category_ids:
                if sc_id not in valid_ids:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Spend category {sc_id} not found",
                    )

        # Check for cross-card conflicts in the same scenario
        if spend_category_ids:
            conflicts = await self.db.execute(
                select(ScenarioCardCategoryPriority).where(
                    ScenarioCardCategoryPriority.scenario_id == scenario_id,
                    ScenarioCardCategoryPriority.spend_category_id.in_(
                        spend_category_ids
                    ),
                    ScenarioCardCategoryPriority.card_instance_id != card_instance.id,
                )
            )
            conflict_rows = list(conflicts.scalars().all())
            if conflict_rows:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Some categories are already pinned to another card "
                        "in this scenario"
                    ),
                )

        # Delete the card's existing pins, then create the new set
        existing_for_card = await self.db.execute(
            select(ScenarioCardCategoryPriority).where(
                ScenarioCardCategoryPriority.scenario_id == scenario_id,
                ScenarioCardCategoryPriority.card_instance_id == card_instance.id,
            )
        )
        for row in existing_for_card.scalars().all():
            await self.db.delete(row)
        await self.db.flush()

        for sc_id in spend_category_ids:
            self.db.add(
                ScenarioCardCategoryPriority(
                    scenario_id=scenario_id,
                    card_instance_id=card_instance.id,
                    spend_category_id=sc_id,
                )
            )
        await self.db.flush()
        return await self.list_for_instance(scenario_id, card_instance.id)


class ScenarioCardGroupSelectionService(BaseService[ScenarioCardGroupSelection]):
    """Per-scenario manual top-N picks for a CardMultiplierGroup."""

    model = ScenarioCardGroupSelection

    async def list_for_scenario(
        self, scenario_id: int
    ) -> list[ScenarioCardGroupSelection]:
        result = await self.db.execute(
            select(ScenarioCardGroupSelection)
            .options(selectinload(ScenarioCardGroupSelection.spend_category))
            .where(ScenarioCardGroupSelection.scenario_id == scenario_id)
        )
        return list(result.scalars().all())

    async def list_for_instance(
        self, scenario_id: int, card_instance_id: int
    ) -> list[ScenarioCardGroupSelection]:
        result = await self.db.execute(
            select(ScenarioCardGroupSelection)
            .options(selectinload(ScenarioCardGroupSelection.spend_category))
            .where(
                ScenarioCardGroupSelection.scenario_id == scenario_id,
                ScenarioCardGroupSelection.card_instance_id == card_instance_id,
            )
        )
        return list(result.scalars().all())

    async def set_for_group(
        self,
        scenario_id: int,
        card_instance: CardInstance,
        multiplier_group_id: int,
        spend_category_ids: list[int],
    ) -> list[ScenarioCardGroupSelection]:
        """Replace the picks for one (instance, multiplier_group) pair."""
        _validate_target_instance(card_instance, scenario_id)

        # Delete existing picks for this group on this instance
        existing = await self.db.execute(
            select(ScenarioCardGroupSelection).where(
                ScenarioCardGroupSelection.scenario_id == scenario_id,
                ScenarioCardGroupSelection.card_instance_id == card_instance.id,
                ScenarioCardGroupSelection.multiplier_group_id == multiplier_group_id,
            )
        )
        for row in existing.scalars().all():
            await self.db.delete(row)
        await self.db.flush()

        new_rows: list[ScenarioCardGroupSelection] = []
        for sc_id in spend_category_ids:
            row = ScenarioCardGroupSelection(
                scenario_id=scenario_id,
                card_instance_id=card_instance.id,
                multiplier_group_id=multiplier_group_id,
                spend_category_id=sc_id,
            )
            self.db.add(row)
            new_rows.append(row)
        await self.db.flush()
        return new_rows


def get_scenario_card_multiplier_service(
    db: AsyncSession = Depends(get_db),
) -> ScenarioCardMultiplierService:
    return ScenarioCardMultiplierService(db)


def get_scenario_card_credit_service(
    db: AsyncSession = Depends(get_db),
) -> ScenarioCardCreditService:
    return ScenarioCardCreditService(db)


def get_scenario_category_priority_service(
    db: AsyncSession = Depends(get_db),
) -> ScenarioCategoryPriorityService:
    return ScenarioCategoryPriorityService(db)


def get_scenario_card_group_selection_service(
    db: AsyncSession = Depends(get_db),
) -> ScenarioCardGroupSelectionService:
    return ScenarioCardGroupSelectionService(db)
