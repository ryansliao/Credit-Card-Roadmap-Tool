"""Wallet portal share endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..auth import get_current_user
from ..database import get_db
from ..helpers import get_user_wallet
from ..models import TravelPortal, User, Wallet, WalletPortalShare
from ..schemas import WalletPortalSharePayload, WalletPortalShareRead

router = APIRouter()


@router.get(
    "/wallets/{wallet_id}/portal-shares",
    response_model=list[WalletPortalShareRead],
)
async def list_wallet_portal_shares(
    wallet_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_user_wallet(wallet_id, user, db)
    result = await db.execute(
        select(WalletPortalShare)
        .options(selectinload(WalletPortalShare.travel_portal))
        .where(WalletPortalShare.wallet_id == wallet_id)
        .order_by(WalletPortalShare.travel_portal_id)
    )
    return result.scalars().all()


@router.put(
    "/wallets/{wallet_id}/portal-shares",
    response_model=WalletPortalShareRead,
)
async def upsert_wallet_portal_share(
    wallet_id: int,
    payload: WalletPortalSharePayload,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_user_wallet(wallet_id, user, db)
    portal_row = await db.execute(
        select(TravelPortal).where(TravelPortal.id == payload.travel_portal_id)
    )
    if not portal_row.scalar_one_or_none():
        raise HTTPException(
            status_code=404,
            detail=f"Travel portal id={payload.travel_portal_id} not found",
        )
    existing = await db.execute(
        select(WalletPortalShare).where(
            WalletPortalShare.wallet_id == wallet_id,
            WalletPortalShare.travel_portal_id == payload.travel_portal_id,
        )
    )
    row = existing.scalar_one_or_none()
    if row is None:
        row = WalletPortalShare(
            wallet_id=wallet_id,
            travel_portal_id=payload.travel_portal_id,
            share=payload.share,
        )
        db.add(row)
    else:
        row.share = payload.share
    await db.commit()
    result = await db.execute(
        select(WalletPortalShare)
        .options(selectinload(WalletPortalShare.travel_portal))
        .where(WalletPortalShare.id == row.id)
    )
    return result.scalar_one()


@router.delete(
    "/wallets/{wallet_id}/portal-shares/{travel_portal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_wallet_portal_share(
    wallet_id: int,
    travel_portal_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_user_wallet(wallet_id, user, db)
    result = await db.execute(
        select(WalletPortalShare).where(
            WalletPortalShare.wallet_id == wallet_id,
            WalletPortalShare.travel_portal_id == travel_portal_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Portal share not found")
    await db.delete(row)
    await db.commit()
