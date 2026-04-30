"""Schema builders: ORM rows + calculator results → Pydantic response
schemas.

These helpers own inheritance rules (e.g. fields that fall back from the
library card when the instance row is null) and per-response derived
fields (e.g. credit totals).
"""

from __future__ import annotations

from typing import Literal, cast

from ..models import CardInstance, Scenario, Wallet, WalletUserSpendCategoryWeight
from .card_instance import (
    CardInstanceRead,
    CreditTotalByCurrency,
    WalletCardCreditValue,
)
from .results import CardResultSchema, CategoryEarnItem, WalletResultSchema
from .scenario import ScenarioRead, ScenarioSummary
from .spend import WalletCategoryWeightOverrideRead
from .wallet import WalletWithScenariosRead


def _build_instance_credit_totals(
    inst: CardInstance,
) -> list[CreditTotalByCurrency]:
    """Aggregate credit values for a card instance by the credit's native
    currency. Cash credits bucket under ``kind="cash"`` (currency_id=None);
    points credits bucket per currency so the UI can render ``pts``
    alongside ``$``.

    Owned cards (``scenario_id IS NULL``) merge library defaults from
    ``card.card_credit_links`` with wallet-level overrides from
    ``wallet_credit_overrides``. Per-scenario overrides don't apply at the
    wallet view (it's scenario-agnostic). Scenario-scoped instances use
    ``credit_overrides_rows`` directly (rows are necessarily scoped to
    that one scenario since the instance itself is scenario-scoped).
    """
    sources: list[tuple[float | None, object]] = []
    if inst.scenario_id is None:
        # library defaults keyed by credit id, then overlay wallet overrides
        merged: dict[int, tuple[float | None, object]] = {}
        for link in getattr(inst.card, "card_credit_links", None) or []:
            lib = link.credit
            if lib is None:
                continue
            raw = link.value if link.value is not None else lib.value
            merged[lib.id] = (raw, lib)
        for row in getattr(inst, "wallet_credit_overrides", None) or []:
            lib = row.library_credit
            if lib is None:
                continue
            merged[lib.id] = (row.value, lib)
        sources = list(merged.values())
    else:
        for row in getattr(inst, "credit_overrides_rows", None) or []:
            sources.append((row.value, row.library_credit))
    if not sources:
        return []
    buckets: dict[tuple[str, int | None], CreditTotalByCurrency] = {}
    for value, lib in sources:
        currency = lib.credit_currency if lib is not None else None
        if currency is not None and currency.reward_kind == "points":
            key = ("points", currency.id)
            name = currency.name
            kind = "points"
            cur_id: int | None = currency.id
        else:
            key = ("cash", None)
            name = currency.name if currency is not None else None
            kind = "cash"
            cur_id = currency.id if currency is not None else None
        existing = buckets.get(key)
        if existing is None:
            buckets[key] = CreditTotalByCurrency(
                kind=kind,
                currency_id=cur_id,
                currency_name=name,
                value=float(value or 0),
            )
        else:
            existing.value += float(value or 0)
    return sorted(
        buckets.values(),
        key=lambda e: (0 if e.kind == "cash" else 1, e.currency_name or ""),
    )


def card_instance_read(inst: CardInstance) -> CardInstanceRead:
    """Build a CardInstanceRead. Library Card must be eager-loaded on the
    instance (CardInstanceService.instance_load_opts() handles this).

    Override fields (sub_*, annual_*, first_year_fee, secondary_currency_rate)
    fall back to the library card's value when null on the row, so consumers
    that don't carry library data (e.g. WalletTab) display the effective
    value. Diff-against-library still happens at write time in the modal's
    update-payload builder.
    """
    card = inst.card
    return CardInstanceRead(
        id=inst.id,
        wallet_id=inst.wallet_id,
        scenario_id=inst.scenario_id,
        card_id=inst.card_id,
        card_name=card.name,
        transfer_enabler=bool(getattr(card, "transfer_enabler", False)),
        photo_slug=getattr(card, "photo_slug", None),
        issuer_name=card.issuer.name if getattr(card, "issuer", None) else None,
        network_tier_name=(
            card.network_tier.name
            if getattr(card, "network_tier", None)
            else None
        ),
        opening_date=inst.opening_date,
        product_change_date=inst.product_change_date,
        closed_date=inst.closed_date,
        sub_points=inst.sub_points if inst.sub_points is not None else card.sub_points,
        sub_min_spend=inst.sub_min_spend if inst.sub_min_spend is not None else card.sub_min_spend,
        sub_months=inst.sub_months if inst.sub_months is not None else card.sub_months,
        sub_spend_earn=inst.sub_spend_earn,
        annual_bonus=inst.annual_bonus if inst.annual_bonus is not None else card.annual_bonus,
        annual_bonus_percent=(
            inst.annual_bonus_percent
            if inst.annual_bonus_percent is not None
            else getattr(card, "annual_bonus_percent", None)
        ),
        annual_bonus_first_year_only=(
            inst.annual_bonus_first_year_only
            if inst.annual_bonus_first_year_only is not None
            else getattr(card, "annual_bonus_first_year_only", None)
        ),
        years_counted=inst.years_counted,
        annual_fee=inst.annual_fee if inst.annual_fee is not None else card.annual_fee,
        first_year_fee=(
            inst.first_year_fee
            if inst.first_year_fee is not None
            else card.first_year_fee
        ),
        secondary_currency_rate=(
            inst.secondary_currency_rate
            if inst.secondary_currency_rate is not None
            else getattr(card, "secondary_currency_rate", None)
        ),
        pc_from_instance_id=inst.pc_from_instance_id,
        panel=cast(
            Literal["in_wallet", "future_cards", "considering"],
            inst.panel,
        ),
        is_enabled=bool(inst.is_enabled),
        credit_totals=_build_instance_credit_totals(inst),
        credit_overrides=[
            WalletCardCreditValue(
                library_credit_id=row.library_credit_id, value=float(row.value)
            )
            for row in (
                getattr(inst, "wallet_credit_overrides", None) or []
            )
        ] if inst.scenario_id is None else [],
    )


def scenario_summary(scenario: Scenario) -> ScenarioSummary:
    return ScenarioSummary.model_validate(scenario)


def scenario_read(scenario: Scenario) -> ScenarioRead:
    return ScenarioRead.model_validate(scenario)


def wallet_with_scenarios_read(
    wallet: Wallet,
    owned_instances: list[CardInstance],
    scenarios: list[Scenario],
    category_weight_overrides: list[WalletUserSpendCategoryWeight] = (),
) -> WalletWithScenariosRead:
    return WalletWithScenariosRead(
        id=wallet.id,
        user_id=wallet.user_id,
        name=wallet.name,
        description=wallet.description,
        foreign_spend_percent=wallet.foreign_spend_percent or 0.0,
        housing_type=wallet.housing_type,
        card_instances=[card_instance_read(i) for i in owned_instances],
        scenarios=[scenario_summary(s) for s in scenarios],
        category_weight_overrides=[
            WalletCategoryWeightOverrideRead.model_validate(o)
            for o in category_weight_overrides
        ],
    )


def wallet_to_schema(
    wallet, photo_slugs: dict[int, str | None] | None = None
) -> WalletResultSchema:
    card_schemas = [
        CardResultSchema(
            card_id=cr.card_id,
            card_name=cr.card_name,
            selected=cr.selected,
            effective_annual_fee=cr.effective_annual_fee,
            card_effective_annual_fee=cr.card_effective_annual_fee,
            card_active_years=cr.card_active_years,
            total_points=cr.total_points,
            annual_point_earn=cr.annual_point_earn,
            annual_point_earn_window=cr.annual_point_earn_window,
            credit_valuation=cr.credit_valuation,
            annual_fee=cr.annual_fee,
            first_year_fee=cr.first_year_fee,
            sub_points=cr.sub_points,
            annual_bonus=cr.annual_bonus,
            annual_bonus_percent=cr.annual_bonus_percent,
            annual_bonus_first_year_only=cr.annual_bonus_first_year_only,
            sub_extra_spend=cr.sub_extra_spend,
            sub_spend_earn=cr.sub_spend_earn,
            sub_opp_cost_dollars=cr.sub_opp_cost_dollars,
            sub_opp_cost_gross_dollars=cr.sub_opp_cost_gross_dollars,
            sub_eaf_contribution=cr.sub_eaf_contribution,
            card_sub_eaf_contribution=cr.card_sub_eaf_contribution,
            avg_spend_multiplier=cr.avg_spend_multiplier,
            cents_per_point=cr.cents_per_point,
            effective_currency_name=cr.effective_currency_name,
            effective_currency_id=cr.effective_currency_id,
            effective_reward_kind=cr.effective_reward_kind,
            effective_currency_photo_slug=cr.effective_currency_photo_slug,
            category_earn=[
                CategoryEarnItem(category=cat, points=pts)
                for cat, pts in cr.category_earn
            ],
            category_multipliers=cr.category_multipliers,
            secondary_currency_earn=cr.secondary_currency_earn,
            secondary_currency_name=cr.secondary_currency_name,
            secondary_currency_id=cr.secondary_currency_id,
            accelerator_activations=cr.accelerator_activations,
            accelerator_bonus_points=cr.accelerator_bonus_points,
            accelerator_cost_points=cr.accelerator_cost_points,
            secondary_currency_net_earn=cr.secondary_currency_net_earn,
            secondary_currency_value_dollars=cr.secondary_currency_value_dollars,
            housing_fee_dollars=cr.housing_fee_dollars,
            photo_slug=photo_slugs.get(cr.card_id) if photo_slugs else None,
            sub_projected_earn_date=cr.sub_projected_earn_date,
        )
        for cr in wallet.card_results
    ]

    return WalletResultSchema(
        years_counted=wallet.years_counted,
        total_effective_annual_fee=wallet.total_effective_annual_fee,
        total_points_earned=wallet.total_points_earned,
        point_income=wallet.point_income,
        total_sub_eaf_contribution=wallet.total_sub_eaf_contribution,
        total_cash_reward_dollars=wallet.total_cash_reward_dollars,
        total_reward_value_usd=wallet.total_reward_value_usd,
        currency_pts=wallet.currency_pts,
        currency_pts_by_id=wallet.currency_pts_by_id,
        wallet_window_years=wallet.wallet_window_years,
        currency_window_years=wallet.currency_window_years,
        secondary_currency_pts=wallet.secondary_currency_pts,
        secondary_currency_pts_by_id=wallet.secondary_currency_pts_by_id,
        card_results=card_schemas,
    )
