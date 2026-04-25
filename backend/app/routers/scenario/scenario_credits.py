"""Per-scenario credit override endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth import get_current_user
from ...database import get_db
from ...models import User
from ...schemas import (
    ScenarioCardCreditRead,
    ScenarioCardCreditUpsert,
)
from ...services import (
    CardInstanceService,
    ScenarioCardCreditService,
    ScenarioService,
    get_card_instance_service,
    get_scenario_card_credit_service,
    get_scenario_service,
)

router = APIRouter(tags=["scenario-credits"])


@router.get(
    "/scenarios/{scenario_id}/card-instances/{instance_id}/credits",
    response_model=list[ScenarioCardCreditRead],
)
async def list_instance_credits(
    scenario_id: int,
    instance_id: int,
    user: User = Depends(get_current_user),
    scenario_service: ScenarioService = Depends(get_scenario_service),
    credit_service: ScenarioCardCreditService = Depends(
        get_scenario_card_credit_service
    ),
):
    await scenario_service.get_user_scenario(scenario_id, user)
    rows = await credit_service.list_for_instance(scenario_id, instance_id)
    return [ScenarioCardCreditRead.model_validate(r) for r in rows]


@router.put(
    "/scenarios/{scenario_id}/card-instances/{instance_id}/credits/{library_credit_id}",
    response_model=ScenarioCardCreditRead,
)
async def upsert_instance_credit(
    scenario_id: int,
    instance_id: int,
    library_credit_id: int,
    payload: ScenarioCardCreditUpsert,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    scenario_service: ScenarioService = Depends(get_scenario_service),
    credit_service: ScenarioCardCreditService = Depends(
        get_scenario_card_credit_service
    ),
    instance_service: CardInstanceService = Depends(get_card_instance_service),
):
    scenario = await scenario_service.get_user_scenario(scenario_id, user)
    inst = await instance_service.get_with_card(instance_id)
    if inst.wallet_id != scenario.wallet_id:
        raise HTTPException(status_code=403, detail="Not your card instance")
    row = await credit_service.upsert(
        scenario_id, inst, library_credit_id, payload.value
    )
    await db.commit()
    row = await credit_service.get_with_library(row.id)
    return ScenarioCardCreditRead.model_validate(row)


@router.delete(
    "/scenarios/{scenario_id}/card-instances/{instance_id}/credits/{library_credit_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_instance_credit(
    scenario_id: int,
    instance_id: int,
    library_credit_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    scenario_service: ScenarioService = Depends(get_scenario_service),
    credit_service: ScenarioCardCreditService = Depends(
        get_scenario_card_credit_service
    ),
    instance_service: CardInstanceService = Depends(get_card_instance_service),
):
    scenario = await scenario_service.get_user_scenario(scenario_id, user)
    inst = await instance_service.get_with_card(instance_id)
    if inst.wallet_id != scenario.wallet_id:
        raise HTTPException(status_code=403, detail="Not your card instance")
    await credit_service.delete(scenario_id, instance_id, library_credit_id)
    await db.commit()
