"""Owned CardInstance CRUD — drives Profile/WalletTab.

These endpoints manage the user's actual cards (CardInstance rows where
``scenario_id IS NULL``). The Roadmap Tool cannot delete or modify owned
card base fields — it operates on overlays and future cards instead.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth import get_current_user
from ...database import get_db
from ...models import User
from ...schemas import (
    CardInstanceRead,
    OwnedCardCreate,
    OwnedCardUpdate,
    card_instance_read,
)
from ...services import (
    CardInstanceService,
    WalletService,
    get_card_instance_service,
    get_wallet_service,
)

router = APIRouter(tags=["wallet-card-instances"])


@router.get(
    "/wallet/card-instances",
    response_model=list[CardInstanceRead],
)
async def list_owned_card_instances(
    user: User = Depends(get_current_user),
    wallet_service: WalletService = Depends(get_wallet_service),
    instance_service: CardInstanceService = Depends(get_card_instance_service),
):
    """List the user's owned cards. Auto-creates the wallet if missing."""
    wallet = await wallet_service.get_for_user(user.id)
    if not wallet:
        raise HTTPException(
            status_code=404, detail="No wallet exists for this user yet"
        )
    instances = await instance_service.list_owned(wallet.id)
    return [card_instance_read(i) for i in instances]


@router.post(
    "/wallet/card-instances",
    response_model=CardInstanceRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_owned_card_instance(
    payload: OwnedCardCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    instance_service: CardInstanceService = Depends(get_card_instance_service),
):
    wallet = await wallet_service.get_for_user(user.id)
    if not wallet:
        raise HTTPException(
            status_code=404, detail="No wallet exists for this user yet"
        )
    inst = await instance_service.create_owned(wallet.id, payload)
    await db.commit()
    inst = await instance_service.get_with_card(inst.id)
    return card_instance_read(inst)


@router.patch(
    "/wallet/card-instances/{instance_id}",
    response_model=CardInstanceRead,
)
async def update_owned_card_instance(
    instance_id: int,
    payload: OwnedCardUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    instance_service: CardInstanceService = Depends(get_card_instance_service),
):
    wallet = await wallet_service.get_for_user(user.id)
    if not wallet:
        raise HTTPException(status_code=404, detail="No wallet for this user")
    inst = await instance_service.get_with_card(instance_id)
    if inst.wallet_id != wallet.id:
        raise HTTPException(status_code=403, detail="Not your card")
    if inst.scenario_id is not None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Use the scenario future-card endpoint to update a "
                "scenario-scoped instance"
            ),
        )
    await instance_service.update(inst, **payload.model_dump(exclude_unset=True))
    await db.commit()
    inst = await instance_service.get_with_card(instance_id)
    return card_instance_read(inst)


@router.delete(
    "/wallet/card-instances/{instance_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_owned_card_instance(
    instance_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    instance_service: CardInstanceService = Depends(get_card_instance_service),
):
    wallet = await wallet_service.get_for_user(user.id)
    if not wallet:
        raise HTTPException(status_code=404, detail="No wallet for this user")
    inst = await instance_service.get_with_card(instance_id)
    if inst.wallet_id != wallet.id:
        raise HTTPException(status_code=403, detail="Not your card")
    await instance_service.delete_owned(inst)
    await db.commit()
