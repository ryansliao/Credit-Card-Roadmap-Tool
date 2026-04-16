"""Wallet card multiplier override endpoints."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_db
from ..models import User
from ..schemas import WalletCardMultiplierRead, WalletCardMultiplierUpsert
from ..services import (
    WalletService,
    WalletCardOverrideService,
    get_wallet_service,
    get_wallet_card_override_service,
)

router = APIRouter(tags=["wallet-multipliers"])


@router.get(
    "/wallets/{wallet_id}/card-multipliers",
    response_model=list[WalletCardMultiplierRead],
)
async def list_wallet_card_multipliers(
    wallet_id: int,
    user: User = Depends(get_current_user),
    wallet_service: WalletService = Depends(get_wallet_service),
    override_service: WalletCardOverrideService = Depends(get_wallet_card_override_service),
):
    """List all wallet-level multiplier overrides."""
    await wallet_service.get_user_wallet(wallet_id, user)
    return await override_service.list_multipliers(wallet_id)


@router.put(
    "/wallets/{wallet_id}/cards/{card_id}/multipliers/{category_id}",
    response_model=WalletCardMultiplierRead,
)
async def upsert_wallet_card_multiplier(
    wallet_id: int,
    card_id: int,
    category_id: int,
    payload: WalletCardMultiplierUpsert,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    override_service: WalletCardOverrideService = Depends(get_wallet_card_override_service),
):
    """Set or update a multiplier override for a card/category in this wallet."""
    await wallet_service.get_user_wallet(wallet_id, user)
    row = await override_service.upsert_multiplier(
        wallet_id, card_id, category_id, payload.multiplier
    )
    await db.commit()
    await db.refresh(row)
    return await override_service.get_multiplier_with_category(row.id)


@router.delete(
    "/wallets/{wallet_id}/cards/{card_id}/multipliers/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_wallet_card_multiplier(
    wallet_id: int,
    card_id: int,
    category_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    override_service: WalletCardOverrideService = Depends(get_wallet_card_override_service),
):
    """Remove a multiplier override (reverts to library value)."""
    await wallet_service.get_user_wallet(wallet_id, user)
    await override_service.delete_multiplier(wallet_id, card_id, category_id)
    await db.commit()
