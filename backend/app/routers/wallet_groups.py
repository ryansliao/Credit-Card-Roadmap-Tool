"""Wallet card group category selection endpoints."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_db
from ..models import User
from ..schemas import WalletCardGroupSelectionRead, WalletCardGroupSelectionSet
from ..services import (
    WalletService,
    WalletCardOverrideService,
    get_wallet_service,
    get_wallet_card_override_service,
)

router = APIRouter()


@router.get(
    "/wallets/{wallet_id}/cards/{card_id}/group-selections",
    response_model=list[WalletCardGroupSelectionRead],
)
async def list_wallet_card_group_selections(
    wallet_id: int,
    card_id: int,
    user: User = Depends(get_current_user),
    wallet_service: WalletService = Depends(get_wallet_service),
    override_service: WalletCardOverrideService = Depends(get_wallet_card_override_service),
):
    await wallet_service.get_user_wallet(wallet_id, user)
    wc = await override_service.get_wallet_card_or_404(wallet_id, card_id)
    return await override_service.list_group_selections(wc.id)


@router.put(
    "/wallets/{wallet_id}/cards/{card_id}/group-selections/{group_id}",
    response_model=list[WalletCardGroupSelectionRead],
)
async def set_wallet_card_group_selections(
    wallet_id: int,
    card_id: int,
    group_id: int,
    payload: WalletCardGroupSelectionSet,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    override_service: WalletCardOverrideService = Depends(get_wallet_card_override_service),
):
    await wallet_service.get_user_wallet(wallet_id, user)
    wc = await override_service.get_wallet_card_or_404(wallet_id, card_id)
    selections = await override_service.set_group_selections(
        wallet_card_id=wc.id,
        group_id=group_id,
        card_id=card_id,
        spend_category_ids=payload.spend_category_ids,
    )
    await db.commit()
    return selections


@router.delete(
    "/wallets/{wallet_id}/cards/{card_id}/group-selections/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_wallet_card_group_selections(
    wallet_id: int,
    card_id: int,
    group_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    override_service: WalletCardOverrideService = Depends(get_wallet_card_override_service),
):
    await wallet_service.get_user_wallet(wallet_id, user)
    wc = await override_service.get_wallet_card_or_404(wallet_id, card_id)
    await override_service.delete_group_selections(wc.id, group_id)
    await db.commit()
