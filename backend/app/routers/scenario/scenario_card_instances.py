"""Scenario-scoped (future) CardInstance CRUD."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth import get_current_user
from ...database import get_db
from ...models import User
from ...schemas import (
    CardInstanceRead,
    FutureCardCreate,
    FutureCardUpdate,
    card_instance_read,
)
from ...services import (
    CardInstanceService,
    ScenarioService,
    get_card_instance_service,
    get_scenario_service,
)

router = APIRouter(tags=["scenario-future-cards"])


@router.get(
    "/scenarios/{scenario_id}/future-cards",
    response_model=list[CardInstanceRead],
)
async def list_future_cards(
    scenario_id: int,
    user: User = Depends(get_current_user),
    scenario_service: ScenarioService = Depends(get_scenario_service),
    instance_service: CardInstanceService = Depends(get_card_instance_service),
):
    await scenario_service.get_user_scenario(scenario_id, user)
    futures = await instance_service.list_future(scenario_id)
    return [card_instance_read(i) for i in futures]


@router.post(
    "/scenarios/{scenario_id}/future-cards",
    response_model=CardInstanceRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_future_card(
    scenario_id: int,
    payload: FutureCardCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    scenario_service: ScenarioService = Depends(get_scenario_service),
    instance_service: CardInstanceService = Depends(get_card_instance_service),
):
    scenario = await scenario_service.get_user_scenario(scenario_id, user)
    inst = await instance_service.create_future(
        wallet_id=scenario.wallet_id,
        scenario_id=scenario_id,
        payload=payload,
    )
    await db.commit()
    inst = await instance_service.get_with_card(inst.id)
    return card_instance_read(inst)


@router.patch(
    "/scenarios/{scenario_id}/future-cards/{instance_id}",
    response_model=CardInstanceRead,
)
async def update_future_card(
    scenario_id: int,
    instance_id: int,
    payload: FutureCardUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    scenario_service: ScenarioService = Depends(get_scenario_service),
    instance_service: CardInstanceService = Depends(get_card_instance_service),
):
    await scenario_service.get_user_scenario(scenario_id, user)
    inst = await instance_service.get_with_card(instance_id)
    if inst.scenario_id != scenario_id:
        raise HTTPException(
            status_code=404,
            detail="Future card not found in this scenario",
        )
    await instance_service.update(inst, **payload.model_dump(exclude_unset=True))
    await db.commit()
    inst = await instance_service.get_with_card(instance_id)
    return card_instance_read(inst)


@router.delete(
    "/scenarios/{scenario_id}/future-cards/{instance_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_future_card(
    scenario_id: int,
    instance_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    scenario_service: ScenarioService = Depends(get_scenario_service),
    instance_service: CardInstanceService = Depends(get_card_instance_service),
):
    await scenario_service.get_user_scenario(scenario_id, user)
    inst = await instance_service.get_with_card(instance_id)
    if inst.scenario_id != scenario_id:
        raise HTTPException(
            status_code=404,
            detail="Future card not found in this scenario",
        )
    await instance_service.delete_future(inst)
    await db.commit()
