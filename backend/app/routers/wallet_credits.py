"""Wallet card credit override endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..auth import get_current_user
from ..database import get_db
from ..helpers import get_user_wallet
from ..models import Credit, User, WalletCard, WalletCardCredit
from ..schemas import WalletCardCreditRead, WalletCardCreditUpsert

router = APIRouter(tags=["wallet-credits"])


@router.get(
    "/wallets/{wallet_id}/cards/{card_id}/credits",
    response_model=list[WalletCardCreditRead],
)
async def list_wallet_card_credits(
    wallet_id: int,
    card_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List credit overrides for a card in this wallet."""
    await get_user_wallet(wallet_id, user, db)
    wc_result = await db.execute(
        select(WalletCard).where(
            WalletCard.wallet_id == wallet_id,
            WalletCard.card_id == card_id,
        )
    )
    wc = wc_result.scalar_one_or_none()
    if not wc:
        raise HTTPException(status_code=404, detail="Wallet card not found")

    result = await db.execute(
        select(WalletCardCredit)
        .options(selectinload(WalletCardCredit.library_credit))
        .where(WalletCardCredit.wallet_card_id == wc.id)
        .order_by(WalletCardCredit.library_credit_id)
    )
    return list(result.scalars().all())


@router.put(
    "/wallets/{wallet_id}/cards/{card_id}/credits/{library_credit_id}",
    response_model=WalletCardCreditRead,
)
async def upsert_wallet_card_credit(
    wallet_id: int,
    card_id: int,
    library_credit_id: int,
    payload: WalletCardCreditUpsert,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Attach a standardized credit to this wallet card with a user-set value."""
    await get_user_wallet(wallet_id, user, db)
    wc_result = await db.execute(
        select(WalletCard).where(
            WalletCard.wallet_id == wallet_id,
            WalletCard.card_id == card_id,
        )
    )
    wc = wc_result.scalar_one_or_none()
    if not wc:
        raise HTTPException(status_code=404, detail="Wallet card not found")

    lib_result = await db.execute(
        select(Credit).where(Credit.id == library_credit_id)
    )
    lib_credit = lib_result.scalar_one_or_none()
    if not lib_credit:
        raise HTTPException(
            status_code=404,
            detail=f"Credit id={library_credit_id} not found in library",
        )

    existing = await db.execute(
        select(WalletCardCredit).where(
            WalletCardCredit.wallet_card_id == wc.id,
            WalletCardCredit.library_credit_id == library_credit_id,
        )
    )
    row = existing.scalar_one_or_none()
    if row:
        row.value = payload.value
    else:
        row = WalletCardCredit(
            wallet_card_id=wc.id,
            library_credit_id=library_credit_id,
            value=payload.value,
        )
        db.add(row)
    await db.commit()
    await db.refresh(row)
    res = await db.execute(
        select(WalletCardCredit)
        .options(selectinload(WalletCardCredit.library_credit))
        .where(WalletCardCredit.id == row.id)
    )
    return res.scalar_one()


@router.delete(
    "/wallets/{wallet_id}/cards/{card_id}/credits/{library_credit_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_wallet_card_credit(
    wallet_id: int,
    card_id: int,
    library_credit_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Detach a standardized credit from this wallet card."""
    await get_user_wallet(wallet_id, user, db)
    wc_result = await db.execute(
        select(WalletCard).where(
            WalletCard.wallet_id == wallet_id,
            WalletCard.card_id == card_id,
        )
    )
    wc = wc_result.scalar_one_or_none()
    if not wc:
        raise HTTPException(status_code=404, detail="Wallet card not found")

    result = await db.execute(
        select(WalletCardCredit).where(
            WalletCardCredit.wallet_card_id == wc.id,
            WalletCardCredit.library_credit_id == library_credit_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No credit override found")
    await db.delete(row)
    await db.commit()
