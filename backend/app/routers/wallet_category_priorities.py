"""Wallet card spend-category priority endpoints.

A category priority pins a single spend category to one wallet card. The
calculator forces that card to win allocation of the pinned category across
all allocation paths (simple and segmented). Uniqueness is enforced per
``(wallet_id, spend_category_id)`` at the model level, so the list endpoint
returns a wallet-wide view.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_db
from ..models import User
from ..schemas import (
    WalletCardCategoryPriorityRead,
    WalletCardCategoryPrioritySet,
)
from ..services import (
    WalletService,
    get_wallet_service,
    WalletCategoryPriorityService,
    get_wallet_category_priority_service,
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
    wallet_service: WalletService = Depends(get_wallet_service),
    priority_service: WalletCategoryPriorityService = Depends(
        get_wallet_category_priority_service
    ),
):
    """List all category priorities for a wallet."""
    await wallet_service.get_user_wallet(wallet_id, user)
    return await priority_service.list_for_wallet(wallet_id)


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
    wallet_service: WalletService = Depends(get_wallet_service),
    priority_service: WalletCategoryPriorityService = Depends(
        get_wallet_category_priority_service
    ),
):
    """Replace the full set of category priorities for this wallet card.

    Any categories claimed by *other* cards in the same wallet are a 409 —
    the caller (typically the modal) is expected to gray those out so the
    conflict should never reach the server.
    """
    await wallet_service.get_user_wallet(wallet_id, user)
    wc = await priority_service.get_wallet_card_or_404(wallet_id, card_id)

    requested_ids = set(payload.spend_category_ids)

    # Reject a request that tries to claim a category already pinned to a
    # different wallet card in this wallet.
    if requested_ids:
        conflicts = await priority_service.check_conflicts(
            wallet_id, wc.id, requested_ids
        )
        if conflicts:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Categories already pinned to another card in this wallet: "
                    f"{conflicts}"
                ),
            )

    result = await priority_service.replace_for_wallet_card(
        wallet_id, wc.id, requested_ids
    )
    await db.commit()
    return result


@router.delete(
    "/wallets/{wallet_id}/cards/{card_id}/category-priorities",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_wallet_card_category_priorities(
    wallet_id: int,
    card_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    priority_service: WalletCategoryPriorityService = Depends(
        get_wallet_category_priority_service
    ),
):
    """Delete all category priorities for a wallet card."""
    await wallet_service.get_user_wallet(wallet_id, user)
    wc = await priority_service.get_wallet_card_or_404(wallet_id, card_id)
    await priority_service.delete_for_wallet_card(wc.id)
    await db.commit()
