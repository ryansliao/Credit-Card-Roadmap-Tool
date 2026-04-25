"""Scenario card overlay endpoints — per-scenario hypothetical edits to
owned card instances."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth import get_current_user
from ...database import get_db
from ...models import User
from ...schemas import ScenarioCardOverlayRead, ScenarioCardOverlayUpsert
from ...services import (
    ScenarioCardOverlayService,
    ScenarioService,
    get_scenario_card_overlay_service,
    get_scenario_service,
)

router = APIRouter(tags=["scenario-overlays"])


@router.get(
    "/scenarios/{scenario_id}/overlays",
    response_model=list[ScenarioCardOverlayRead],
)
async def list_overlays(
    scenario_id: int,
    user: User = Depends(get_current_user),
    scenario_service: ScenarioService = Depends(get_scenario_service),
    overlay_service: ScenarioCardOverlayService = Depends(
        get_scenario_card_overlay_service
    ),
):
    await scenario_service.get_user_scenario(scenario_id, user)
    rows = await overlay_service.list_for_scenario(scenario_id)
    return [ScenarioCardOverlayRead.model_validate(r) for r in rows]


@router.put(
    "/scenarios/{scenario_id}/overlays/{card_instance_id}",
    response_model=ScenarioCardOverlayRead,
)
async def upsert_overlay(
    scenario_id: int,
    card_instance_id: int,
    payload: ScenarioCardOverlayUpsert,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    scenario_service: ScenarioService = Depends(get_scenario_service),
    overlay_service: ScenarioCardOverlayService = Depends(
        get_scenario_card_overlay_service
    ),
):
    """Upsert overlay fields for an owned card. Fields explicitly set to
    null in the payload clear that field's overlay (revert to base)."""
    await scenario_service.get_user_scenario(scenario_id, user)
    fields = payload.model_dump(exclude_unset=True)
    row = await overlay_service.upsert(scenario_id, card_instance_id, **fields)
    await db.commit()
    return ScenarioCardOverlayRead.model_validate(row)


@router.delete(
    "/scenarios/{scenario_id}/overlays/{card_instance_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def clear_overlay(
    scenario_id: int,
    card_instance_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    scenario_service: ScenarioService = Depends(get_scenario_service),
    overlay_service: ScenarioCardOverlayService = Depends(
        get_scenario_card_overlay_service
    ),
):
    await scenario_service.get_user_scenario(scenario_id, user)
    await overlay_service.clear(scenario_id, card_instance_id)
    await db.commit()
