"""Per-wallet UserSpendCategoryMapping weight overrides.

Three endpoints under /wallet/category-weights/{user_category_id}:
  - GET    : current effective weights (defaults + overrides + effective)
  - PUT    : save new weights (server normalizes to sum=1)
  - DELETE : reset to defaults (delete all override rows for the pair)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth import get_current_user
from ...database import get_db
from ...models import User
from ...schemas import (
    WalletCategoryWeightsRead,
    WalletCategoryWeightsWrite,
)
from ...services import (
    WalletCategoryWeightService,
    WalletService,
    get_wallet_category_weight_service,
    get_wallet_service,
)

router = APIRouter(tags=["wallet-category-weights"])


async def _resolve_wallet_id(
    user: User,
    wallet_service: WalletService,
) -> int:
    wallet = await wallet_service.get_for_user(user.id)
    if wallet is None:
        raise HTTPException(
            status_code=404,
            detail="No wallet exists yet — fetch /wallet first to auto-create",
        )
    return wallet.id


@router.get(
    "/wallet/category-weights/{user_category_id}",
    response_model=WalletCategoryWeightsRead,
)
async def get_my_category_weights(
    user_category_id: int,
    user: User = Depends(get_current_user),
    wallet_service: WalletService = Depends(get_wallet_service),
    weight_service: WalletCategoryWeightService = Depends(
        get_wallet_category_weight_service
    ),
):
    wallet_id = await _resolve_wallet_id(user, wallet_service)
    return await weight_service.get_for_editor(wallet_id, user_category_id)


@router.put(
    "/wallet/category-weights/{user_category_id}",
    response_model=WalletCategoryWeightsRead,
)
async def save_my_category_weights(
    user_category_id: int,
    payload: WalletCategoryWeightsWrite,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    weight_service: WalletCategoryWeightService = Depends(
        get_wallet_category_weight_service
    ),
):
    wallet_id = await _resolve_wallet_id(user, wallet_service)
    weights = [(row.earn_category_id, row.weight) for row in payload.weights]
    result = await weight_service.save(wallet_id, user_category_id, weights)
    await db.commit()
    return result


@router.delete(
    "/wallet/category-weights/{user_category_id}",
    response_model=WalletCategoryWeightsRead,
)
async def reset_my_category_weights(
    user_category_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    weight_service: WalletCategoryWeightService = Depends(
        get_wallet_category_weight_service
    ),
):
    wallet_id = await _resolve_wallet_id(user, wallet_service)
    result = await weight_service.reset(wallet_id, user_category_id)
    await db.commit()
    return result
