"""Scenario category-priority pin endpoints.

Each pin forces a specific spend_category to flow to a specific
card_instance in this scenario. At most one card per category per
scenario."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth import get_current_user
from ...database import get_db
from ...models import User
from ...schemas import (
    ScenarioCardCategoryPriorityRead,
    ScenarioCardCategoryPrioritySet,
)
from ...services import (
    CardInstanceService,
    ScenarioCategoryPriorityService,
    ScenarioService,
    get_card_instance_service,
    get_scenario_category_priority_service,
    get_scenario_service,
)

router = APIRouter()


@router.get(
    "/scenarios/{scenario_id}/category-priorities",
    response_model=list[ScenarioCardCategoryPriorityRead],
)
async def list_scenario_category_priorities(
    scenario_id: int,
    user: User = Depends(get_current_user),
    scenario_service: ScenarioService = Depends(get_scenario_service),
    priority_service: ScenarioCategoryPriorityService = Depends(
        get_scenario_category_priority_service
    ),
):
    await scenario_service.get_user_scenario(scenario_id, user)
    rows = await priority_service.list_for_scenario(scenario_id)
    return [ScenarioCardCategoryPriorityRead.model_validate(r) for r in rows]


@router.put(
    "/scenarios/{scenario_id}/card-instances/{instance_id}/category-priorities",
    response_model=list[ScenarioCardCategoryPriorityRead],
)
async def set_instance_category_priorities(
    scenario_id: int,
    instance_id: int,
    payload: ScenarioCardCategoryPrioritySet,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    scenario_service: ScenarioService = Depends(get_scenario_service),
    priority_service: ScenarioCategoryPriorityService = Depends(
        get_scenario_category_priority_service
    ),
    instance_service: CardInstanceService = Depends(get_card_instance_service),
):
    """Replace the full category-priority set for a card instance in this
    scenario. Empty list clears all pins for the card."""
    scenario = await scenario_service.get_user_scenario(scenario_id, user)
    inst = await instance_service.get_with_card(instance_id)
    if inst.wallet_id != scenario.wallet_id:
        raise HTTPException(status_code=403, detail="Not your card instance")
    rows = await priority_service.set_for_instance(
        scenario_id, inst, payload.spend_category_ids
    )
    await db.commit()
    return [ScenarioCardCategoryPriorityRead.model_validate(r) for r in rows]


@router.delete(
    "/scenarios/{scenario_id}/card-instances/{instance_id}/category-priorities",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def clear_instance_category_priorities(
    scenario_id: int,
    instance_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    scenario_service: ScenarioService = Depends(get_scenario_service),
    priority_service: ScenarioCategoryPriorityService = Depends(
        get_scenario_category_priority_service
    ),
    instance_service: CardInstanceService = Depends(get_card_instance_service),
):
    scenario = await scenario_service.get_user_scenario(scenario_id, user)
    inst = await instance_service.get_with_card(instance_id)
    if inst.wallet_id != scenario.wallet_id:
        raise HTTPException(status_code=403, detail="Not your card instance")
    await priority_service.set_for_instance(scenario_id, inst, [])
    await db.commit()
