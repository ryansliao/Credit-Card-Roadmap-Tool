"""Wallet spend item endpoints. Spend lives on the wallet (one set per
user, no scenario variation)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth import get_current_user
from ...database import get_db
from ...models import User
from ...schemas import (
    WalletSpendItemCreate,
    WalletSpendItemRead,
    WalletSpendItemUpdate,
)
from ...services import (
    WalletService,
    WalletSpendService,
    get_wallet_service,
    get_wallet_spend_service,
)

router = APIRouter(tags=["wallet-spend"])


async def _resolve_wallet_id(
    user: User,
    wallet_service: WalletService,
    spend_service: WalletSpendService,
    db: AsyncSession,
) -> int:
    wallet = await wallet_service.get_for_user(user.id)
    if wallet is None:
        raise HTTPException(
            status_code=404,
            detail="No wallet exists yet — fetch /wallet first to auto-create",
        )
    await spend_service.ensure_all_user_categories(wallet.id)
    await db.commit()
    return wallet.id


@router.get("/wallet/spend-items", response_model=list[WalletSpendItemRead])
async def list_my_spend_items(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    spend_service: WalletSpendService = Depends(get_wallet_spend_service),
):
    wallet_id = await _resolve_wallet_id(user, wallet_service, spend_service, db)
    return await spend_service.list_for_wallet(wallet_id)


@router.post(
    "/wallet/spend-items",
    response_model=WalletSpendItemRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_my_spend_item(
    payload: WalletSpendItemCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    spend_service: WalletSpendService = Depends(get_wallet_spend_service),
):
    wallet_id = await _resolve_wallet_id(user, wallet_service, spend_service, db)
    item = await spend_service.create(
        wallet_id=wallet_id,
        user_spend_category_id=payload.user_spend_category_id,
        amount=payload.amount,
    )
    await db.commit()
    return await spend_service.get_with_opts(item.id)


@router.put(
    "/wallet/spend-items/{item_id}",
    response_model=WalletSpendItemRead,
)
async def update_my_spend_item(
    item_id: int,
    payload: WalletSpendItemUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    spend_service: WalletSpendService = Depends(get_wallet_spend_service),
):
    wallet_id = await _resolve_wallet_id(user, wallet_service, spend_service, db)
    item = await spend_service.get_for_wallet_or_404(wallet_id, item_id)
    await spend_service.update_amount(item, payload.amount)
    await db.commit()
    return await spend_service.get_with_opts(item_id)


@router.delete(
    "/wallet/spend-items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_my_spend_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    spend_service: WalletSpendService = Depends(get_wallet_spend_service),
):
    wallet_id = await _resolve_wallet_id(user, wallet_service, spend_service, db)
    item = await spend_service.get_for_wallet_or_404(wallet_id, item_id)
    await spend_service.delete(item)
    await db.commit()
