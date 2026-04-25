"""Wallet CRUD and wallet card management endpoints."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth import get_current_user
from ...database import get_db
from ...models import User
from ...schemas import (
    WalletCardCreate,
    WalletCardRead,
    WalletCardUpdate,
    WalletCreate,
    WalletRead,
    WalletSummary,
    WalletUpdate,
    wallet_read,
    wc_read,
)
from ...services import (
    WalletService,
    WalletSpendService,
    get_wallet_service,
    get_wallet_spend_service,
)

router = APIRouter(tags=["wallets"])


@router.get("/wallets", response_model=list[WalletSummary])
async def list_my_wallets(
    user: User = Depends(get_current_user),
    wallet_service: WalletService = Depends(get_wallet_service),
):
    """List the authenticated user's wallets (summary fields only)."""
    wallets = await wallet_service.list_summaries_for_user(user.id)
    return [WalletSummary.model_validate(w) for w in wallets]


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
    """Create a new wallet for the authenticated user."""
    wallet = await wallet_service.create(
        user_id=user.id,
        name=payload.name,
        description=payload.description,
    )
    await spend_service.ensure_all_user_categories(wallet.id)
    await db.commit()
    wallet = await wallet_service.get_with_cards(wallet.id)
    return wallet_read(wallet)


@router.get("/wallet", response_model=WalletRead)
async def get_my_wallet(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    spend_service: WalletSpendService = Depends(get_wallet_spend_service),
):
    """Get the authenticated user's wallet, creating one if none exists."""
    wallet = await wallet_service.get_for_user(user.id)
    if not wallet:
        wallet = await wallet_service.create(
            user_id=user.id,
            name="My Wallet",
            description=None,
        )
        await spend_service.ensure_all_user_categories(wallet.id)
        await db.commit()
        wallet = await wallet_service.get_with_cards(wallet.id)
    return wallet_read(wallet)


@router.get("/wallets/{wallet_id}", response_model=WalletRead)
async def get_wallet(
    wallet_id: int,
    user: User = Depends(get_current_user),
    wallet_service: WalletService = Depends(get_wallet_service),
):
    await wallet_service.get_user_wallet(wallet_id, user)
    wallet = await wallet_service.get_with_cards(wallet_id)
    return wallet_read(wallet)


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
    wallet = await wallet_service.get_with_cards(wallet_id)
    return wallet_read(wallet)


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
):
    await wallet_service.get_user_wallet(wallet_id, user)
    wc_obj = await wallet_service.add_card_to_wallet(wallet_id, payload)

    await db.commit()
    wc_obj = await wallet_service.get_wallet_card_with_credits(wc_obj.id)

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
    and closed_date (mark card as closed).
    """
    await wallet_service.get_user_wallet(wallet_id, user)
    wc_obj = await wallet_service.get_wallet_card_or_404(wallet_id, card_id)

    await wallet_service.update_wallet_card(
        wc_obj, **payload.model_dump(exclude_unset=True)
    )

    await db.commit()
    wc_obj = await wallet_service.get_wallet_card_with_credits(wc_obj.id)

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
):
    await wallet_service.get_user_wallet(wallet_id, user)
    wc_obj = await wallet_service.get_wallet_card_or_404(wallet_id, card_id)
    await wallet_service.remove_card_from_wallet(wc_obj)

    await db.commit()
