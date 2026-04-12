"""Wallet card spend-category priority endpoints.

A category priority pins a single spend category to one wallet card. The
calculator forces that card to win allocation of the pinned category across
all allocation paths (simple and segmented). Uniqueness is enforced per
``(wallet_id, spend_category_id)`` at the model level, so the list endpoint
returns a wallet-wide view.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..auth import get_current_user
from ..database import get_db
from ..helpers import get_user_wallet
from ..models import (
    User,
    WalletCard,
    WalletCardCategoryPriority,
)
from ..schemas import (
    WalletCardCategoryPriorityRead,
    WalletCardCategoryPrioritySet,
)

router = APIRouter()


@router.get(
    "/wallets/{wallet_id}/category-priorities",
    response_model=list[WalletCardCategoryPriorityRead],
)
async def list_wallet_category_priorities(
    wallet_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_user_wallet(wallet_id, user, db)
    result = await db.execute(
        select(WalletCardCategoryPriority)
        .options(selectinload(WalletCardCategoryPriority.spend_category))
        .where(WalletCardCategoryPriority.wallet_id == wallet_id)
    )
    return result.scalars().all()


@router.put(
    "/wallets/{wallet_id}/cards/{card_id}/category-priorities",
    response_model=list[WalletCardCategoryPriorityRead],
)
async def set_wallet_card_category_priorities(
    wallet_id: int,
    card_id: int,
    payload: WalletCardCategoryPrioritySet,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Replace the full set of category priorities for this wallet card.
    Any categories claimed by *other* cards in the same wallet are a 409 —
    the caller (typically the modal) is expected to gray those out so the
    conflict should never reach the server.
    """
    await get_user_wallet(wallet_id, user, db)
    wc = await db.execute(
        select(WalletCard).where(
            WalletCard.wallet_id == wallet_id,
            WalletCard.card_id == card_id,
        )
    )
    wc_row = wc.scalar_one_or_none()
    if not wc_row:
        raise HTTPException(status_code=404, detail="Wallet card not found")

    requested_ids = set(payload.spend_category_ids)

    # Reject a request that tries to claim a category already pinned to a
    # different wallet card in this wallet.
    if requested_ids:
        conflicts = await db.execute(
            select(WalletCardCategoryPriority)
            .where(
                WalletCardCategoryPriority.wallet_id == wallet_id,
                WalletCardCategoryPriority.spend_category_id.in_(requested_ids),
                WalletCardCategoryPriority.wallet_card_id != wc_row.id,
            )
        )
        conflict_rows = conflicts.scalars().all()
        if conflict_rows:
            conflict_ids = sorted({r.spend_category_id for r in conflict_rows})
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Categories already pinned to another card in this wallet: "
                    f"{conflict_ids}"
                ),
            )

    # Drop this card's existing rows and reinsert the requested set. A full
    # replace avoids per-row diffing and keeps the endpoint idempotent.
    existing = await db.execute(
        select(WalletCardCategoryPriority).where(
            WalletCardCategoryPriority.wallet_card_id == wc_row.id
        )
    )
    for row in existing.scalars().all():
        await db.delete(row)
    await db.flush()

    for cat_id in requested_ids:
        db.add(
            WalletCardCategoryPriority(
                wallet_id=wallet_id,
                wallet_card_id=wc_row.id,
                spend_category_id=cat_id,
            )
        )
    await db.commit()

    result = await db.execute(
        select(WalletCardCategoryPriority)
        .options(selectinload(WalletCardCategoryPriority.spend_category))
        .where(WalletCardCategoryPriority.wallet_card_id == wc_row.id)
    )
    return result.scalars().all()


@router.delete(
    "/wallets/{wallet_id}/cards/{card_id}/category-priorities",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_wallet_card_category_priorities(
    wallet_id: int,
    card_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_user_wallet(wallet_id, user, db)
    wc = await db.execute(
        select(WalletCard).where(
            WalletCard.wallet_id == wallet_id,
            WalletCard.card_id == card_id,
        )
    )
    wc_row = wc.scalar_one_or_none()
    if not wc_row:
        raise HTTPException(status_code=404, detail="Wallet card not found")
    existing = await db.execute(
        select(WalletCardCategoryPriority).where(
            WalletCardCategoryPriority.wallet_card_id == wc_row.id
        )
    )
    for row in existing.scalars().all():
        await db.delete(row)
    await db.commit()
