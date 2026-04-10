"""Wallet results (EV calculation) and roadmap endpoints."""

from __future__ import annotations

import dataclasses
import json
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..calculator import calc_annual_allocated_spend, compute_wallet, plan_sub_targeting
from ..database import get_db
from ..date_utils import add_months
from ..db_helpers import (
    apply_wallet_card_group_selections,
    apply_wallet_card_multiplier_overrides,
    apply_wallet_card_overrides,
    apply_wallet_portal_shares,
    load_card_data,
    load_card_ids_by_portal,
    load_housing_category_names,
    load_wallet_card_credits,
    load_wallet_card_group_selections,
    load_wallet_card_multipliers,
    load_currency_defaults,
    load_currency_kinds,
    load_wallet_cpp_overrides,
    load_wallet_portal_shares,
    load_wallet_spend_items,
)
from ..helpers import (
    is_sub_earnable,
    months_in_half_open_interval,
    projected_sub_earn_date,
    sync_wallet_balances_from_currency_pts,
    wallet_404,
    wallet_to_schema,
    years_counted_from_total_months,
)
from ..models import Card, IssuerApplicationRule, Wallet, WalletCard
from ..schemas import (
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
    db: AsyncSession = Depends(get_db),
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
    result = await db.execute(
        select(Wallet)
        .options(selectinload(Wallet.wallet_cards))
        .where(Wallet.id == wallet_id)
    )
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise wallet_404(wallet_id)

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
        if wc.panel in ("in_wallet", "future")
        and wc.added_date < window_end
        and (wc.closed_date is None or wc.closed_date >= ref_date)
    ]

    _save_calc_window = "end" if end_date is not None else "duration"
    wallet.calc_start_date = ref_date
    wallet.calc_end_date = resp_end
    wallet.calc_duration_years = resp_dur_y
    wallet.calc_duration_months = resp_dur_m
    wallet.calc_window_mode = _save_calc_window

    if not active_wallet_cards:
        await sync_wallet_balances_from_currency_pts(db, wallet_id, {})
        await db.commit()
        return WalletResultResponseSchema(
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

    cpp_overrides = await load_wallet_cpp_overrides(db, wallet_id)
    all_cards = await load_card_data(db, cpp_overrides=cpp_overrides)
    card_ids_sel = {wc.card_id for wc in active_wallet_cards}
    lib_for_overrides = await db.execute(
        select(Card).where(Card.id.in_(card_ids_sel))
    )
    library_cards_by_id = {c.id: c for c in lib_for_overrides.scalars().all()}
    wallet_credit_rows = await load_wallet_card_credits(db, wallet_id)
    currency_defaults = await load_currency_defaults(db)
    currency_kinds = await load_currency_kinds(db)
    modified_cards = apply_wallet_card_overrides(
        all_cards, active_wallet_cards, library_cards_by_id, wallet_credit_rows,
        cpp_overrides=cpp_overrides, currency_defaults=currency_defaults,
        currency_kinds=currency_kinds,
    )
    wallet_multiplier_rows = await load_wallet_card_multipliers(db, wallet_id)
    modified_cards = apply_wallet_card_multiplier_overrides(modified_cards, wallet_multiplier_rows)
    group_selections = await load_wallet_card_group_selections(db, wallet_id)
    modified_cards = apply_wallet_card_group_selections(modified_cards, group_selections)
    portal_shares = await load_wallet_portal_shares(db, wallet_id)
    if portal_shares:
        card_ids_by_portal = await load_card_ids_by_portal(db)
        modified_cards = apply_wallet_portal_shares(
            modified_cards, portal_shares, card_ids_by_portal
        )
    selected_ids = card_ids_sel
    spend = await load_wallet_spend_items(db, wallet_id)
    if overrides:
        spend.update(overrides)
    housing_names = await load_housing_category_names(db)

    selected_card_data = [c for c in modified_cards if c.id in card_ids_sel]
    wcids = {c.currency.id for c in selected_card_data}

    in_wallet_panel_card_ids = {
        wc.card_id for wc in active_wallet_cards if wc.panel == "in_wallet"
    }
    sub_already_earned_ids = {wc.card_id for wc in active_wallet_cards if wc.sub_earned_date}

    def _has_sub_window(cd) -> bool:
        if cd.id in in_wallet_panel_card_ids:
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
    sub_plan = plan_sub_targeting(sub_cards_for_plan, spend, ref_date, wcids)

    plan_rates: dict[int, float] = {s.card_id: s.daily_spend_allocated for s in sub_plan.schedules}
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
        if wc.panel == "in_wallet":
            proj: Optional[date] = None
        else:
            lib = library_cards_by_id.get(wc.card_id)
            eff_min = wc.sub_min_spend if wc.sub_min_spend is not None else (lib.sub_min_spend if lib else None)
            eff_months = wc.sub_months if wc.sub_months is not None else (lib.sub_months if lib else None)
            eff_sub = wc.sub_points if wc.sub_points is not None else (lib.sub_points if lib else None)
            if wc.card_id in plan_earn_dates:
                proj = plan_earn_dates[wc.card_id]
            elif not eff_sub or not eff_min:
                proj = None
            else:
                daily_rate = card_daily_rates.get(wc.card_id, 0.0)
                proj = projected_sub_earn_date(wc.added_date, eff_min, eff_months, daily_rate)
        projected_dates[wc.card_id] = proj
        if wc.sub_projected_earn_date != proj:
            wc.sub_projected_earn_date = proj

    plan_card_ids = {s.card_id for s in sub_plan.schedules}
    modified_cards = [
        dataclasses.replace(
            c,
            sub_already_earned=(
                False if c.id in in_wallet_panel_card_ids else c.id in sub_already_earned_ids
            ),
            sub_earnable=(
                False
                if c.id in in_wallet_panel_card_ids
                else (
                    True
                    if c.id in sub_already_earned_ids
                    else (
                        (c.id in plan_card_ids)
                        if c.id in sub_priority_card_ids
                        else is_sub_earnable(c.sub_min_spend, c.sub_months, card_daily_rates.get(c.id, 0.0))
                    )
                )
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
    )

    # Merge secondary currency points into the balance sync map
    merged_pts_by_id = dict(wallet_result.currency_pts_by_id)
    for cid, pts in wallet_result.secondary_currency_pts_by_id.items():
        merged_pts_by_id[cid] = merged_pts_by_id.get(cid, 0.0) + pts
    await sync_wallet_balances_from_currency_pts(
        db, wallet_id, merged_pts_by_id
    )
    await db.commit()

    return WalletResultResponseSchema(
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
        wallet=wallet_to_schema(wallet_result),
    )


@router.get(
    "/wallets/{wallet_id}/roadmap",
    response_model=RoadmapResponse,
)
async def wallet_roadmap(
    wallet_id: int,
    as_of_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Compute roadmap status for the wallet: 5/24 count, per-card SUB status and
    next eligibility dates, and any issuer velocity rule violations.
    """
    result = await db.execute(
        select(Wallet)
        .options(
            selectinload(Wallet.wallet_cards).selectinload(WalletCard.card).selectinload(Card.issuer),
        )
        .where(Wallet.id == wallet_id)
    )
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise wallet_404(wallet_id)

    today = as_of_date or date.today()

    rules_result = await db.execute(
        select(IssuerApplicationRule)
        .options(selectinload(IssuerApplicationRule.issuer))
    )
    rules = rules_result.scalars().all()

    roadmap_spend = await load_wallet_spend_items(db, wallet_id)
    roadmap_daily_rate = sum(roadmap_spend.values()) / 365.0

    card_statuses: list[RoadmapCardStatus] = []
    personal_cards_24mo: list[str] = []
    cutoff_24mo = today - timedelta(days=730)

    in_wallet_cards = [
        wc for wc in wallet.wallet_cards if wc.panel in ("in_wallet", "future")
    ]

    for wc in in_wallet_cards:
        card = wc.card
        is_active = wc.closed_date is None

        if not card.business and wc.added_date >= cutoff_24mo and wc.acquisition_type == "opened":
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
            and wc.panel != "in_wallet"
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
        cutoff = today - timedelta(days=rule.period_days)
        counted: list[str] = []
        for wc in in_wallet_cards:
            card = wc.card
            if wc.added_date < cutoff:
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
