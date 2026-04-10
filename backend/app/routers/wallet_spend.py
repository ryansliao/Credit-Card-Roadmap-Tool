"""Wallet spend item endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..db_helpers import ensure_all_other_wallet_spend_item
from ..helpers import load_spend_item_opts, wallet_404
from ..models import (
    SpendCategory,
    Wallet,
    WalletSpendItem,
)
from ..schemas import (
    WalletSpendItemCreate,
    WalletSpendItemRead,
    WalletSpendItemUpdate,
)

router = APIRouter(tags=["wallet-spend"])


@router.get(
    "/wallets/{wallet_id}/spend-items",
    response_model=list[WalletSpendItemRead],
)
async def list_wallet_spend_items(
    wallet_id: int,
    db: AsyncSession = Depends(get_db),
):
    """List wallet spend items. Auto-creates the 'All Other' item if missing."""
    wallet_result = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
    if not wallet_result.scalar_one_or_none():
        raise wallet_404(wallet_id)
    await ensure_all_other_wallet_spend_item(db, wallet_id)
    await db.commit()
    result = await db.execute(
        select(WalletSpendItem)
        .options(*load_spend_item_opts())
        .where(WalletSpendItem.wallet_id == wallet_id)
        .join(WalletSpendItem.spend_category)
        .order_by(WalletSpendItem.amount.desc(), SpendCategory.category)
    )
    return result.scalars().all()


@router.post(
    "/wallets/{wallet_id}/spend-items",
    response_model=WalletSpendItemRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_wallet_spend_item(
    wallet_id: int,
    payload: WalletSpendItemCreate,
    db: AsyncSession = Depends(get_db),
):
    """Add a spend item to a wallet for a given app spend category."""
    wallet_result = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
    if not wallet_result.scalar_one_or_none():
        raise wallet_404(wallet_id)

    sc_result = await db.execute(
        select(SpendCategory).where(SpendCategory.id == payload.spend_category_id)
    )
    sc = sc_result.scalar_one_or_none()
    if not sc:
        raise HTTPException(status_code=422, detail=f"SpendCategory id={payload.spend_category_id} not found")
    if sc.is_system:
        raise HTTPException(status_code=403, detail=f"'{sc.category}' is a system category; update its amount via PUT instead")

    existing = await db.execute(
        select(WalletSpendItem).where(
            WalletSpendItem.wallet_id == wallet_id,
            WalletSpendItem.spend_category_id == payload.spend_category_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"A spend item for '{sc.category}' already exists in this wallet")

    item = WalletSpendItem(
        wallet_id=wallet_id,
        spend_category_id=payload.spend_category_id,
        amount=payload.amount,
    )
    db.add(item)
    await db.commit()
    result = await db.execute(
        select(WalletSpendItem)
        .options(*load_spend_item_opts())
        .where(WalletSpendItem.id == item.id)
    )
    return result.scalar_one()


@router.put(
    "/wallets/{wallet_id}/spend-items/{item_id}",
    response_model=WalletSpendItemRead,
)
async def update_wallet_spend_item(
    wallet_id: int,
    item_id: int,
    payload: WalletSpendItemUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update the annual spend amount for a wallet spend item."""
    result = await db.execute(
        select(WalletSpendItem).where(
            WalletSpendItem.id == item_id,
            WalletSpendItem.wallet_id == wallet_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail=f"Spend item {item_id} not found")
    item.amount = payload.amount
    await db.commit()
    result = await db.execute(
        select(WalletSpendItem)
        .options(*load_spend_item_opts())
        .where(WalletSpendItem.id == item_id)
    )
    return result.scalar_one()


@router.delete(
    "/wallets/{wallet_id}/spend-items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_wallet_spend_item(
    wallet_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Remove a spend item from a wallet. The 'All Other' item cannot be deleted."""
    result = await db.execute(
        select(WalletSpendItem)
        .options(selectinload(WalletSpendItem.spend_category))
        .where(WalletSpendItem.id == item_id, WalletSpendItem.wallet_id == wallet_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail=f"Spend item {item_id} not found")
    if item.spend_category and item.spend_category.is_system:
        raise HTTPException(
            status_code=403,
            detail=f"The '{item.spend_category.category}' item cannot be deleted",
        )
    await db.delete(item)
    await db.commit()
