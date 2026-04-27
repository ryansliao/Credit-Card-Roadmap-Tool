"""CardInstance data access service.

Manages owned card instances (scenario_id IS NULL) and future card
instances (scenario_id set). Owned-card CRUD is driven from
Profile/WalletTab; future-card CRUD from the Roadmap Tool.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models import (
    Card,
    CardCredit,
    CardInstance,
    Credit,
    ScenarioCardCredit,
    WalletCardCredit,
)
from ..schemas import (
    FutureCardCreate,
    OwnedCardCreate,
)
from .base import BaseService


class CardInstanceService(BaseService[CardInstance]):
    """CRUD on CardInstance rows + product-change chain marking."""

    model = CardInstance

    @staticmethod
    def instance_load_opts():
        """Eager-load the relationships ``card_instance_read`` reads.

        ``card.issuer`` and ``card.network_tier`` are required by the read
        builder; without them the access fires a sync lazy-load that fails
        with ``MissingGreenlet`` once the request handler returns. The
        builder also walks the credit chain — for owned cards it merges
        library credits (via ``card.card_credit_links → Credit →
        credit_currency``) with wallet overrides (via
        ``wallet_credit_overrides → library_credit → credit_currency``);
        for scenario-scoped instances it walks
        ``credit_overrides_rows → library_credit → credit_currency``.
        """
        card_chain = selectinload(CardInstance.card)
        library_credit_chain = card_chain.selectinload(
            Card.card_credit_links
        ).selectinload(CardCredit.credit)
        wallet_credit_chain = selectinload(
            CardInstance.wallet_credit_overrides
        ).selectinload(WalletCardCredit.library_credit)
        credit_chain = selectinload(
            CardInstance.credit_overrides_rows
        ).selectinload(ScenarioCardCredit.library_credit)
        return [
            card_chain,
            card_chain.selectinload(Card.issuer),
            card_chain.selectinload(Card.network_tier),
            library_credit_chain,
            library_credit_chain.selectinload(Credit.credit_currency),
            wallet_credit_chain,
            wallet_credit_chain.selectinload(Credit.credit_currency),
            credit_chain,
            credit_chain.selectinload(Credit.credit_currency),
        ]

    async def list_owned(self, wallet_id: int) -> list[CardInstance]:
        """List the user's owned cards (scenario_id IS NULL)."""
        result = await self.db.execute(
            select(CardInstance)
            .options(*self.instance_load_opts())
            .where(
                CardInstance.wallet_id == wallet_id,
                CardInstance.scenario_id.is_(None),
            )
            .order_by(CardInstance.id)
        )
        return list(result.scalars().all())

    async def list_for_scenario(
        self, wallet_id: int, scenario_id: int
    ) -> list[CardInstance]:
        """List both owned (wallet) and future (this scenario) cards."""
        result = await self.db.execute(
            select(CardInstance)
            .options(*self.instance_load_opts())
            .where(
                CardInstance.wallet_id == wallet_id,
                (
                    (CardInstance.scenario_id.is_(None))
                    | (CardInstance.scenario_id == scenario_id)
                ),
            )
            .order_by(CardInstance.id)
        )
        return list(result.scalars().all())

    async def list_future(self, scenario_id: int) -> list[CardInstance]:
        """List future cards specific to the scenario."""
        result = await self.db.execute(
            select(CardInstance)
            .options(*self.instance_load_opts())
            .where(CardInstance.scenario_id == scenario_id)
            .order_by(CardInstance.id)
        )
        return list(result.scalars().all())

    async def get_with_card(self, instance_id: int) -> CardInstance:
        """Fetch a single instance with its library Card eager-loaded."""
        result = await self.db.execute(
            select(CardInstance)
            .options(*self.instance_load_opts())
            .where(CardInstance.id == instance_id)
        )
        inst = result.scalar_one_or_none()
        if not inst:
            raise HTTPException(
                status_code=404, detail=f"Card instance {instance_id} not found"
            )
        return inst

    async def get_card_or_404(self, card_id: int) -> Card:
        """Validate a library card_id exists."""
        result = await self.db.execute(
            select(Card)
            .where(Card.id == card_id)
            .options(selectinload(Card.issuer), selectinload(Card.network_tier))
        )
        card = result.scalar_one_or_none()
        if not card:
            raise HTTPException(
                status_code=404, detail=f"Card {card_id} not found"
            )
        return card

    async def create_owned(
        self, wallet_id: int, payload: OwnedCardCreate
    ) -> CardInstance:
        """Add an owned card to the user's wallet. Carries the same SUB /
        bonus / fee override fields as a future card plus optional
        ``credit_overrides`` — wallet-level credit valuations persisted as
        ``WalletCardCredit`` rows. Owned cards have no scenario context, so
        no per-scenario credit / priority / multiplier overrides apply
        here."""
        await self.get_card_or_404(payload.card_id)

        if payload.opening_date > date.today():
            raise HTTPException(
                status_code=422,
                detail="Owned cards must have an opening_date on or before today",
            )

        instance = CardInstance(
            wallet_id=wallet_id,
            scenario_id=None,
            card_id=payload.card_id,
            opening_date=payload.opening_date,
            product_change_date=payload.product_change_date,
            closed_date=payload.closed_date,
            sub_points=payload.sub_points,
            sub_min_spend=payload.sub_min_spend,
            sub_months=payload.sub_months,
            sub_spend_earn=payload.sub_spend_earn,
            years_counted=payload.years_counted,
            annual_bonus=payload.annual_bonus,
            annual_bonus_percent=payload.annual_bonus_percent,
            annual_bonus_first_year_only=payload.annual_bonus_first_year_only,
            annual_fee=payload.annual_fee,
            first_year_fee=payload.first_year_fee,
            secondary_currency_rate=payload.secondary_currency_rate,
            sub_earned_date=payload.sub_earned_date,
            panel="in_wallet",
            is_enabled=True,
        )
        self.db.add(instance)
        await self.db.flush()
        if payload.credit_overrides:
            await self._set_wallet_credit_overrides(
                instance.id,
                [(o.library_credit_id, o.value) for o in payload.credit_overrides],
            )
        return instance

    async def create_future(
        self,
        wallet_id: int,
        scenario_id: int,
        payload: FutureCardCreate,
    ) -> CardInstance:
        """Add a future card to a scenario. May carry every override field
        plus a pc_from_instance_id link."""
        await self.get_card_or_404(payload.card_id)

        # Validate pc_from_instance_id (if set) belongs to the same wallet
        # and is either owned or in the same scenario.
        if payload.pc_from_instance_id is not None:
            src = await self.get_with_card(payload.pc_from_instance_id)
            if src.wallet_id != wallet_id:
                raise HTTPException(
                    status_code=400,
                    detail="pc_from_instance_id belongs to a different wallet",
                )
            if (
                src.scenario_id is not None
                and src.scenario_id != scenario_id
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "pc_from_instance_id is scoped to a different scenario"
                    ),
                )

        instance = CardInstance(
            wallet_id=wallet_id,
            scenario_id=scenario_id,
            card_id=payload.card_id,
            opening_date=payload.opening_date,
            product_change_date=payload.product_change_date,
            closed_date=payload.closed_date,
            sub_points=payload.sub_points,
            sub_min_spend=payload.sub_min_spend,
            sub_months=payload.sub_months,
            sub_spend_earn=payload.sub_spend_earn,
            years_counted=payload.years_counted,
            annual_bonus=payload.annual_bonus,
            annual_bonus_percent=payload.annual_bonus_percent,
            annual_bonus_first_year_only=payload.annual_bonus_first_year_only,
            annual_fee=payload.annual_fee,
            first_year_fee=payload.first_year_fee,
            secondary_currency_rate=payload.secondary_currency_rate,
            sub_earned_date=payload.sub_earned_date,
            pc_from_instance_id=payload.pc_from_instance_id,
            panel=payload.panel,
            is_enabled=payload.is_enabled,
        )
        self.db.add(instance)
        await self.db.flush()
        return instance

    async def update(self, instance: CardInstance, **updates) -> CardInstance:
        """Partial update. Callers pass `payload.model_dump(exclude_unset=True)`
        so the dict only contains fields the client explicitly set; None is
        meaningful here ("clear back to inherit / null"), e.g. flipping a
        card's status from Closed → Active sends ``closed_date=None``.

        ``credit_overrides`` is handled separately: when present (even if
        empty list), it replaces the instance's WalletCardCredit set. When
        absent (key not in updates), wallet credit overrides are left
        unchanged.
        """
        credit_overrides = updates.pop("credit_overrides", None)
        for field, value in updates.items():
            setattr(instance, field, value)
        if credit_overrides is not None:
            pairs = [
                (
                    o["library_credit_id"] if isinstance(o, dict) else o.library_credit_id,
                    o["value"] if isinstance(o, dict) else o.value,
                )
                for o in credit_overrides
            ]
            await self._set_wallet_credit_overrides(instance.id, pairs)
        return instance

    async def _set_wallet_credit_overrides(
        self,
        instance_id: int,
        overrides: list[tuple[int, float]],
    ) -> None:
        """Replace the WalletCardCredit set for ``instance_id`` with the
        provided (library_credit_id, value) pairs. Validates each library
        credit exists; deletes any existing rows not in the new set.
        """
        # Delete existing rows for this instance
        existing = await self.db.execute(
            select(WalletCardCredit).where(
                WalletCardCredit.card_instance_id == instance_id
            )
        )
        for row in existing.scalars().all():
            await self.db.delete(row)
        await self.db.flush()
        if not overrides:
            return
        lib_ids = {cid for cid, _ in overrides}
        lib_rows = await self.db.execute(
            select(Credit).where(Credit.id.in_(lib_ids))
        )
        valid_ids = {row.id for row in lib_rows.scalars()}
        for cid, val in overrides:
            if cid not in valid_ids:
                raise HTTPException(
                    status_code=404,
                    detail=f"Credit id={cid} not found in library",
                )
            self.db.add(
                WalletCardCredit(
                    card_instance_id=instance_id,
                    library_credit_id=cid,
                    value=val,
                )
            )
        await self.db.flush()

    async def delete_owned(self, instance: CardInstance) -> None:
        """Delete an owned CardInstance from Profile/WalletTab."""
        if instance.scenario_id is not None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Cannot delete a scenario-scoped instance via the owned-card "
                    "endpoint; use DELETE /scenarios/{sid}/future-cards/{id}"
                ),
            )
        await self.db.delete(instance)
        await self.db.flush()

    async def delete_future(self, instance: CardInstance) -> None:
        """Delete a future CardInstance from the Roadmap Tool."""
        if instance.scenario_id is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Cannot delete an owned instance via the future-card "
                    "endpoint; use Profile/WalletTab"
                ),
            )
        await self.db.delete(instance)
        await self.db.flush()

    async def add_credits_for_instance(
        self,
        scenario_id: int,
        instance_id: int,
        credits: list[tuple[int, float]],
    ) -> None:
        """Bulk-add ScenarioCardCredit rows for a future card created with
        initial credit overrides. Each tuple is (library_credit_id, value).
        Validates each library credit exists.
        """
        if not credits:
            return
        lib_ids = {cid for cid, _ in credits}
        lib_rows = await self.db.execute(
            select(Credit).where(Credit.id.in_(lib_ids))
        )
        valid_ids = {row.id for row in lib_rows.scalars()}
        for cid, val in credits:
            if cid not in valid_ids:
                raise HTTPException(
                    status_code=404,
                    detail=f"Credit id={cid} not found in library",
                )
            self.db.add(
                ScenarioCardCredit(
                    scenario_id=scenario_id,
                    card_instance_id=instance_id,
                    library_credit_id=cid,
                    value=val,
                )
            )


def get_card_instance_service(
    db: AsyncSession = Depends(get_db),
) -> CardInstanceService:
    """FastAPI dependency for CardInstanceService."""
    return CardInstanceService(db)
