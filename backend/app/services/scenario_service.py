"""Scenario data access service.

Handles Scenario CRUD, default-scenario invariants, and the deep-copy
clone path used when a user duplicates a scenario.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models import (
    CardInstance,
    Scenario,
    ScenarioCardCategoryPriority,
    ScenarioCardCredit,
    ScenarioCardGroupSelection,
    ScenarioCardMultiplier,
    ScenarioCardOverlay,
    ScenarioCurrencyBalance,
    ScenarioCurrencyCpp,
    ScenarioPortalShare,
    User,
    Wallet,
)
from .base import BaseService


class ScenarioService(BaseService[Scenario]):
    """Service for Scenario CRUD + clone + default-scenario invariants."""

    model = Scenario

    @staticmethod
    def scenario_load_opts():
        """Eager-load options for a scenario (lightweight — just direct
        children that downstream callers nearly always need).
        """
        return [
            selectinload(Scenario.card_instances).selectinload(CardInstance.card),
            selectinload(Scenario.overlays),
        ]

    async def get_user_scenario(self, scenario_id: int, user: User) -> Scenario:
        """Load a scenario and verify the parent wallet belongs to the user.

        Raises HTTPException 404 if not found, 403 if owned by another user.
        """
        result = await self.db.execute(
            select(Scenario)
            .options(selectinload(Scenario.wallet))
            .where(Scenario.id == scenario_id)
        )
        scenario = result.scalar_one_or_none()
        if not scenario:
            raise HTTPException(
                status_code=404, detail=f"Scenario {scenario_id} not found"
            )
        if scenario.wallet.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not your scenario")
        return scenario

    async def list_for_wallet(self, wallet_id: int) -> list[Scenario]:
        """List all scenarios for a wallet, ordered by default first then id."""
        result = await self.db.execute(
            select(Scenario)
            .where(Scenario.wallet_id == wallet_id)
            .order_by(Scenario.is_default.desc(), Scenario.id)
        )
        return list(result.scalars().all())

    async def get_default_for_wallet(self, wallet_id: int) -> Optional[Scenario]:
        """Get the wallet's default scenario, if any."""
        result = await self.db.execute(
            select(Scenario)
            .where(Scenario.wallet_id == wallet_id, Scenario.is_default == True)  # noqa: E712
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_default(self, wallet_id: int) -> Scenario:
        """Create a wallet's first scenario, marked default. Used when a
        wallet is auto-created on first GET /wallet."""
        scenario = Scenario(
            wallet_id=wallet_id,
            name="Default",
            description=None,
            is_default=True,
        )
        self.db.add(scenario)
        await self.db.flush()
        return scenario

    async def create(
        self,
        wallet_id: int,
        name: str,
        description: Optional[str] = None,
        copy_from_scenario_id: Optional[int] = None,
    ) -> Scenario:
        """Create a new (non-default) scenario under the wallet.

        If ``copy_from_scenario_id`` is provided, deep-copies calc config,
        future card instances, overlays, and per-scenario override tables
        from the source.
        """
        source: Optional[Scenario] = None
        if copy_from_scenario_id is not None:
            source = await self.get_by_id(copy_from_scenario_id)
            if not source:
                raise HTTPException(
                    status_code=404,
                    detail=f"Source scenario {copy_from_scenario_id} not found",
                )
            if source.wallet_id != wallet_id:
                raise HTTPException(
                    status_code=400,
                    detail="Source scenario belongs to a different wallet",
                )

        scenario = Scenario(
            wallet_id=wallet_id,
            name=name,
            description=description,
            is_default=False,
            start_date=source.start_date if source else None,
            end_date=source.end_date if source else None,
            duration_years=source.duration_years if source else 2,
            duration_months=source.duration_months if source else 0,
            window_mode=source.window_mode if source else "duration",
            include_subs=source.include_subs if source else True,
        )
        self.db.add(scenario)
        await self.db.flush()

        if source is not None:
            await self._clone_scenario_contents(source.id, scenario.id, wallet_id)

        return scenario

    async def _clone_scenario_contents(
        self, source_id: int, target_id: int, wallet_id: int
    ) -> None:
        """Copy future card instances, overlays, and override tables from
        ``source_id`` into ``target_id``. Owned card instances (scenario_id
        IS NULL) are NOT copied — they belong to the wallet, not a scenario.
        """
        # Future card instances (scenario-scoped). Translate to a fresh
        # instance row per future card; preserve a mapping so overlays /
        # overrides that reference the source's instances can be retargeted.
        src_instances = await self.db.execute(
            select(CardInstance).where(CardInstance.scenario_id == source_id)
        )
        old_to_new_instance: dict[int, int] = {}
        for src in src_instances.scalars().all():
            new_inst = CardInstance(
                wallet_id=wallet_id,
                scenario_id=target_id,
                card_id=src.card_id,
                opening_date=src.opening_date,
                product_change_date=src.product_change_date,
                closed_date=src.closed_date,
                sub_earned_date=src.sub_earned_date,
                # pc_from_instance_id intentionally not copied — would
                # require a second pass and is rarely meaningful across a
                # scenario clone. Future cards in the new scenario start
                # without PC chain links.
                pc_from_instance_id=None,
                sub_points=src.sub_points,
                sub_min_spend=src.sub_min_spend,
                sub_months=src.sub_months,
                sub_spend_earn=src.sub_spend_earn,
                years_counted=src.years_counted,
                annual_bonus=src.annual_bonus,
                annual_bonus_percent=src.annual_bonus_percent,
                annual_bonus_first_year_only=src.annual_bonus_first_year_only,
                annual_fee=src.annual_fee,
                first_year_fee=src.first_year_fee,
                secondary_currency_rate=src.secondary_currency_rate,
                panel=src.panel,
                is_enabled=src.is_enabled,
            )
            self.db.add(new_inst)
            await self.db.flush()
            old_to_new_instance[src.id] = new_inst.id

        # Overlays — point to OWNED card instances which are wallet-scoped
        # and shared across scenarios; just clone the overlay row with the
        # new scenario_id and the unchanged card_instance_id.
        overlays = await self.db.execute(
            select(ScenarioCardOverlay).where(
                ScenarioCardOverlay.scenario_id == source_id
            )
        )
        for o in overlays.scalars().all():
            self.db.add(
                ScenarioCardOverlay(
                    scenario_id=target_id,
                    card_instance_id=o.card_instance_id,
                    closed_date=o.closed_date,
                    product_change_date=o.product_change_date,
                    sub_earned_date=o.sub_earned_date,
                    sub_points=o.sub_points,
                    sub_min_spend=o.sub_min_spend,
                    sub_months=o.sub_months,
                    sub_spend_earn=o.sub_spend_earn,
                    annual_bonus=o.annual_bonus,
                    annual_bonus_percent=o.annual_bonus_percent,
                    annual_bonus_first_year_only=o.annual_bonus_first_year_only,
                    annual_fee=o.annual_fee,
                    first_year_fee=o.first_year_fee,
                    secondary_currency_rate=o.secondary_currency_rate,
                    is_enabled=o.is_enabled,
                )
            )

        # Per-card override tables — translate card_instance_id when the
        # source pointed to a future-card instance from the source scenario;
        # otherwise keep as-is (owned-card targets are wallet-shared).
        def _retarget(old_id: int) -> int:
            return old_to_new_instance.get(old_id, old_id)

        mults = await self.db.execute(
            select(ScenarioCardMultiplier).where(
                ScenarioCardMultiplier.scenario_id == source_id
            )
        )
        for m in mults.scalars().all():
            self.db.add(
                ScenarioCardMultiplier(
                    scenario_id=target_id,
                    card_instance_id=_retarget(m.card_instance_id),
                    category_id=m.category_id,
                    multiplier=m.multiplier,
                )
            )

        credits = await self.db.execute(
            select(ScenarioCardCredit).where(
                ScenarioCardCredit.scenario_id == source_id
            )
        )
        for c in credits.scalars().all():
            self.db.add(
                ScenarioCardCredit(
                    scenario_id=target_id,
                    card_instance_id=_retarget(c.card_instance_id),
                    library_credit_id=c.library_credit_id,
                    value=c.value,
                )
            )

        prios = await self.db.execute(
            select(ScenarioCardCategoryPriority).where(
                ScenarioCardCategoryPriority.scenario_id == source_id
            )
        )
        for p in prios.scalars().all():
            self.db.add(
                ScenarioCardCategoryPriority(
                    scenario_id=target_id,
                    card_instance_id=_retarget(p.card_instance_id),
                    spend_category_id=p.spend_category_id,
                )
            )

        groups = await self.db.execute(
            select(ScenarioCardGroupSelection).where(
                ScenarioCardGroupSelection.scenario_id == source_id
            )
        )
        for g in groups.scalars().all():
            self.db.add(
                ScenarioCardGroupSelection(
                    scenario_id=target_id,
                    card_instance_id=_retarget(g.card_instance_id),
                    multiplier_group_id=g.multiplier_group_id,
                    spend_category_id=g.spend_category_id,
                )
            )

        cpps = await self.db.execute(
            select(ScenarioCurrencyCpp).where(
                ScenarioCurrencyCpp.scenario_id == source_id
            )
        )
        for cp in cpps.scalars().all():
            self.db.add(
                ScenarioCurrencyCpp(
                    scenario_id=target_id,
                    currency_id=cp.currency_id,
                    cents_per_point=cp.cents_per_point,
                )
            )

        bals = await self.db.execute(
            select(ScenarioCurrencyBalance).where(
                ScenarioCurrencyBalance.scenario_id == source_id
            )
        )
        for b in bals.scalars().all():
            self.db.add(
                ScenarioCurrencyBalance(
                    scenario_id=target_id,
                    currency_id=b.currency_id,
                    balance=b.balance,
                )
            )

        portals = await self.db.execute(
            select(ScenarioPortalShare).where(
                ScenarioPortalShare.scenario_id == source_id
            )
        )
        for ps in portals.scalars().all():
            self.db.add(
                ScenarioPortalShare(
                    scenario_id=target_id,
                    travel_portal_id=ps.travel_portal_id,
                    share=ps.share,
                )
            )

        await self.db.flush()

    async def update(self, scenario: Scenario, **updates) -> Scenario:
        """Update scenario fields. None values are skipped (partial PATCH)."""
        for field, value in updates.items():
            if value is not None:
                setattr(scenario, field, value)
        return scenario

    async def set_default(self, scenario: Scenario) -> Scenario:
        """Make ``scenario`` the wallet's default. Clears the flag on
        siblings first to satisfy the filtered unique index."""
        # Clear the flag on every other scenario in the wallet
        siblings = await self.db.execute(
            select(Scenario).where(
                Scenario.wallet_id == scenario.wallet_id,
                Scenario.id != scenario.id,
                Scenario.is_default == True,  # noqa: E712
            )
        )
        for s in siblings.scalars().all():
            s.is_default = False
        await self.db.flush()
        scenario.is_default = True
        return scenario

    async def delete(self, scenario: Scenario) -> Scenario:
        """Delete a scenario. If this was the default and other scenarios
        exist, promote the next-most-recent to default. If this was the
        last scenario, auto-spawn a fresh empty default to satisfy the
        invariant that every wallet has at least one scenario."""
        wallet_id = scenario.wallet_id
        was_default = scenario.is_default
        await self.db.delete(scenario)
        await self.db.flush()

        if was_default:
            # Promote the most-recently-updated remaining scenario, or
            # create a fresh default if none remain.
            remaining = await self.db.execute(
                select(Scenario)
                .where(Scenario.wallet_id == wallet_id)
                .order_by(Scenario.updated_at.desc(), Scenario.id.desc())
                .limit(1)
            )
            promote = remaining.scalar_one_or_none()
            if promote is not None:
                promote.is_default = True
            else:
                await self.create_default(wallet_id)
        return scenario

    async def save_calc_window(
        self,
        scenario: Scenario,
        start: Optional[date],
        end: Optional[date],
        duration_years: int,
        duration_months: int,
        window_mode: str,
    ) -> None:
        """Persist the calc-window config used for a results call."""
        scenario.start_date = start
        scenario.end_date = end
        scenario.duration_years = duration_years
        scenario.duration_months = duration_months
        scenario.window_mode = window_mode

    async def save_last_calc_snapshot(
        self,
        scenario: Scenario,
        snapshot_json: str,
        *,
        input_hash: Optional[str] = None,
    ) -> None:
        """Cache the last results-payload JSON, its input-hash, and the time.

        ``input_hash`` is a SHA-256 hex of the calc inputs; the roadmap
        endpoint compares it against a fresh hash to decide whether the
        snapshot's per-instance projected SUB earn dates are still valid.
        """
        scenario.last_calc_snapshot = snapshot_json
        scenario.last_calc_input_hash = input_hash
        scenario.last_calc_timestamp = datetime.now(timezone.utc)


def get_scenario_service(db: AsyncSession = Depends(get_db)) -> ScenarioService:
    """FastAPI dependency for ScenarioService."""
    return ScenarioService(db)
