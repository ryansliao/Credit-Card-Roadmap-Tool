"""Singular-wallet endpoints.

The new model is one wallet per user. ``GET /wallet`` and ``PATCH /wallet``
are the canonical endpoints for the user's wallet metadata + owned card
instances + scenario summaries. Owned-card CRUD lives at
``/wallet/card-instances/*`` (see :mod:`wallet_card_instances`); spend
items at ``/wallet/spend-items/*`` (see :mod:`wallet_spend`).
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth import get_current_user
from ...database import get_db
from ...models import User, Wallet
from ...schemas import (
    WalletUpdate,
    WalletWithScenariosRead,
    wallet_with_scenarios_read,
)
from ...services import (
    CardInstanceService,
    ScenarioService,
    WalletService,
    WalletSpendService,
    get_card_instance_service,
    get_scenario_service,
    get_wallet_service,
    get_wallet_spend_service,
)

router = APIRouter(tags=["wallet"])


async def _get_or_create_wallet(
    user: User,
    db: AsyncSession,
    wallet_service: WalletService,
    spend_service: WalletSpendService,
    scenario_service: ScenarioService,
) -> int:
    """Return the user's wallet id, creating wallet + default scenario +
    spend rows on first call."""
    wallet = await wallet_service.get_for_user(user.id)
    if wallet is None:
        wallet = await wallet_service.create(
            user_id=user.id,
            name="My Wallet",
            description=None,
        )
        await spend_service.ensure_all_user_categories(wallet.id)
        existing_default = await scenario_service.get_default_for_wallet(wallet.id)
        if existing_default is None:
            await scenario_service.create_default(wallet.id)
        await db.commit()
    return wallet.id


@router.get("/wallet", response_model=WalletWithScenariosRead)
async def get_my_wallet(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    spend_service: WalletSpendService = Depends(get_wallet_spend_service),
    instance_service: CardInstanceService = Depends(get_card_instance_service),
    scenario_service: ScenarioService = Depends(get_scenario_service),
):
    """Return the authenticated user's wallet with owned card instances and
    a list of scenarios. Auto-creates the wallet + default scenario on
    first access."""
    wallet_id = await _get_or_create_wallet(
        user, db, wallet_service, spend_service, scenario_service
    )
    result = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
    wallet = result.scalar_one()
    owned = await instance_service.list_owned(wallet_id)
    scenarios = await scenario_service.list_for_wallet(wallet_id)
    return wallet_with_scenarios_read(wallet, owned, scenarios)


@router.patch("/wallet", response_model=WalletWithScenariosRead)
async def update_my_wallet(
    payload: WalletUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    spend_service: WalletSpendService = Depends(get_wallet_spend_service),
    instance_service: CardInstanceService = Depends(get_card_instance_service),
    scenario_service: ScenarioService = Depends(get_scenario_service),
):
    """Update wallet metadata. Calc-config fields (start_date, duration_*,
    window_mode, include_subs) belong on a Scenario and are silently
    ignored if present in the payload."""
    wallet_id = await _get_or_create_wallet(
        user, db, wallet_service, spend_service, scenario_service
    )
    wallet = await wallet_service.get_for_user(user.id)
    assert wallet is not None
    updates = payload.model_dump(exclude_none=True)
    for legacy_field in ("include_subs", "as_of_date"):
        updates.pop(legacy_field, None)
    await wallet_service.update(wallet, **updates)
    await db.commit()

    owned = await instance_service.list_owned(wallet_id)
    scenarios = await scenario_service.list_for_wallet(wallet_id)
    result = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
    wallet_refreshed = result.scalar_one()
    return wallet_with_scenarios_read(wallet_refreshed, owned, scenarios)
