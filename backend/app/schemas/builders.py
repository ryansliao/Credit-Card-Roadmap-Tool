"""Schema builders: ORM/calculator → Pydantic response schemas.

These helpers construct the read-model Pydantic schemas returned by the
routers from internal ORM rows and calculator result objects. They own
inheritance rules (e.g. SUB fields fall back from the library card when
the wallet row is null) and per-response derived fields (e.g. credit
totals).
"""

from __future__ import annotations

from typing import Literal, cast

from ..models import Card, CardInstance, Scenario, Wallet, WalletCard
from .card_instance import (
    CardInstanceRead,
    CreditTotalByCurrency as CICreditTotalByCurrency,
)
from .results import CardResultSchema, CategoryEarnItem, WalletResultSchema
from .scenario import ScenarioRead, ScenarioSummary
from .wallet import (
    CreditTotalByCurrency,
    WalletCardRead,
    WalletRead,
    WalletWithScenariosRead,
)


def _build_credit_totals(wc: WalletCard) -> list[CreditTotalByCurrency]:
    """Aggregate a wallet card's credit override values by the credit's native
    currency. Cash credits bucket under ``kind="cash"`` (currency_id=None);
    points credits bucket per currency so the UI can render ``pts`` alongside
    ``$``. Credits without a resolved currency (legacy rows) are treated as
    cash for backwards compatibility — ``wallet_card_credits.value`` was
    dollars before ``credit_currency_id`` was introduced.
    """
    if not wc.credit_overrides_rows:
        return []

    buckets: dict[tuple[str, int | None], CreditTotalByCurrency] = {}
    for row in wc.credit_overrides_rows:
        lib = row.library_credit
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
                value=float(row.value or 0),
            )
        else:
            existing.value += float(row.value or 0)
    # Stable ordering: cash first, then points sorted by currency name.
    return sorted(
        buckets.values(),
        key=lambda e: (0 if e.kind == "cash" else 1, e.currency_name or ""),
    )


def wc_read(wc: WalletCard, card: Card) -> WalletCardRead:
    """
    Build a WalletCardRead for API responses.

    SUB and fee fields fall back to the library Card when the wallet row stores
    null (inherit defaults). The database row is unchanged; only the read model
    exposes effective values for clients.
    """
    def _inh(wv, cv):
        return wv if wv is not None else cv

    return WalletCardRead(
        id=wc.id,
        wallet_id=wc.wallet_id,
        card_id=wc.card_id,
        card_name=card.name,
        transfer_enabler=bool(getattr(card, "transfer_enabler", False)),
        photo_slug=getattr(card, "photo_slug", None),
        issuer_name=card.issuer.name if card.issuer else None,
        network_tier_name=card.network_tier.name if getattr(card, "network_tier", None) else None,
        added_date=wc.added_date,
        sub_points=_inh(wc.sub_points, card.sub_points),
        sub_min_spend=_inh(wc.sub_min_spend, card.sub_min_spend),
        sub_months=_inh(wc.sub_months, card.sub_months),
        sub_spend_earn=_inh(wc.sub_spend_earn, card.sub_spend_earn),
        annual_bonus=_inh(wc.annual_bonus, card.annual_bonus),
        annual_bonus_percent=_inh(wc.annual_bonus_percent, card.annual_bonus_percent),
        annual_bonus_first_year_only=_inh(wc.annual_bonus_first_year_only, card.annual_bonus_first_year_only),
        years_counted=wc.years_counted,
        annual_fee=_inh(wc.annual_fee, card.annual_fee),
        first_year_fee=_inh(wc.first_year_fee, card.first_year_fee),
        sub_earned_date=wc.sub_earned_date,
        sub_projected_earn_date=wc.sub_projected_earn_date,
        closed_date=wc.closed_date,
        product_changed_date=wc.product_changed_date,
        acquisition_type=cast(Literal["opened", "product_change"], wc.acquisition_type),
        pc_from_card_id=wc.pc_from_card_id,
        panel=cast(Literal["in_wallet", "future_cards", "considering"], wc.panel),
        is_enabled=bool(wc.is_enabled),
        credit_totals=_build_credit_totals(wc),
    )


def wallet_read(wallet: Wallet) -> WalletRead:
    """Build a WalletRead with fully populated wallet_cards.

    The ORM ``wallet`` must have ``wallet_cards`` and each card's library
    ``card`` (with issuer / network_tier / credit_overrides_rows) eager-loaded.
    """
    return WalletRead(
        id=wallet.id,
        user_id=wallet.user_id,
        name=wallet.name,
        description=wallet.description,
        as_of_date=wallet.as_of_date,
        calc_start_date=wallet.calc_start_date,
        calc_end_date=wallet.calc_end_date,
        calc_duration_years=wallet.calc_duration_years,
        calc_duration_months=wallet.calc_duration_months,
        calc_window_mode=wallet.calc_window_mode,
        foreign_spend_percent=wallet.foreign_spend_percent,
        include_subs=wallet.include_subs,
        wallet_cards=[wc_read(wc, wc.card) for wc in wallet.wallet_cards],
    )


def _build_instance_credit_totals(
    inst: CardInstance,
) -> list[CICreditTotalByCurrency]:
    """Aggregate scenario-scoped credit override values for a card instance
    by the credit's native currency. Mirrors :func:`_build_credit_totals`
    but reads from ``ScenarioCardCredit`` rows attached to the instance."""
    rows = getattr(inst, "credit_overrides_rows", None) or []
    if not rows:
        return []
    buckets: dict[tuple[str, int | None], CICreditTotalByCurrency] = {}
    for row in rows:
        lib = row.library_credit
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
            buckets[key] = CICreditTotalByCurrency(
                kind=kind,
                currency_id=cur_id,
                currency_name=name,
                value=float(row.value or 0),
            )
        else:
            existing.value += float(row.value or 0)
    return sorted(
        buckets.values(),
        key=lambda e: (0 if e.kind == "cash" else 1, e.currency_name or ""),
    )


def card_instance_read(inst: CardInstance) -> CardInstanceRead:
    """Build a CardInstanceRead. Library Card must be eager-loaded on the
    instance (CardInstanceService.instance_load_opts() handles this)."""
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
        sub_points=inst.sub_points,
        sub_min_spend=inst.sub_min_spend,
        sub_months=inst.sub_months,
        sub_spend_earn=inst.sub_spend_earn,
        annual_bonus=inst.annual_bonus,
        annual_bonus_percent=inst.annual_bonus_percent,
        annual_bonus_first_year_only=inst.annual_bonus_first_year_only,
        years_counted=inst.years_counted,
        annual_fee=inst.annual_fee,
        first_year_fee=inst.first_year_fee,
        secondary_currency_rate=inst.secondary_currency_rate,
        sub_earned_date=inst.sub_earned_date,
        sub_projected_earn_date=inst.sub_projected_earn_date,
        pc_from_instance_id=inst.pc_from_instance_id,
        panel=cast(
            Literal["in_wallet", "future_cards", "considering"],
            inst.panel,
        ),
        is_enabled=bool(inst.is_enabled),
        credit_totals=_build_instance_credit_totals(inst),
    )


def scenario_summary(scenario: Scenario) -> ScenarioSummary:
    return ScenarioSummary.model_validate(scenario)


def scenario_read(scenario: Scenario) -> ScenarioRead:
    return ScenarioRead.model_validate(scenario)


def wallet_with_scenarios_read(
    wallet: Wallet,
    owned_instances: list[CardInstance],
    scenarios: list[Scenario],
) -> WalletWithScenariosRead:
    """Compose the new ``GET /wallet`` response."""
    return WalletWithScenariosRead(
        id=wallet.id,
        user_id=wallet.user_id,
        name=wallet.name,
        description=wallet.description,
        foreign_spend_percent=wallet.foreign_spend_percent or 0.0,
        card_instances=[card_instance_read(i) for i in owned_instances],
        scenarios=[scenario_summary(s) for s in scenarios],
    )


def wallet_to_schema(wallet, photo_slugs: dict[int, str | None] | None = None) -> WalletResultSchema:
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
            photo_slug=photo_slugs.get(cr.card_id) if photo_slugs else None,
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
