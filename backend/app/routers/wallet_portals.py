"""Wallet portal share endpoints."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_db
from ..models import User
from ..schemas import WalletPortalSharePayload, WalletPortalShareRead
from ..services import (
    WalletService,
    WalletPortalService,
    get_wallet_service,
    get_wallet_portal_service,
)

router = APIRouter()


@router.get(
    "/wallets/{wallet_id}/portal-shares",
    response_model=list[WalletPortalShareRead],
)
async def list_wallet_portal_shares(
    wallet_id: int,
    user: User = Depends(get_current_user),
    wallet_service: WalletService = Depends(get_wallet_service),
    portal_service: WalletPortalService = Depends(get_wallet_portal_service),
):
    await wallet_service.get_user_wallet(wallet_id, user)
    return await portal_service.list_for_wallet(wallet_id)


@router.put(
    "/wallets/{wallet_id}/portal-shares",
    response_model=WalletPortalShareRead,
)
async def upsert_wallet_portal_share(
    wallet_id: int,
    payload: WalletPortalSharePayload,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    portal_service: WalletPortalService = Depends(get_wallet_portal_service),
):
    await wallet_service.get_user_wallet(wallet_id, user)
    row = await portal_service.upsert_share(
        wallet_id, payload.travel_portal_id, payload.share
    )
    await db.commit()
    return await portal_service.get_share_with_portal(row.id)


@router.delete(
    "/wallets/{wallet_id}/portal-shares/{travel_portal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_wallet_portal_share(
    wallet_id: int,
    travel_portal_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    portal_service: WalletPortalService = Depends(get_wallet_portal_service),
):
    await wallet_service.get_user_wallet(wallet_id, user)
    await portal_service.delete_share(wallet_id, travel_portal_id)
    await db.commit()
