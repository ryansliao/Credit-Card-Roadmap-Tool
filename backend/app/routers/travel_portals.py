"""Travel portal endpoints (read + admin CRUD)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import (
    AdminCreateTravelPortalPayload,
    AdminUpdateTravelPortalPayload,
    TravelPortalRead,
)
from ..services import TravelPortalService, get_travel_portal_service

router = APIRouter()


@router.get("/travel-portals", response_model=list[TravelPortalRead])
async def list_travel_portals(
    portal_service: TravelPortalService = Depends(get_travel_portal_service),
):
    return await portal_service.list_all_with_cards()


@router.post(
    "/admin/travel-portals",
    response_model=TravelPortalRead,
    status_code=status.HTTP_201_CREATED,
    tags=["admin"],
)
async def admin_create_travel_portal(
    payload: AdminCreateTravelPortalPayload,
    db: AsyncSession = Depends(get_db),
    portal_service: TravelPortalService = Depends(get_travel_portal_service),
):
    portal = await portal_service.create(
        name=payload.name,
        card_ids=payload.card_ids,
    )
    await db.commit()
    return await portal_service.get_with_cards(portal.id)


@router.put(
    "/admin/travel-portals/{portal_id}",
    response_model=TravelPortalRead,
    tags=["admin"],
)
async def admin_update_travel_portal(
    portal_id: int,
    payload: AdminUpdateTravelPortalPayload,
    db: AsyncSession = Depends(get_db),
    portal_service: TravelPortalService = Depends(get_travel_portal_service),
):
    portal = await portal_service.get_or_404(portal_id)
    await portal_service.update(
        portal,
        name=payload.name,
        card_ids=payload.card_ids,
    )
    await db.commit()
    return await portal_service.get_with_cards(portal_id)


@router.delete(
    "/admin/travel-portals/{portal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["admin"],
)
async def admin_delete_travel_portal(
    portal_id: int,
    db: AsyncSession = Depends(get_db),
    portal_service: TravelPortalService = Depends(get_travel_portal_service),
):
    portal = await portal_service.get_or_404(portal_id)
    await portal_service.delete(portal)
    await db.commit()
