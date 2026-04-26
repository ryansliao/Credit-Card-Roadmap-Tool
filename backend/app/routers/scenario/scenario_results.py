"""Scenario results (EV calculation) and roadmap endpoints.

Mirrors the legacy ``wallet_results.py`` orchestration but reads from
``Scenario`` + ``CardInstance`` via :class:`ScenarioResolver`. The
calculator (``app.calculator``) is unchanged.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth import get_current_user
from ...calculator import calc_annual_allocated_spend, compute_wallet, plan_sub_targeting
from ...database import get_db
from ...date_utils import (
    add_months,
    is_sub_earnable,
    months_in_half_open_interval,
    projected_sub_earn_date,
    years_counted_from_total_months,
)
from ...models import User
from ...schemas import (
    RoadmapCardStatus,
    RoadmapResponse,
    RoadmapRuleStatus,
    WalletResultResponseSchema,
    WalletResultSchema,
    wallet_to_schema,
)
from ...services import (
    CalculatorDataService,
    CardInstanceService,
    IssuerService,
    ScenarioResolver,
    ScenarioService,
    get_card_instance_service,
    get_issuer_service,
    get_scenario_resolver,
    get_scenario_service,
)

router = APIRouter(tags=["scenarios"])


@router.get(
    "/scenarios/{scenario_id}/results",
    response_model=WalletResultResponseSchema,
)
async def scenario_results(
    scenario_id: int,
    start_date: Optional[date] = None,
    reference_date: Optional[date] = None,
    end_date: Optional[date] = None,
    duration_years: int = Query(0, ge=0),
    duration_months: int = Query(0, ge=0),
    projection_years: int = 2,
    projection_months: int = 0,
    spend_overrides: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    scenario_service: ScenarioService = Depends(get_scenario_service),
    resolver: ScenarioResolver = Depends(get_scenario_resolver),
):
    """Compute the scenario's EV (effective fees, points, credits, SUB
    opportunity cost). Persists the calc window onto the scenario and
    caches the response JSON."""
    overrides: dict[str, float] = {}
    if spend_overrides:
        try:
            overrides = json.loads(spend_overrides)
        except (json.JSONDecodeError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="spend_overrides must be valid JSON (e.g. '{\"Dining\": 5000}')",
            )
    scenario = await scenario_service.get_user_scenario(scenario_id, user)

    if (
        start_date is not None
        and reference_date is not None
        and start_date != reference_date
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_date and reference_date disagree; send only one.",
        )
    user_provided_start = start_date if start_date is not None else reference_date
    ref_date = user_provided_start or date.today()

    duration_span = duration_years * 12 + duration_months
    if end_date is not None and duration_span > 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Do not send end_date together with duration_years/duration_months.",
        )

    resp_end: Optional[date] = None
    resp_dur_y, resp_dur_m = 0, 0
    total_months: int
    today_dt = date.today()

    if end_date is not None:
        try:
            total_months = months_in_half_open_interval(ref_date, end_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="end_date must be after start_date.",
            ) from None
        yc = years_counted_from_total_months(total_months)
        resp_end = end_date
        window_end = end_date
    elif duration_span > 0:
        window_end = add_months(today_dt, duration_span)
        total_months = months_in_half_open_interval(ref_date, window_end)
        yc = years_counted_from_total_months(total_months)
        resp_dur_y, resp_dur_m = duration_years, duration_months
    else:
        window_end = add_months(today_dt, projection_years * 12 + projection_months)
        total_months = months_in_half_open_interval(ref_date, window_end)
        yc = max(1, projection_years + (1 if projection_months >= 6 else 0))

    inputs = await resolver.build_compute_inputs(
        scenario, ref_date=ref_date, window_end=window_end
    )

    _save_window_mode = "end" if end_date is not None else "duration"
    await scenario_service.save_calc_window(
        scenario,
        start=ref_date,
        end=resp_end,
        duration_years=resp_dur_y,
        duration_months=resp_dur_m,
        window_mode=_save_window_mode,
    )

    if not inputs.selected_ids:
        empty_response = WalletResultResponseSchema(
            wallet_id=scenario.wallet_id,
            wallet_name=scenario.name,
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            start_date=ref_date,
            end_date=resp_end,
            duration_years=resp_dur_y,
            duration_months=resp_dur_m,
            total_months=total_months,
            as_of_date=ref_date,
            projection_years=projection_years,
            projection_months=projection_months,
            years_counted=yc,
            wallet=WalletResultSchema(
                years_counted=yc,
                total_effective_annual_fee=0,
                total_points_earned=0,
                point_income=0,
                total_cash_reward_dollars=0,
                total_reward_value_usd=0,
            ),
        )
        await scenario_service.save_last_calc_snapshot(
            scenario, empty_response.model_dump_json()
        )
        await db.commit()
        return empty_response

    modified_cards = inputs.all_cards
    selected_ids = inputs.selected_ids
    spend = dict(inputs.spend)
    if overrides:
        spend.update(overrides)

    # SUB planning. Use the synthesised instance ids for everything; that's
    # what CardData.id holds for active instances after the resolver builds
    # them.
    selected_card_data = [c for c in modified_cards if c.id in selected_ids]
    wcids = {c.currency.id for c in selected_card_data}

    # Instances that exist as of ref_date (added on or before ref_date) —
    # their SUB windows are history.
    in_wallet_now_instance_ids = {
        r.instance_id
        for r in inputs.resolved_instances
        if (r.effective.get("opening_date") or r.instance.opening_date) <= ref_date
    }

    def _has_sub_window(cd) -> bool:
        if cd.id in in_wallet_now_instance_ids:
            return False
        if not cd.sub_points or not cd.sub_min_spend or not cd.wallet_added_date:
            return False
        if cd.sub_months:
            window_end_dt = add_months(cd.wallet_added_date, cd.sub_months)
            if ref_date >= window_end_dt:
                return False
        return True

    sub_priority_card_ids = {
        cd.id
        for cd in selected_card_data
        if _has_sub_window(cd)
        and (
            not cd.sub_min_spend
            or calc_annual_allocated_spend(
                cd, selected_card_data, spend, wcids
            ) < cd.sub_min_spend
        )
    }

    sub_cards_for_plan = [cd for cd in selected_card_data if _has_sub_window(cd)]
    sub_plan = plan_sub_targeting(
        sub_cards_for_plan,
        spend,
        ref_date,
        wcids,
        housing_category_names=inputs.housing_category_names,
    )

    plan_rates: dict[int, float] = {
        s.card_id: s.daily_spend_allocated for s in sub_plan.schedules
    }
    total_daily_spend = sum(spend.values()) / 365.0
    card_daily_rates: dict[int, float] = {}
    for cd in selected_card_data:
        if cd.id in plan_rates:
            card_daily_rates[cd.id] = plan_rates[cd.id]
        else:
            allocated = calc_annual_allocated_spend(
                cd, selected_card_data, spend, wcids, sub_priority_card_ids
            )
            card_daily_rates[cd.id] = allocated / 365.0

    plan_earn_dates: dict[int, date] = {
        s.card_id: s.projected_earn_date for s in sub_plan.schedules
    }
    projected_dates: dict[int, Optional[date]] = {}
    for r in inputs.resolved_instances:
        opening = r.effective.get("opening_date") or r.instance.opening_date
        if opening <= ref_date:
            proj: Optional[date] = None
        else:
            lib_cd = inputs.library_cards_by_id.get(r.library_card_id)
            eff_min = r.effective.get("sub_min_spend")
            if eff_min is None and lib_cd is not None:
                eff_min = lib_cd.sub_min_spend
            eff_months = r.effective.get("sub_months")
            if eff_months is None and lib_cd is not None:
                eff_months = lib_cd.sub_months
            eff_sub = r.effective.get("sub_points")
            if eff_sub is None and lib_cd is not None:
                eff_sub = lib_cd.sub_points
            if not eff_sub or not eff_min:
                proj = None
            elif r.instance_id in sub_priority_card_ids:
                proj = projected_sub_earn_date(
                    opening, eff_min, eff_months, total_daily_spend
                )
            elif r.instance_id in plan_earn_dates:
                proj = plan_earn_dates[r.instance_id]
            else:
                daily_rate = card_daily_rates.get(r.instance_id, 0.0)
                proj = projected_sub_earn_date(
                    opening, eff_min, eff_months, daily_rate
                )
        projected_dates[r.instance_id] = proj

    modified_cards = [
        dataclasses.replace(
            c,
            sub_earnable=(
                False
                if c.id in in_wallet_now_instance_ids
                else is_sub_earnable(
                    c.sub_min_spend, c.sub_months, total_daily_spend
                )
            ),
            sub_projected_earn_date=projected_dates.get(
                c.id, c.sub_projected_earn_date
            ),
        )
        for c in modified_cards
    ]

    wallet_result = compute_wallet(
        all_cards=modified_cards,
        selected_ids=selected_ids,
        spend=spend,
        years=yc,
        window_start=ref_date,
        window_end=window_end,
        sub_priority_card_ids=sub_priority_card_ids,
        housing_category_names=inputs.housing_category_names,
        foreign_spend_pct=inputs.foreign_spend_pct,
        foreign_eligible_categories=inputs.foreign_eligible_categories,
    )

    # photo_slug lives on the ORM ``Card``, not on ``CardData``, so resolve
    # it via a separate lookup against the library Card table keyed by the
    # active instances' library card_ids.
    library_card_ids = {r.library_card_id for r in inputs.resolved_instances}
    library_cards_orm = await CalculatorDataService(db).load_cards_by_ids(
        library_card_ids
    )
    photo_slugs: dict[int, str | None] = {}
    for r in inputs.resolved_instances:
        card = library_cards_orm.get(r.library_card_id)
        photo_slugs[r.instance_id] = (
            getattr(card, "photo_slug", None) if card else None
        )

    response = WalletResultResponseSchema(
        wallet_id=scenario.wallet_id,
        wallet_name=scenario.name,
        scenario_id=scenario.id,
        scenario_name=scenario.name,
        start_date=ref_date,
        end_date=resp_end,
        duration_years=resp_dur_y,
        duration_months=resp_dur_m,
        total_months=total_months,
        as_of_date=ref_date,
        projection_years=projection_years,
        projection_months=projection_months,
        years_counted=wallet_result.years_counted,
        wallet=wallet_to_schema(wallet_result, photo_slugs=photo_slugs),
    )
    await scenario_service.save_last_calc_snapshot(
        scenario, response.model_dump_json()
    )
    await db.commit()
    return response


@router.get(
    "/scenarios/{scenario_id}/results/latest",
    response_model=Optional[WalletResultResponseSchema],
)
async def scenario_results_latest(
    scenario_id: int,
    user: User = Depends(get_current_user),
    scenario_service: ScenarioService = Depends(get_scenario_service),
):
    """Return the cached last results payload for this scenario, or null
    if no calculation has been run yet."""
    scenario = await scenario_service.get_user_scenario(scenario_id, user)
    if not scenario.last_calc_snapshot:
        return None
    try:
        return WalletResultResponseSchema.model_validate_json(
            scenario.last_calc_snapshot
        )
    except Exception:
        return None


@router.get(
    "/scenarios/{scenario_id}/roadmap",
    response_model=RoadmapResponse,
)
async def scenario_roadmap(
    scenario_id: int,
    as_of_date: Optional[date] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    scenario_service: ScenarioService = Depends(get_scenario_service),
    resolver: ScenarioResolver = Depends(get_scenario_resolver),
    instance_service: CardInstanceService = Depends(get_card_instance_service),
    issuer_service: IssuerService = Depends(get_issuer_service),
):
    """Compute roadmap status: 5/24, per-instance SUB status, issuer
    velocity rules. Future cards live on the scenario; owned cards are
    shared across all scenarios."""
    scenario = await scenario_service.get_user_scenario(scenario_id, user)
    today = as_of_date or date.today()

    instances = await instance_service.list_for_scenario(
        scenario.wallet_id, scenario_id
    )
    instances = [i for i in instances if i.is_enabled]

    # 5/24 anchored to the latest planned future open in the scenario.
    future_open_dates = [
        i.opening_date
        for i in instances
        if i.opening_date > today and i.product_change_date is None
    ]
    five_twenty_four_as_of = (
        max(future_open_dates) if future_open_dates else today
    )

    rules = await issuer_service.list_application_rules()

    # Spend dict for SUB-projection rate calculation.
    inputs = await resolver.build_compute_inputs(
        scenario,
        ref_date=today,
        window_end=add_months(today, 24),
    )
    daily_rate = sum(inputs.spend.values()) / 365.0

    card_statuses: list[RoadmapCardStatus] = []
    personal_cards_24mo: list[str] = []
    cutoff_24mo = five_twenty_four_as_of - timedelta(days=730)

    for inst in instances:
        card = inst.card
        is_active = inst.closed_date is None
        is_pc = inst.product_change_date is not None

        # 5/24 counts personal cards opened (not PC'd) in the trailing 24mo.
        if (
            not card.business
            and inst.opening_date >= cutoff_24mo
            and inst.opening_date <= five_twenty_four_as_of
            and not is_pc
        ):
            personal_cards_24mo.append(card.name)

        eff_sub = inst.sub_points if inst.sub_points is not None else (
            card.sub_points or 0
        )
        eff_sub_months = (
            inst.sub_months if inst.sub_months is not None else card.sub_months
        )
        eff_sub_min = (
            inst.sub_min_spend if inst.sub_min_spend is not None else card.sub_min_spend
        )

        sub_projected = inst.sub_projected_earn_date
        if (
            sub_projected is None
            and eff_sub
            and eff_sub_min
            and inst.opening_date > today
        ):
            sub_projected = projected_sub_earn_date(
                inst.opening_date, eff_sub_min, eff_sub_months, daily_rate
            )

        if not eff_sub:
            sub_status = "no_sub"
            sub_window_end = None
            sub_days_remaining = None
        elif sub_projected is not None and sub_projected <= today:
            sub_status = "earned"
            sub_window_end = None
            sub_days_remaining = None
        elif eff_sub_months:
            sub_window_end = add_months(inst.opening_date, eff_sub_months)
            remaining = (sub_window_end - today).days
            if remaining < 0:
                sub_status = "expired"
                sub_days_remaining = None
            else:
                sub_status = "pending"
                sub_days_remaining = remaining
        else:
            sub_status = "pending"
            sub_window_end = None
            sub_days_remaining = None

        recurrence = card.sub_recurrence_months
        next_eligible: Optional[date] = None
        if recurrence:
            effective_earned = (
                sub_projected if sub_projected and sub_projected <= today else None
            )
            if effective_earned:
                next_eligible = add_months(effective_earned, recurrence)
            else:
                next_eligible = add_months(inst.opening_date, recurrence)

        card_statuses.append(
            RoadmapCardStatus(
                wallet_card_id=inst.id,
                card_id=card.id,
                card_name=card.name,
                issuer_name=card.issuer.name,
                is_business=card.business,
                added_date=inst.opening_date,
                closed_date=inst.closed_date,
                is_active=is_active,
                sub_earned_date=None,
                sub_projected_earn_date=sub_projected,
                sub_status=sub_status,
                sub_window_end=sub_window_end,
                next_sub_eligible_date=next_eligible,
                sub_days_remaining=sub_days_remaining,
            )
        )

    rule_statuses: list[RoadmapRuleStatus] = []
    for rule in rules:
        is_long_horizon = rule.period_days >= 730
        rule_anchor = (
            five_twenty_four_as_of if is_long_horizon else today
        )
        cutoff = rule_anchor - timedelta(days=rule.period_days)
        counted: list[str] = []
        for inst in instances:
            card = inst.card
            if inst.opening_date < cutoff:
                continue
            if is_long_horizon and inst.opening_date > rule_anchor:
                continue
            if not rule.scope_all_issuers and card.issuer_id != rule.issuer_id:
                continue
            if rule.personal_only and card.business:
                continue
            # PCs don't count toward velocity rules.
            if inst.product_change_date is not None:
                continue
            counted.append(card.name)

        rule_statuses.append(
            RoadmapRuleStatus(
                rule_id=rule.id,
                rule_name=rule.rule_name,
                issuer_name=rule.issuer.name if rule.issuer else None,
                description=rule.description,
                max_count=rule.max_count,
                period_days=rule.period_days,
                current_count=len(counted),
                is_violated=len(counted) >= rule.max_count,
                personal_only=rule.personal_only,
                scope_all_issuers=rule.scope_all_issuers,
                counted_cards=counted,
            )
        )

    five_twenty_four_count = len(personal_cards_24mo)

    return RoadmapResponse(
        wallet_id=scenario.wallet_id,
        wallet_name=scenario.name,
        as_of_date=today,
        five_twenty_four_count=five_twenty_four_count,
        five_twenty_four_eligible=five_twenty_four_count < 5,
        personal_cards_24mo=personal_cards_24mo,
        rule_statuses=rule_statuses,
        cards=card_statuses,
    )
