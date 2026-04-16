"""Wallet CRUD and wallet card management endpoints."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_db
from ..helpers import wc_read
from ..models import User
from ..schemas import (
    WalletCardCreate,
    WalletCardRead,
    WalletCardUpdate,
    WalletCreate,
    WalletRead,
    WalletUpdate,
)
from ..services import (
    WalletService,
    WalletCurrencyService,
    WalletSpendService,
    get_wallet_service,
    get_wallet_currency_service,
    get_wallet_spend_service,
)

router = APIRouter(tags=["wallets"])


@router.get("/wallets", response_model=list[WalletRead])
async def list_wallets(
    user: User = Depends(get_current_user),
    wallet_service: WalletService = Depends(get_wallet_service),
):
    """List wallets for the authenticated user."""
    wallets = await wallet_service.list_for_user(user.id)
    out = []
    for w in wallets:
        read = WalletRead.model_validate(w)
        read.wallet_cards = [wc_read(wc_item, wc_item.card) for wc_item in w.wallet_cards]
        out.append(read)
    return out


@router.post(
    "/wallets",
    response_model=WalletRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_wallet(
    payload: WalletCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    spend_service: WalletSpendService = Depends(get_wallet_spend_service),
):
    wallet = await wallet_service.create(
        user_id=user.id,
        name=payload.name,
        description=payload.description,
        as_of_date=payload.as_of_date,
    )
    await spend_service.ensure_all_other_item(wallet.id)
    await db.commit()
    await db.refresh(wallet)
    return WalletRead(
        id=wallet.id,
        user_id=wallet.user_id,
        name=wallet.name,
        description=wallet.description,
        as_of_date=wallet.as_of_date,
        wallet_cards=[],
    )


@router.get("/wallets/{wallet_id}", response_model=WalletRead)
async def get_wallet(
    wallet_id: int,
    user: User = Depends(get_current_user),
    wallet_service: WalletService = Depends(get_wallet_service),
):
    await wallet_service.get_user_wallet(wallet_id, user)
    wallet = await wallet_service.get_with_cards(wallet_id)
    read = WalletRead.model_validate(wallet)
    read.wallet_cards = [wc_read(wc_item, wc_item.card) for wc_item in wallet.wallet_cards]
    return read


@router.patch("/wallets/{wallet_id}", response_model=WalletRead)
async def update_wallet(
    wallet_id: int,
    payload: WalletUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
):
    await wallet_service.get_user_wallet(wallet_id, user)
    wallet = await wallet_service.get_with_cards(wallet_id)
    await wallet_service.update(wallet, **payload.model_dump(exclude_none=True))
    await db.commit()
    await db.refresh(wallet)
    read = WalletRead.model_validate(wallet)
    read.wallet_cards = [wc_read(wc_item, wc_item.card) for wc_item in wallet.wallet_cards]
    return read


@router.delete(
    "/wallets/{wallet_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_wallet(
    wallet_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
):
    wallet = await wallet_service.get_user_wallet(wallet_id, user)
    await wallet_service.delete(wallet)
    await db.commit()


@router.post(
    "/wallets/{wallet_id}/cards",
    response_model=WalletCardRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_card_to_wallet(
    wallet_id: int,
    payload: WalletCardCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    currency_service: WalletCurrencyService = Depends(get_wallet_currency_service),
):
    await wallet_service.get_user_wallet(wallet_id, user)
    wc_obj = await wallet_service.add_card_to_wallet(wallet_id, payload)

    await currency_service.ensure_earning_currency_rows(wallet_id)

    await db.commit()
    await db.refresh(wc_obj, attribute_names=["credit_overrides_rows"])

    card = await wallet_service.get_card_or_404(wc_obj.card_id)
    return wc_read(wc_obj, card)


@router.patch(
    "/wallets/{wallet_id}/cards/{card_id}",
    response_model=WalletCardRead,
)
async def update_wallet_card(
    wallet_id: int,
    card_id: int,
    payload: WalletCardUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
):
    """
    Partially update a wallet card. Supports updating SUB overrides, years_counted,
    sub_earned_date (mark when the SUB was earned), and closed_date (mark card as closed).
    """
    await wallet_service.get_user_wallet(wallet_id, user)
    wc_obj = await wallet_service.get_wallet_card_or_404(wallet_id, card_id)

    await wallet_service.update_wallet_card(
        wc_obj, **payload.model_dump(exclude_unset=True)
    )

    await db.commit()
    await db.refresh(wc_obj, attribute_names=["credit_overrides_rows"])

    card = await wallet_service.get_card_or_404(wc_obj.card_id)
    return wc_read(wc_obj, card)


@router.delete(
    "/wallets/{wallet_id}/cards/{card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_card_from_wallet(
    wallet_id: int,
    card_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    currency_service: WalletCurrencyService = Depends(get_wallet_currency_service),
):
    await wallet_service.get_user_wallet(wallet_id, user)
    wc_obj = await wallet_service.get_wallet_card_or_404(wallet_id, card_id)
    await wallet_service.remove_card_from_wallet(wc_obj)

    # Clean up orphaned currency balance rows
    remaining_currency_ids = await currency_service.effective_earn_currency_ids(wallet_id)
    await currency_service.delete_orphan_balances(wallet_id, remaining_currency_ids)

    await db.commit()
