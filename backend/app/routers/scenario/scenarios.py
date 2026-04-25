"""Scenario CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth import get_current_user
from ...database import get_db
from ...models import User
from ...schemas import (
    ScenarioCreate,
    ScenarioRead,
    ScenarioSummary,
    ScenarioUpdate,
    scenario_read,
    scenario_summary,
)
from ...services import (
    ScenarioService,
    WalletService,
    get_scenario_service,
    get_wallet_service,
)

router = APIRouter(tags=["scenarios"])


@router.get("/scenarios", response_model=list[ScenarioSummary])
async def list_scenarios(
    user: User = Depends(get_current_user),
    wallet_service: WalletService = Depends(get_wallet_service),
    scenario_service: ScenarioService = Depends(get_scenario_service),
):
    """List the user's scenarios. Empty list if no wallet exists yet."""
    wallet = await wallet_service.get_for_user(user.id)
    if wallet is None:
        return []
    scenarios = await scenario_service.list_for_wallet(wallet.id)
    return [scenario_summary(s) for s in scenarios]


@router.post(
    "/scenarios",
    response_model=ScenarioRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_scenario(
    payload: ScenarioCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    scenario_service: ScenarioService = Depends(get_scenario_service),
):
    wallet = await wallet_service.get_for_user(user.id)
    if wallet is None:
        raise HTTPException(
            status_code=404,
            detail="No wallet exists yet — fetch /wallet first to auto-create",
        )
    if payload.copy_from_scenario_id is not None:
        # Verify ownership of the source scenario
        await scenario_service.get_user_scenario(payload.copy_from_scenario_id, user)
    scenario = await scenario_service.create(
        wallet_id=wallet.id,
        name=payload.name,
        description=payload.description,
        copy_from_scenario_id=payload.copy_from_scenario_id,
    )
    await db.commit()
    return scenario_read(scenario)


@router.get("/scenarios/{scenario_id}", response_model=ScenarioRead)
async def get_scenario(
    scenario_id: int,
    user: User = Depends(get_current_user),
    scenario_service: ScenarioService = Depends(get_scenario_service),
):
    scenario = await scenario_service.get_user_scenario(scenario_id, user)
    return scenario_read(scenario)


@router.patch("/scenarios/{scenario_id}", response_model=ScenarioRead)
async def update_scenario(
    scenario_id: int,
    payload: ScenarioUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    scenario_service: ScenarioService = Depends(get_scenario_service),
):
    scenario = await scenario_service.get_user_scenario(scenario_id, user)
    await scenario_service.update(
        scenario, **payload.model_dump(exclude_none=True)
    )
    await db.commit()
    return scenario_read(scenario)


@router.delete(
    "/scenarios/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_scenario(
    scenario_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    scenario_service: ScenarioService = Depends(get_scenario_service),
):
    """Delete a scenario. Auto-spawns a fresh empty default if this was the
    last scenario in the wallet — wallets always have at least one."""
    scenario = await scenario_service.get_user_scenario(scenario_id, user)
    await scenario_service.delete(scenario)
    await db.commit()


@router.post(
    "/scenarios/{scenario_id}/make-default",
    response_model=ScenarioRead,
)
async def make_default_scenario(
    scenario_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    scenario_service: ScenarioService = Depends(get_scenario_service),
):
    scenario = await scenario_service.get_user_scenario(scenario_id, user)
    await scenario_service.set_default(scenario)
    await db.commit()
    return scenario_read(scenario)
