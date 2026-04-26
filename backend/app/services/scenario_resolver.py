"""Scenario resolver — assembles the inputs ``compute_wallet`` consumes.

Three-tier resolution precedence for owned cards:

    overlay.<field>      (per-scenario hypothetical, only on owned instances)
    card_instance.<field>  (the user's actual override)
    library_card.<field>   (catalog default)

For scenario-scoped (future) instances, only the second and third tiers
apply — overlays don't target future cards.

The resolver synthesises one ``CardData`` per active CardInstance, using
``card_instance.id`` as the synthetic ``CardData.id``. This keeps duplicates
of the same library card distinct in the calculator's eyes (each CSP is its
own card with its own SUB / fee / dates). Library-keyed external maps
(portal membership) are translated to instance-keyed maps inside the
resolver before they reach the calculator.

The calculator (``app.calculator``) is unchanged.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Optional

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..calculator import CardData, CreditLine
from ..database import get_db
from ..models import (
    CardInstance,
    Scenario,
    ScenarioCardCategoryPriority,
    ScenarioCardCredit,
    ScenarioCardGroupSelection,
    ScenarioCardMultiplier,
    ScenarioCardOverlay,
    ScenarioCurrencyCpp,
    ScenarioPortalShare,
    Wallet,
)
from .calculator_data_service import (
    CalculatorDataService,
    get_calculator_data_service,
)

if TYPE_CHECKING:
    from ..models import Credit


# The set of CardInstance fields where three-tier resolution applies.
# Lookup is by attribute name on the ORM class; matching attribute on
# ScenarioCardOverlay is the overlay layer.
_RESOLVABLE_FIELDS: tuple[str, ...] = (
    "sub_points",
    "sub_min_spend",
    "sub_months",
    "sub_spend_earn",
    "annual_bonus",
    "annual_bonus_percent",
    "annual_bonus_first_year_only",
    "annual_fee",
    "first_year_fee",
    "secondary_currency_rate",
    "sub_earned_date",
    "sub_projected_earn_date",
    "closed_date",
    "product_change_date",
    "is_enabled",
)


@dataclass
class ResolvedInstance:
    """An owned/future CardInstance with its overlay (if any) materialised
    into resolved field values. ``effective`` is a flat dict of the resolved
    field values; ``library_card_id`` and ``instance_id`` make the dual
    identity explicit."""

    instance: CardInstance
    overlay: Optional[ScenarioCardOverlay]
    effective: dict[str, object]

    @property
    def instance_id(self) -> int:
        return self.instance.id

    @property
    def library_card_id(self) -> int:
        return self.instance.card_id


@dataclass
class ComputeInputs:
    """Bundle of the kwargs needed by ``wallet_results.py`` to call
    ``compute_wallet``. Routers consume this directly."""

    # The full universe of CardData (library cards + per-instance copies for
    # active instances). Entries are unique by ``CardData.id``.
    all_cards: list[CardData]
    # Set of synthesised ``card_instance.id`` values for active instances.
    selected_ids: set[int]
    # The user's wallet-scoped spend (no scenario variation).
    spend: dict[str, float]
    # Foreign-spend percentage from the wallet (not the scenario).
    foreign_spend_pct: float
    housing_category_names: set[str]
    foreign_eligible_categories: set[str]
    # The list of resolved active instances (owned + future). Used by
    # downstream caller to drive SUB-projection writes.
    resolved_instances: list[ResolvedInstance]
    # Lookup helpers (used by the SUB-projection & roadmap steps).
    library_cards_by_id: dict[int, "CardData"]


class ScenarioResolver:
    """Builds ``ComputeInputs`` for a scenario.

    The resolver is the only place in the backend that reads from the
    overlay table. Callers feed the result into ``compute_wallet`` as-is.
    """

    def __init__(
        self,
        db: AsyncSession,
        calc_data: CalculatorDataService,
    ) -> None:
        self.db = db
        self.calc_data = calc_data

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def build_compute_inputs(
        self,
        scenario: Scenario,
        *,
        ref_date: date,
        window_end: date,
    ) -> ComputeInputs:
        wallet_id = scenario.wallet_id
        scenario_id = scenario.id

        # 1. Load wallet (for foreign_spend_percent).
        wallet = await self._load_wallet(wallet_id)

        # 2. Load active card instances (owned + this scenario's futures).
        instances = await self._load_active_instances(
            wallet_id, scenario_id, ref_date=ref_date, window_end=window_end
        )

        # 3. Load overlays for owned instances in this scenario.
        overlays = await self._load_overlays(scenario_id)
        overlay_by_instance: dict[int, ScenarioCardOverlay] = {
            o.card_instance_id: o for o in overlays
        }

        # 4. Resolve effective field values per instance.
        resolved: list[ResolvedInstance] = []
        for inst in instances:
            ov = overlay_by_instance.get(inst.id) if inst.scenario_id is None else None
            effective = self._resolve_effective(inst, ov)
            resolved.append(
                ResolvedInstance(instance=inst, overlay=ov, effective=effective)
            )

        # Apply post-resolution enable filter (overlay can disable an owned
        # instance scenario-locally; resolved value lives in `effective`).
        active_resolved: list[ResolvedInstance] = [
            r for r in resolved if bool(r.effective.get("is_enabled", True))
        ]

        # 5. Load CPP overrides (scenario-scoped) and library CardData.
        cpp_overrides = await self._load_cpp_overrides(scenario_id)
        all_library_card_data = await self.calc_data.load_card_data(
            cpp_overrides=cpp_overrides
        )
        library_cards_by_id: dict[int, CardData] = {
            cd.id: cd for cd in all_library_card_data
        }

        # 6. Load currency lookup tables for credit valuation.
        currency_defaults = await self.calc_data.load_currency_defaults()
        currency_kinds = await self.calc_data.load_currency_kinds()

        # 7. Load scenario-scoped credit rows keyed by card_instance_id.
        credits_by_instance = await self._load_credits_by_instance(scenario_id)

        # 8. Build per-instance CardData. For each active instance, clone
        #    the library CardData and patch with effective field values.
        per_instance_card_data: list[CardData] = []
        active_library_card_ids: set[int] = set()
        for r in active_resolved:
            lib_cd = library_cards_by_id.get(r.library_card_id)
            if lib_cd is None:
                continue
            active_library_card_ids.add(r.library_card_id)
            per_instance_card_data.append(
                self._build_instance_card_data(
                    r,
                    lib_cd,
                    credits_by_instance.get(r.instance_id, []),
                    cpp_overrides,
                    currency_defaults,
                    currency_kinds,
                )
            )

        # 9. Compose all_cards = one CardData per active instance.
        #
        # Important: do NOT also include the rest of the library cards.
        # ``CardData.id`` for a per-instance entry is the synthetic
        # ``card_instance.id``; library card ids share the same numeric
        # space, so adding library entries lets ``c.id in selected_ids``
        # match library cards whose id happens to coincide with an
        # instance id (e.g. library card 8 = Chase Freedom Flex collides
        # with instance #8 = Discover IT Cash Back). The frontend never
        # consumes ``c.selected = false`` rows, so dropping them is safe.
        all_cards: list[CardData] = per_instance_card_data
        selected_ids: set[int] = {r.instance_id for r in active_resolved}

        # 10. Apply scenario-scoped multiplier overrides per instance.
        multiplier_rows = await self._load_multipliers(scenario_id)
        if multiplier_rows:
            all_cards = self._apply_instance_multipliers(all_cards, multiplier_rows)

        # 11. Apply scenario-scoped category priority pins per instance.
        priorities_by_instance = await self._load_category_priorities(scenario_id)
        if priorities_by_instance:
            all_cards = self._apply_category_priorities(
                all_cards, priorities_by_instance
            )

        # 12. Apply scenario-scoped portal shares (translate library
        #     card_ids to instance ids).
        portal_shares = await self._load_portal_shares(scenario_id)
        if portal_shares:
            card_ids_by_portal_lib = await self.calc_data.load_card_ids_by_portal()
            instance_ids_by_portal: dict[int, set[int]] = {}
            for portal_id, lib_ids in card_ids_by_portal_lib.items():
                bucket: set[int] = set()
                for r in active_resolved:
                    if r.library_card_id in lib_ids:
                        bucket.add(r.instance_id)
                if bucket:
                    instance_ids_by_portal[portal_id] = bucket
            if instance_ids_by_portal:
                all_cards = self._apply_portal_shares(
                    all_cards, portal_shares, instance_ids_by_portal
                )

        # 13. Wallet-scoped spend + supporting dimension lookups.
        spend = await self.calc_data.load_wallet_spend_items(wallet_id)
        housing_names = await self.calc_data.load_housing_category_names()
        foreign_eligible = await self.calc_data.load_foreign_eligible_category_names()

        return ComputeInputs(
            all_cards=all_cards,
            selected_ids=selected_ids,
            spend=spend,
            foreign_spend_pct=wallet.foreign_spend_percent or 0.0,
            housing_category_names=housing_names,
            foreign_eligible_categories=foreign_eligible,
            resolved_instances=active_resolved,
            library_cards_by_id=library_cards_by_id,
        )

    # ------------------------------------------------------------------
    # Loaders
    # ------------------------------------------------------------------

    async def _load_wallet(self, wallet_id: int) -> Wallet:
        result = await self.db.execute(
            select(Wallet).where(Wallet.id == wallet_id)
        )
        wallet = result.scalar_one_or_none()
        assert wallet is not None, f"Wallet {wallet_id} not found in resolver"
        return wallet

    async def _load_active_instances(
        self,
        wallet_id: int,
        scenario_id: int,
        *,
        ref_date: date,
        window_end: date,
    ) -> list[CardInstance]:
        """Active = enabled, opens before window_end, not yet closed (or
        closed after ref_date), and either owned or scoped to this
        scenario. Note: overlay closed_date is applied later in the
        resolution pass; this filter is on the instance's own dates."""
        result = await self.db.execute(
            select(CardInstance)
            .options(selectinload(CardInstance.card))
            .where(
                CardInstance.wallet_id == wallet_id,
                CardInstance.is_enabled == True,  # noqa: E712
                CardInstance.opening_date < window_end,
                (
                    CardInstance.closed_date.is_(None)
                    | (CardInstance.closed_date >= ref_date)
                ),
                (
                    (CardInstance.scenario_id.is_(None))
                    | (CardInstance.scenario_id == scenario_id)
                ),
            )
        )
        return list(result.scalars().all())

    async def _load_overlays(self, scenario_id: int) -> list[ScenarioCardOverlay]:
        result = await self.db.execute(
            select(ScenarioCardOverlay).where(
                ScenarioCardOverlay.scenario_id == scenario_id
            )
        )
        return list(result.scalars().all())

    async def _load_cpp_overrides(self, scenario_id: int) -> dict[int, float]:
        result = await self.db.execute(
            select(ScenarioCurrencyCpp).where(
                ScenarioCurrencyCpp.scenario_id == scenario_id
            )
        )
        return {row.currency_id: float(row.cents_per_point) for row in result.scalars()}

    async def _load_credits_by_instance(
        self, scenario_id: int
    ) -> dict[int, list[ScenarioCardCredit]]:
        result = await self.db.execute(
            select(ScenarioCardCredit)
            .options(selectinload(ScenarioCardCredit.library_credit))
            .where(ScenarioCardCredit.scenario_id == scenario_id)
        )
        out: dict[int, list[ScenarioCardCredit]] = {}
        for row in result.scalars().all():
            out.setdefault(row.card_instance_id, []).append(row)
        return out

    async def _load_multipliers(
        self, scenario_id: int
    ) -> list[ScenarioCardMultiplier]:
        result = await self.db.execute(
            select(ScenarioCardMultiplier)
            .options(selectinload(ScenarioCardMultiplier.spend_category))
            .where(ScenarioCardMultiplier.scenario_id == scenario_id)
        )
        return list(result.scalars().all())

    async def _load_category_priorities(
        self, scenario_id: int
    ) -> dict[int, frozenset[str]]:
        result = await self.db.execute(
            select(ScenarioCardCategoryPriority)
            .options(selectinload(ScenarioCardCategoryPriority.spend_category))
            .where(ScenarioCardCategoryPriority.scenario_id == scenario_id)
        )
        per_instance: dict[int, set[str]] = {}
        for r in result.scalars().all():
            cat = r.spend_category.category if r.spend_category else ""
            key = (cat or "").strip().lower()
            if not key:
                continue
            per_instance.setdefault(r.card_instance_id, set()).add(key)
        return {iid: frozenset(keys) for iid, keys in per_instance.items()}

    async def _load_portal_shares(self, scenario_id: int) -> dict[int, float]:
        result = await self.db.execute(
            select(ScenarioPortalShare).where(
                ScenarioPortalShare.scenario_id == scenario_id
            )
        )
        return {row.travel_portal_id: float(row.share) for row in result.scalars()}

    # ------------------------------------------------------------------
    # Three-tier resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_effective(
        instance: CardInstance,
        overlay: Optional[ScenarioCardOverlay],
    ) -> dict[str, object]:
        """For every resolvable field, return overlay.<f> if non-None,
        else instance.<f>."""
        effective: dict[str, object] = {}
        for f in _RESOLVABLE_FIELDS:
            overlay_val = getattr(overlay, f, None) if overlay is not None else None
            if overlay_val is not None:
                effective[f] = overlay_val
                continue
            inst_val = getattr(instance, f, None)
            effective[f] = inst_val
        # opening_date is not overlay-able (an owned card's opening date
        # is a fact, not a hypothesis); always take it from the instance.
        effective["opening_date"] = instance.opening_date
        return effective

    # ------------------------------------------------------------------
    # CardData synthesis (three-tier resolved → CardData)
    # ------------------------------------------------------------------

    def _build_instance_card_data(
        self,
        resolved: ResolvedInstance,
        lib_cd: CardData,
        credit_rows: list[ScenarioCardCredit],
        cpp_overrides: dict[int, float],
        currency_defaults: dict[int, float],
        currency_kinds: dict[int, str],
    ) -> CardData:
        eff = resolved.effective

        # Library defaults for fields where None means "keep library value"
        def _coalesce(field: str, lib_value):
            v = eff.get(field)
            return v if v is not None else lib_value

        annual_fee = _coalesce("annual_fee", lib_cd.annual_fee)
        first_year_fee = _coalesce("first_year_fee", lib_cd.first_year_fee)

        # Build credit lines from the scenario-scoped credit rows.
        credit_lines: list[CreditLine] = []
        for row in credit_rows:
            lib_credit = row.library_credit
            if lib_credit is None:
                continue
            dollar_value = row.value
            cur_id = lib_credit.credit_currency_id
            if cur_id is not None and currency_kinds.get(cur_id) != "cash":
                cpp = cpp_overrides.get(cur_id) or currency_defaults.get(cur_id, 1.0)
                dollar_value = row.value * cpp / 100.0
            credit_lines.append(
                CreditLine(
                    library_credit_id=row.library_credit_id,
                    name=lib_credit.credit_name,
                    value=dollar_value,
                    excludes_first_year=lib_credit.excludes_first_year,
                    is_one_time=lib_credit.is_one_time,
                )
            )

        return dataclasses.replace(
            lib_cd,
            id=resolved.instance_id,  # synthetic id = card_instance.id
            sub_points=_coalesce("sub_points", lib_cd.sub_points),
            sub_min_spend=_coalesce("sub_min_spend", lib_cd.sub_min_spend),
            sub_months=_coalesce("sub_months", lib_cd.sub_months),
            sub_spend_earn=_coalesce("sub_spend_earn", lib_cd.sub_spend_earn),
            annual_bonus=_coalesce("annual_bonus", lib_cd.annual_bonus),
            annual_bonus_percent=_coalesce(
                "annual_bonus_percent", lib_cd.annual_bonus_percent
            ),
            annual_bonus_first_year_only=_coalesce(
                "annual_bonus_first_year_only",
                lib_cd.annual_bonus_first_year_only,
            ),
            annual_fee=annual_fee,
            first_year_fee=first_year_fee,
            credit_lines=credit_lines,
            secondary_currency_rate=_coalesce(
                "secondary_currency_rate", lib_cd.secondary_currency_rate
            ),
            wallet_added_date=eff.get("opening_date"),
            wallet_closed_date=eff.get("closed_date"),
            sub_projected_earn_date=eff.get("sub_projected_earn_date"),
        )

    # ------------------------------------------------------------------
    # Per-instance override appliers
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_instance_multipliers(
        cards: list[CardData],
        multiplier_rows: list[ScenarioCardMultiplier],
    ) -> list[CardData]:
        overrides_by_instance: dict[int, dict[str, float]] = {}
        for row in multiplier_rows:
            cat = row.spend_category.category if row.spend_category else None
            if not cat:
                continue
            overrides_by_instance.setdefault(row.card_instance_id, {})[cat] = row.multiplier

        if not overrides_by_instance:
            return cards
        out: list[CardData] = []
        for cd in cards:
            ov = overrides_by_instance.get(cd.id)
            if not ov:
                out.append(cd)
                continue
            patched = dict(cd.multipliers)
            patched.update(ov)
            out.append(dataclasses.replace(cd, multipliers=patched))
        return out

    @staticmethod
    def _apply_category_priorities(
        cards: list[CardData],
        priorities_by_instance: dict[int, frozenset[str]],
    ) -> list[CardData]:
        out: list[CardData] = []
        for cd in cards:
            pins = priorities_by_instance.get(cd.id)
            if not pins:
                out.append(cd)
                continue
            out.append(dataclasses.replace(cd, priority_categories=pins))
        return out

    @staticmethod
    def _apply_portal_shares(
        cards: list[CardData],
        shares_by_portal: dict[int, float],
        instance_ids_by_portal: dict[int, set[int]],
    ) -> list[CardData]:
        memberships_by_instance: dict[int, dict[int, float]] = {}
        for portal_id, share in shares_by_portal.items():
            if share <= 0.0:
                continue
            for iid in instance_ids_by_portal.get(portal_id, ()):
                memberships_by_instance.setdefault(iid, {})[portal_id] = share
        if not memberships_by_instance:
            return cards
        out: list[CardData] = []
        for cd in cards:
            memberships = memberships_by_instance.get(cd.id)
            if not memberships:
                out.append(cd)
                continue
            out.append(
                dataclasses.replace(
                    cd,
                    portal_share=max(memberships.values()),
                    portal_memberships=dict(memberships),
                )
            )
        return out


def get_scenario_resolver(
    db: AsyncSession = Depends(get_db),
    calc_data: CalculatorDataService = Depends(get_calculator_data_service),
) -> ScenarioResolver:
    """FastAPI dependency for ScenarioResolver."""
    return ScenarioResolver(db, calc_data)
