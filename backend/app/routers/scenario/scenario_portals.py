"""Scenario portal share endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth import get_current_user
from ...database import get_db
from ...models import User
from ...schemas import ScenarioPortalShareRead
from ...services import (
    ScenarioPortalService,
    ScenarioService,
    get_scenario_portal_service,
    get_scenario_service,
)

router = APIRouter()


class _PortalShareUpsert:
    """Body schema lives in schemas/scenario_currency.py via
    ScenarioPortalShareSet — but the legacy router accepted
    {travel_portal_id, share}. Keep the same body shape for parity."""


from pydantic import BaseModel, Field


class ScenarioPortalSharePayload(BaseModel):
    travel_portal_id: int
    share: float = Field(..., ge=0, le=1)


@router.get(
    "/scenarios/{scenario_id}/portal-shares",
    response_model=list[ScenarioPortalShareRead],
)
async def list_scenario_portal_shares(
    scenario_id: int,
    user: User = Depends(get_current_user),
    scenario_service: ScenarioService = Depends(get_scenario_service),
    portal_service: ScenarioPortalService = Depends(get_scenario_portal_service),
):
    await scenario_service.get_user_scenario(scenario_id, user)
    rows = await portal_service.list_for_scenario(scenario_id)
    return [ScenarioPortalShareRead.model_validate(r) for r in rows]


@router.put(
    "/scenarios/{scenario_id}/portal-shares",
    response_model=ScenarioPortalShareRead,
)
async def upsert_scenario_portal_share(
    scenario_id: int,
    payload: ScenarioPortalSharePayload,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    scenario_service: ScenarioService = Depends(get_scenario_service),
    portal_service: ScenarioPortalService = Depends(get_scenario_portal_service),
):
    await scenario_service.get_user_scenario(scenario_id, user)
    row = await portal_service.upsert(
        scenario_id, payload.travel_portal_id, payload.share
    )
    await db.commit()
    return ScenarioPortalShareRead.model_validate(row)


@router.delete(
    "/scenarios/{scenario_id}/portal-shares/{travel_portal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_scenario_portal_share(
    scenario_id: int,
    travel_portal_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    scenario_service: ScenarioService = Depends(get_scenario_service),
    portal_service: ScenarioPortalService = Depends(get_scenario_portal_service),
):
    await scenario_service.get_user_scenario(scenario_id, user)
    await portal_service.delete(scenario_id, travel_portal_id)
    await db.commit()
