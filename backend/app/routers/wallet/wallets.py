"""Wallet CRUD and wallet card management endpoints.

The new model is one wallet per user. ``GET /wallet`` and ``PATCH /wallet``
are the canonical endpoints. The legacy ``/wallets`` (list) and
``/wallets/{wallet_id}`` family is preserved during the migration window
so existing clients keep working — they delegate to the singular wallet
under the hood.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...auth import get_current_user
from ...database import get_db
from ...models import CardInstance, Scenario, User, Wallet
from ...schemas import (
    WalletCardCreate,
    WalletCardRead,
    WalletCardUpdate,
    WalletCreate,
    WalletRead,
    WalletSummary,
    WalletUpdate,
    WalletWithScenariosRead,
    wallet_read,
    wallet_with_scenarios_read,
    wc_read,
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

router = APIRouter(tags=["wallets"])


# ---------------------------------------------------------------------------
# New canonical singular-wallet endpoints
# ---------------------------------------------------------------------------


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
        # Spawn the default scenario so the picker always has something.
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
    """Update wallet metadata. Only ``name``, ``description``,
    ``foreign_spend_percent`` are persisted in the new model — calc-config
    fields belong on a Scenario."""
    wallet_id = await _get_or_create_wallet(
        user, db, wallet_service, spend_service, scenario_service
    )
    wallet = await wallet_service.get_with_cards(wallet_id)
    updates = payload.model_dump(exclude_none=True)
    # Calc-config fields no longer live on Wallet; ignore if present.
    for legacy_field in ("include_subs", "as_of_date"):
        updates.pop(legacy_field, None)
    await wallet_service.update(wallet, **updates)
    await db.commit()

    owned = await instance_service.list_owned(wallet_id)
    scenarios = await scenario_service.list_for_wallet(wallet_id)
    result = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
    wallet_refreshed = result.scalar_one()
    return wallet_with_scenarios_read(wallet_refreshed, owned, scenarios)


# ---------------------------------------------------------------------------
# Legacy endpoints — preserved for backward compatibility during migration.
# ---------------------------------------------------------------------------


@router.get("/wallets", response_model=list[WalletSummary])
async def list_my_wallets(
    user: User = Depends(get_current_user),
    wallet_service: WalletService = Depends(get_wallet_service),
):
    """Legacy list endpoint. With one-wallet-per-user, this returns at
    most one entry."""
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
    scenario_service: ScenarioService = Depends(get_scenario_service),
):
    """Legacy create endpoint. Returns the existing wallet if one exists."""
    existing = await wallet_service.get_for_user(user.id)
    if existing:
        wallet = await wallet_service.get_with_cards(existing.id)
        return wallet_read(wallet)
    wallet = await wallet_service.create(
        user_id=user.id,
        name=payload.name,
        description=payload.description,
    )
    await spend_service.ensure_all_user_categories(wallet.id)
    if not await scenario_service.get_default_for_wallet(wallet.id):
        await scenario_service.create_default(wallet.id)
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
    """Legacy WalletCard create. The new flow uses
    ``POST /wallet/card-instances`` for owned cards and
    ``POST /scenarios/{sid}/future-cards`` for scenario-scoped cards."""
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
