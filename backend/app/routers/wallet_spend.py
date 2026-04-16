"""Wallet spend item endpoints."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_db
from ..models import User
from ..schemas import (
    WalletSpendItemCreate,
    WalletSpendItemRead,
    WalletSpendItemUpdate,
)
from ..services import (
    WalletService,
    WalletSpendService,
    get_wallet_service,
    get_wallet_spend_service,
)

router = APIRouter(tags=["wallet-spend"])


@router.get(
    "/wallets/{wallet_id}/spend-items",
    response_model=list[WalletSpendItemRead],
)
async def list_wallet_spend_items(
    wallet_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    spend_service: WalletSpendService = Depends(get_wallet_spend_service),
):
    """List wallet spend items. Auto-creates the 'All Other' item if missing."""
    await wallet_service.get_user_wallet(wallet_id, user)
    await spend_service.ensure_all_other_item(wallet_id)
    await db.commit()
    return await spend_service.list_for_wallet(wallet_id)


@router.post(
    "/wallets/{wallet_id}/spend-items",
    response_model=WalletSpendItemRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_wallet_spend_item(
    wallet_id: int,
    payload: WalletSpendItemCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    spend_service: WalletSpendService = Depends(get_wallet_spend_service),
):
    """Add a spend item to a wallet for a given app spend category."""
    await wallet_service.get_user_wallet(wallet_id, user)
    item = await spend_service.create(
        wallet_id=wallet_id,
        spend_category_id=payload.spend_category_id,
        amount=payload.amount,
    )
    await db.commit()
    return await spend_service.get_with_opts(item.id)


@router.put(
    "/wallets/{wallet_id}/spend-items/{item_id}",
    response_model=WalletSpendItemRead,
)
async def update_wallet_spend_item(
    wallet_id: int,
    item_id: int,
    payload: WalletSpendItemUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    spend_service: WalletSpendService = Depends(get_wallet_spend_service),
):
    """Update the annual spend amount for a wallet spend item."""
    await wallet_service.get_user_wallet(wallet_id, user)
    item = await spend_service.get_for_wallet_or_404(wallet_id, item_id)
    await spend_service.update_amount(item, payload.amount)
    await db.commit()
    return await spend_service.get_with_opts(item_id)


@router.delete(
    "/wallets/{wallet_id}/spend-items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_wallet_spend_item(
    wallet_id: int,
    item_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    spend_service: WalletSpendService = Depends(get_wallet_spend_service),
):
    """Remove a spend item from a wallet. The 'All Other' item cannot be deleted."""
    await wallet_service.get_user_wallet(wallet_id, user)
    item = await spend_service.get_for_wallet_or_404(wallet_id, item_id)
    await spend_service.delete(item)
    await db.commit()
