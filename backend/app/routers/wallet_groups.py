"""Wallet card group category selection endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..auth import get_current_user
from ..database import get_db
from ..helpers import get_user_wallet
from ..models import (
    Card,
    CardCategoryMultiplier,
    CardMultiplierGroup,
    RotatingCategory,
    User,
    WalletCard,
    WalletCardGroupSelection,
)
from ..schemas import WalletCardGroupSelectionRead, WalletCardGroupSelectionSet

router = APIRouter()


@router.get(
    "/wallets/{wallet_id}/cards/{card_id}/group-selections",
    response_model=list[WalletCardGroupSelectionRead],
)
async def list_wallet_card_group_selections(
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
    result = await db.execute(
        select(WalletCardGroupSelection)
        .options(selectinload(WalletCardGroupSelection.spend_category))
        .where(WalletCardGroupSelection.wallet_card_id == wc_row.id)
    )
    return result.scalars().all()


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

    grp = await db.execute(
        select(CardMultiplierGroup)
        .options(
            selectinload(CardMultiplierGroup.categories).selectinload(
                CardCategoryMultiplier.spend_category
            ),
            selectinload(CardMultiplierGroup.card)
            .selectinload(Card.rotating_categories)
            .selectinload(RotatingCategory.spend_category),
        )
        .where(
            CardMultiplierGroup.id == group_id,
            CardMultiplierGroup.card_id == card_id,
        )
    )
    grp_row = grp.scalar_one_or_none()
    if not grp_row:
        raise HTTPException(status_code=404, detail="Multiplier group not found for this card")

    existing = await db.execute(
        select(WalletCardGroupSelection).where(
            WalletCardGroupSelection.wallet_card_id == wc_row.id,
            WalletCardGroupSelection.multiplier_group_id == group_id,
        )
    )
    for row in existing.scalars().all():
        await db.delete(row)
    await db.flush()

    if not payload.spend_category_ids:
        await db.commit()
        return []

    top_n = grp_row.top_n_categories
    if top_n and len(payload.spend_category_ids) != top_n:
        raise HTTPException(
            status_code=422,
            detail=f"Must select exactly {top_n} categories, got {len(payload.spend_category_ids)}",
        )

    valid_cat_ids = {c.category_id for c in grp_row.categories}
    for cat_id in payload.spend_category_ids:
        if cat_id not in valid_cat_ids:
            raise HTTPException(
                status_code=422,
                detail=f"Category {cat_id} is not in this multiplier group",
            )

    for cat_id in payload.spend_category_ids:
        db.add(
            WalletCardGroupSelection(
                wallet_card_id=wc_row.id,
                multiplier_group_id=group_id,
                spend_category_id=cat_id,
            )
        )
    await db.commit()

    result = await db.execute(
        select(WalletCardGroupSelection)
        .options(selectinload(WalletCardGroupSelection.spend_category))
        .where(
            WalletCardGroupSelection.wallet_card_id == wc_row.id,
            WalletCardGroupSelection.multiplier_group_id == group_id,
        )
    )
    return result.scalars().all()


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
        select(WalletCardGroupSelection).where(
            WalletCardGroupSelection.wallet_card_id == wc_row.id,
            WalletCardGroupSelection.multiplier_group_id == group_id,
        )
    )
    for row in existing.scalars().all():
        await db.delete(row)
    await db.commit()
