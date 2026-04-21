"""Wallet results (EV calculation) and roadmap endpoints."""

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
from ...card_data_transforms import (
    apply_wallet_card_category_priorities,
    apply_wallet_card_multiplier_overrides,
    apply_wallet_card_overrides,
    apply_wallet_portal_shares,
)
from ...date_utils import (
    add_months,
    is_sub_earnable,
    months_in_half_open_interval,
    projected_sub_earn_date,
    years_counted_from_total_months,
)
from ...schemas import wallet_to_schema
from ...services import (
    WalletService,
    CalculatorDataService,
    IssuerService,
    get_wallet_service,
    get_calculator_data_service,
    get_issuer_service,
)
from ...models import User
from ...schemas import (
    RoadmapCardStatus,
    RoadmapResponse,
    RoadmapRuleStatus,
    WalletResultResponseSchema,
    WalletResultSchema,
)

router = APIRouter(tags=["wallets"])


@router.get(
    "/wallets/{wallet_id}/results",
    response_model=WalletResultResponseSchema,
)
async def wallet_results(
    wallet_id: int,
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
    wallet_service: WalletService = Depends(get_wallet_service),
    calc_data_service: CalculatorDataService = Depends(get_calculator_data_service),
):
    """
    Compute wallet results (effective fees, points, credits) and SUB opportunity cost.
    """
    overrides: dict[str, float] = {}
    if spend_overrides:
        try:
            overrides = json.loads(spend_overrides)
        except (json.JSONDecodeError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="spend_overrides must be valid JSON (e.g. '{\"Dining\": 5000}')",
            )
    await wallet_service.get_user_wallet(wallet_id, user)
    wallet = await wallet_service.get_with_cards(wallet_id)

    if start_date is not None and reference_date is not None and start_date != reference_date:
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

    active_wallet_cards = [
        wc
        for wc in wallet.wallet_cards
        if wc.is_enabled
        and wc.added_date < window_end
        and (wc.closed_date is None or wc.closed_date >= ref_date)
    ]

    _save_calc_window = "end" if end_date is not None else "duration"
    await wallet_service.save_calc_window(
        wallet,
        start=ref_date,
        end=resp_end,
        duration_years=resp_dur_y,
        duration_months=resp_dur_m,
        window_mode=_save_calc_window,
    )

    if not active_wallet_cards:
        empty_response = WalletResultResponseSchema(
            wallet_id=wallet_id,
            wallet_name=wallet.name,
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
                total_annual_pts=0,
                total_cash_reward_dollars=0,
                total_reward_value_usd=0,
            ),
        )
        await wallet_service.save_last_calc_snapshot(
            wallet, empty_response.model_dump_json()
        )
        await db.commit()
        return empty_response

    cpp_overrides = await calc_data_service.load_wallet_cpp_overrides(wallet_id)
    all_cards = await calc_data_service.load_card_data(cpp_overrides=cpp_overrides)
    card_ids_sel = {wc.card_id for wc in active_wallet_cards}
    library_cards_by_id = await calc_data_service.load_cards_by_ids(card_ids_sel)
    wallet_credit_rows = await calc_data_service.load_wallet_card_credits(wallet_id)
    currency_defaults = await calc_data_service.load_currency_defaults()
    currency_kinds = await calc_data_service.load_currency_kinds()
    modified_cards = apply_wallet_card_overrides(
        all_cards, active_wallet_cards, wallet_credit_rows,
        cpp_overrides=cpp_overrides, currency_defaults=currency_defaults,
        currency_kinds=currency_kinds,
    )
    wallet_multiplier_rows = await calc_data_service.load_wallet_card_multipliers(wallet_id)
    modified_cards = apply_wallet_card_multiplier_overrides(modified_cards, wallet_multiplier_rows)
    category_priorities = await calc_data_service.load_wallet_card_category_priorities(wallet_id)
    modified_cards = apply_wallet_card_category_priorities(modified_cards, category_priorities)
    portal_shares = await calc_data_service.load_wallet_portal_shares(wallet_id)
    if portal_shares:
        card_ids_by_portal = await calc_data_service.load_card_ids_by_portal()
        modified_cards = apply_wallet_portal_shares(
            modified_cards, portal_shares, card_ids_by_portal
        )
    selected_ids = card_ids_sel
    spend = await calc_data_service.load_wallet_spend_items(wallet_id)
    if overrides:
        spend.update(overrides)
    housing_names = await calc_data_service.load_housing_category_names()
    foreign_eligible_names = await calc_data_service.load_foreign_eligible_category_names()

    selected_card_data = [c for c in modified_cards if c.id in card_ids_sel]
    wcids = {c.currency.id for c in selected_card_data}

    # Cards already in the user's wallet at the calc start: SUB windows for
    # these are not projected (they would have been earned before the window,
    # or are marked via sub_earned_date).
    in_wallet_now_card_ids = {
        wc.card_id for wc in active_wallet_cards if wc.added_date <= ref_date
    }
    sub_already_earned_ids = {wc.card_id for wc in active_wallet_cards if wc.sub_earned_date}

    def _has_sub_window(cd) -> bool:
        if cd.id in in_wallet_now_card_ids:
            return False
        if cd.id in sub_already_earned_ids:
            return False
        if not cd.sub_points or not cd.sub_min_spend or not cd.wallet_added_date:
            return False
        if cd.sub_months:
            window_end_dt = add_months(cd.wallet_added_date, cd.sub_months)
            if ref_date >= window_end_dt:
                return False
        return True

    sub_priority_card_ids = {
        cd.id for cd in selected_card_data
        if _has_sub_window(cd)
        and (
            not cd.sub_min_spend
            or calc_annual_allocated_spend(cd, selected_card_data, spend, wcids) < cd.sub_min_spend
        )
    }

    sub_cards_for_plan = [cd for cd in selected_card_data if _has_sub_window(cd)]
    sub_plan = plan_sub_targeting(sub_cards_for_plan, spend, ref_date, wcids, housing_category_names=housing_names)

    plan_rates: dict[int, float] = {s.card_id: s.daily_spend_allocated for s in sub_plan.schedules}
    # Total wallet daily spend: used for SUB-priority cards because during
    # their priority window ALL wallet spend flows to them, not just their
    # normal allocated share.
    total_daily_spend = sum(spend.values()) / 365.0
    card_daily_rates: dict[int, float] = {}
    for cd in selected_card_data:
        if cd.id in plan_rates:
            card_daily_rates[cd.id] = plan_rates[cd.id]
        else:
            allocated = calc_annual_allocated_spend(cd, selected_card_data, spend, wcids, sub_priority_card_ids)
            card_daily_rates[cd.id] = allocated / 365.0

    plan_earn_dates: dict[int, date] = {s.card_id: s.projected_earn_date for s in sub_plan.schedules}
    projected_dates: dict[int, Optional[date]] = {}
    for wc in active_wallet_cards:
        if wc.added_date <= ref_date:
            proj: Optional[date] = None
        else:
            lib = library_cards_by_id.get(wc.card_id)
            eff_min = wc.sub_min_spend if wc.sub_min_spend is not None else (lib.sub_min_spend if lib else None)
            eff_months = wc.sub_months if wc.sub_months is not None else (lib.sub_months if lib else None)
            eff_sub = wc.sub_points if wc.sub_points is not None else (lib.sub_points if lib else None)
            if not eff_sub or not eff_min:
                proj = None
            elif wc.card_id in sub_priority_card_ids:
                # During the SUB priority window the LP routes ALL wallet spend
                # to this card, so use the total daily spend rate — not the
                # card's normal allocated share or the planner's estimate, both
                # of which severely under-count how fast the minimum is hit.
                proj = projected_sub_earn_date(wc.added_date, eff_min, eff_months, total_daily_spend)
            elif wc.card_id in plan_earn_dates:
                proj = plan_earn_dates[wc.card_id]
            else:
                daily_rate = card_daily_rates.get(wc.card_id, 0.0)
                proj = projected_sub_earn_date(wc.added_date, eff_min, eff_months, daily_rate)
        projected_dates[wc.card_id] = proj
        await wallet_service.set_projected_sub_earn_date(wc, proj)

    plan_card_ids = {s.card_id for s in sub_plan.schedules}
    modified_cards = [
        dataclasses.replace(
            c,
            sub_already_earned=c.id in sub_already_earned_ids,
            # In-wallet-now cards' SUBs are history, not projection value —
            # they're either already in the user's balance or were missed.
            # Only future cards with a feasible SUB window contribute to
            # projected balance/EAF. Feasibility uses total wallet daily spend
            # so this matches the roadmap's projected-earn-date view.
            sub_earnable=(
                False
                if c.id in in_wallet_now_card_ids
                else is_sub_earnable(c.sub_min_spend, c.sub_months, total_daily_spend)
            ),
            sub_projected_earn_date=projected_dates.get(c.id, c.sub_projected_earn_date),
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
        housing_category_names=housing_names,
        foreign_spend_pct=wallet.foreign_spend_percent or 0.0,
        foreign_eligible_categories=foreign_eligible_names,
    )

    photo_slugs = {card_id: card.photo_slug for card_id, card in library_cards_by_id.items()}

    response = WalletResultResponseSchema(
        wallet_id=wallet_id,
        wallet_name=wallet.name,
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
    await wallet_service.save_last_calc_snapshot(wallet, response.model_dump_json())
    await db.commit()

    return response


@router.get(
    "/wallets/{wallet_id}/results/latest",
    response_model=Optional[WalletResultResponseSchema],
)
async def wallet_results_latest(
    wallet_id: int,
    user: User = Depends(get_current_user),
    wallet_service: WalletService = Depends(get_wallet_service),
):
    """
    Return the last persisted /wallets/{id}/results response for this wallet,
    or null if no calculation has been run yet. Used by the Roadmap Tool to
    re-hydrate the prior calculation on page load without re-running the
    full EV computation.
    """
    wallet = await wallet_service.get_user_wallet(wallet_id, user)
    if not wallet.last_calc_snapshot:
        return None
    try:
        return WalletResultResponseSchema.model_validate_json(wallet.last_calc_snapshot)
    except Exception:
        # Snapshot schema drift (older cached payload). Treat as absent rather
        # than 500; the user can press Calculate to refresh.
        return None


@router.get(
    "/wallets/{wallet_id}/roadmap",
    response_model=RoadmapResponse,
)
async def wallet_roadmap(
    wallet_id: int,
    as_of_date: Optional[date] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    calc_data_service: CalculatorDataService = Depends(get_calculator_data_service),
    issuer_service: IssuerService = Depends(get_issuer_service),
):
    """
    Compute roadmap status for the wallet: 5/24 count, per-card SUB status and
    next eligibility dates, and any issuer velocity rule violations.
    """
    await wallet_service.get_user_wallet(wallet_id, user)
    wallet = await wallet_service.get_with_cards(wallet_id)

    today = as_of_date or date.today()

    # 5/24 is projected to the added_date of the latest opened future card
    # so the status reflects what the wallet looks like right after the
    # last planned acquisition. If there are no future opened cards to
    # project to, fall back to today. Disabled cards are excluded.
    future_opened_dates = [
        wc.added_date
        for wc in wallet.wallet_cards
        if wc.is_enabled
        and wc.added_date > today
        and wc.acquisition_type == "opened"
    ]
    five_twenty_four_as_of = max(future_opened_dates) if future_opened_dates else today

    rules = await issuer_service.list_application_rules()

    roadmap_spend = await calc_data_service.load_wallet_spend_items(wallet_id)
    roadmap_daily_rate = sum(roadmap_spend.values()) / 365.0

    card_statuses: list[RoadmapCardStatus] = []
    personal_cards_24mo: list[str] = []
    cutoff_24mo = five_twenty_four_as_of - timedelta(days=730)

    # Roadmap includes every card the user considers part of their plan
    # (wallet cards and future acquisitions). Disabled cards are excluded —
    # they're just being held for re-enablement.
    in_wallet_cards = [wc for wc in wallet.wallet_cards if wc.is_enabled]

    for wc in in_wallet_cards:
        card = wc.card
        is_active = wc.closed_date is None

        if (
            not card.business
            and wc.added_date >= cutoff_24mo
            and wc.added_date <= five_twenty_four_as_of
            and wc.acquisition_type == "opened"
        ):
            personal_cards_24mo.append(card.name)

        eff_sub = wc.sub_points if wc.sub_points is not None else (card.sub_points or 0)
        eff_sub_months = wc.sub_months if wc.sub_months is not None else card.sub_months
        eff_sub_min = wc.sub_min_spend if wc.sub_min_spend is not None else card.sub_min_spend

        sub_projected = wc.sub_projected_earn_date
        if (
            sub_projected is None
            and eff_sub
            and eff_sub_min
            and not wc.sub_earned_date
            and wc.added_date > today
        ):
            sub_projected = projected_sub_earn_date(wc.added_date, eff_sub_min, eff_sub_months, roadmap_daily_rate)

        if not eff_sub:
            sub_status = "no_sub"
            sub_window_end = None
            sub_days_remaining = None
        elif wc.sub_earned_date:
            sub_status = "earned"
            sub_window_end = None
            sub_days_remaining = None
        elif sub_projected is not None and sub_projected <= today:
            sub_status = "earned"
            sub_window_end = None
            sub_days_remaining = None
        elif eff_sub_months:
            sub_window_end = add_months(wc.added_date, eff_sub_months)
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
            effective_earned = wc.sub_earned_date or (sub_projected if sub_projected and sub_projected <= today else None)
            if effective_earned:
                next_eligible = add_months(effective_earned, recurrence)
            else:
                next_eligible = add_months(wc.added_date, recurrence)

        card_statuses.append(
            RoadmapCardStatus(
                wallet_card_id=wc.id,
                card_id=card.id,
                card_name=card.name,
                issuer_name=card.issuer.name,
                is_business=card.business,
                added_date=wc.added_date,
                closed_date=wc.closed_date,
                is_active=is_active,
                sub_earned_date=wc.sub_earned_date,
                sub_projected_earn_date=sub_projected,
                sub_status=sub_status,
                sub_window_end=sub_window_end,
                next_sub_eligible_date=next_eligible,
                sub_days_remaining=sub_days_remaining,
            )
        )

    rule_statuses: list[RoadmapRuleStatus] = []
    for rule in rules:
        # Long-horizon velocity rules (24+ months) are anchored to the
        # latest planned future card acquisition so the status reflects
        # post-acquisition state, with a matching upper bound so cards
        # added later don't count. Short cooldowns stay anchored to today
        # with no upper bound, so the existing warning modal still
        # surfaces future-dated 1/90 / 1/8 / 2/65 / 2/30 conflicts within
        # the plan.
        is_long_horizon = rule.period_days >= 730
        rule_anchor = five_twenty_four_as_of if is_long_horizon else today
        cutoff = rule_anchor - timedelta(days=rule.period_days)
        counted: list[str] = []
        for wc in in_wallet_cards:
            card = wc.card
            if wc.added_date < cutoff:
                continue
            if is_long_horizon and wc.added_date > rule_anchor:
                continue
            if not rule.scope_all_issuers and card.issuer_id != rule.issuer_id:
                continue
            if rule.personal_only and card.business:
                continue
            if wc.acquisition_type == "product_change":
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
        wallet_id=wallet_id,
        wallet_name=wallet.name,
        as_of_date=today,
        five_twenty_four_count=five_twenty_four_count,
        five_twenty_four_eligible=five_twenty_four_count < 5,
        personal_cards_24mo=personal_cards_24mo,
        rule_statuses=rule_statuses,
        cards=card_statuses,
    )
