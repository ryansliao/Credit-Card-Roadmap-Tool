"""Scenario CPP override endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth import get_current_user
from ...database import get_db
from ...models import Currency, User
from ...schemas import (
    CurrencyRead,
    ScenarioCurrencyCppSet,
)
from ...services import (
    ScenarioCurrencyService,
    ScenarioService,
    get_scenario_currency_service,
    get_scenario_service,
)

router = APIRouter(tags=["scenario-cpp"])


@router.get(
    "/scenarios/{scenario_id}/currencies",
    response_model=list[CurrencyRead],
)
async def list_scenario_currencies_with_cpp(
    scenario_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    scenario_service: ScenarioService = Depends(get_scenario_service),
    currency_service: ScenarioCurrencyService = Depends(
        get_scenario_currency_service
    ),
):
    """Return all currencies with the scenario's CPP overrides applied."""
    await scenario_service.get_user_scenario(scenario_id, user)
    cpp_rows = await currency_service.list_cpp(scenario_id)
    cpp_by_currency: dict[int, float] = {
        r.currency_id: r.cents_per_point for r in cpp_rows
    }
    from sqlalchemy import select

    result = await db.execute(select(Currency))
    out = []
    for currency in result.scalars().all():
        schema = CurrencyRead.model_validate(currency)
        override = cpp_by_currency.get(currency.id)
        schema.user_cents_per_point = (
            override if override is not None else currency.cents_per_point
        )
        out.append(schema)
    return out


@router.put(
    "/scenarios/{scenario_id}/currencies/{currency_id}/cpp",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def set_scenario_cpp(
    scenario_id: int,
    currency_id: int,
    payload: ScenarioCurrencyCppSet,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    scenario_service: ScenarioService = Depends(get_scenario_service),
    currency_service: ScenarioCurrencyService = Depends(
        get_scenario_currency_service
    ),
):
    await scenario_service.get_user_scenario(scenario_id, user)
    await currency_service.upsert_cpp(
        scenario_id, currency_id, payload.cents_per_point
    )
    await db.commit()


@router.delete(
    "/scenarios/{scenario_id}/currencies/{currency_id}/cpp",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_scenario_cpp(
    scenario_id: int,
    currency_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    scenario_service: ScenarioService = Depends(get_scenario_service),
    currency_service: ScenarioCurrencyService = Depends(
        get_scenario_currency_service
    ),
):
    await scenario_service.get_user_scenario(scenario_id, user)
    await currency_service.delete_cpp(scenario_id, currency_id)
    await db.commit()
