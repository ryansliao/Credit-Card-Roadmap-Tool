"""Wallet card credit override endpoints."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth import get_current_user
from ...database import get_db
from ...models import User
from ...schemas import WalletCardCreditRead, WalletCardCreditUpsert
from ...services import (
    WalletService,
    WalletCardOverrideService,
    get_wallet_service,
    get_wallet_card_override_service,
)

router = APIRouter(tags=["wallet-credits"])


@router.get(
    "/wallets/{wallet_id}/cards/{card_id}/credits",
    response_model=list[WalletCardCreditRead],
)
async def list_wallet_card_credits(
    wallet_id: int,
    card_id: int,
    user: User = Depends(get_current_user),
    wallet_service: WalletService = Depends(get_wallet_service),
    override_service: WalletCardOverrideService = Depends(get_wallet_card_override_service),
):
    """List credit overrides for a card in this wallet."""
    await wallet_service.get_user_wallet(wallet_id, user)
    wc = await wallet_service.get_wallet_card_or_404(wallet_id, card_id)
    return await override_service.list_credits(wc.id)


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
    wallet_service: WalletService = Depends(get_wallet_service),
    override_service: WalletCardOverrideService = Depends(get_wallet_card_override_service),
):
    """Attach a standardized credit to this wallet card with a user-set value."""
    await wallet_service.get_user_wallet(wallet_id, user)
    wc = await wallet_service.get_wallet_card_or_404(wallet_id, card_id)
    row = await override_service.upsert_credit(wc.id, library_credit_id, payload.value)
    await db.commit()
    await db.refresh(row)
    return await override_service.get_credit_with_library(row.id)


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
    wallet_service: WalletService = Depends(get_wallet_service),
    override_service: WalletCardOverrideService = Depends(get_wallet_card_override_service),
):
    """Detach a standardized credit from this wallet card."""
    await wallet_service.get_user_wallet(wallet_id, user)
    wc = await wallet_service.get_wallet_card_or_404(wallet_id, card_id)
    await override_service.delete_credit(wc.id, library_credit_id)
    await db.commit()
