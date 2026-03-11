"""
FastAPI application entry point.

Endpoints
---------
GET  /issuers                       List all issuers
GET  /currencies                    List all currencies
GET  /cards                         List all cards
GET  /cards/{id}                    Get one card
PATCH /cards/{id}                   Update card static data

GET  /spend                         Get spend categories
PUT  /spend/{category}              Update a spend category

POST /calculate                     Run wallet calculation directly

GET  /wallets                       List wallets (by user_id, default 1)
POST /wallets                       Create a wallet
GET  /wallets/{id}                   Get one wallet
PATCH /wallets/{id}                 Update wallet metadata
DELETE /wallets/{id}                Delete wallet
POST /wallets/{id}/cards            Add a card to a wallet
DELETE /wallets/{id}/cards/{cid}    Remove a card from a wallet
GET  /wallets/{id}/results          Compute EV and opportunity cost (projection_years/months, reference_date, spend_overrides)

GET  /scenarios                     List scenarios
POST /scenarios                     Create a scenario
GET  /scenarios/{id}                Get one scenario
PATCH /scenarios/{id}               Update scenario metadata
DELETE /scenarios/{id}              Delete scenario
POST /scenarios/{id}/cards         Add a card to a scenario
DELETE /scenarios/{id}/cards/{cid}  Remove a card from a scenario
GET  /scenarios/{id}/results        Compute wallet for a scenario
"""

from __future__ import annotations

import contextlib
import json
import os
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .calculator import compute_wallet
from .database import create_tables, get_db
from .db_helpers import load_card_data, load_spend
from .models import (
    Card,
    CardCategoryMultiplier,
    CardCredit,
    CardEcosystem,
    Currency,
    Ecosystem,
    EcosystemCurrency,
    Issuer,
    Scenario,
    ScenarioCard,
    SpendCategory,
    User,
    Wallet,
    WalletCard,
)
from .db_helpers import apply_wallet_card_overrides
from .schemas import (
    CalculateRequest,
    CardCreate,
    CardRead,
    CardResultSchema,
    CardUpdate,
    CurrencyCreate,
    CurrencyRead,
    CurrencyUpdate,
    EcosystemCreate,
    EcosystemRead,
    EcosystemUpdate,
    IssuerCreate,
    IssuerRead,
    IssuerUpdate,
    ScenarioCardCreate,
    ScenarioCardRead,
    ScenarioCreate,
    ScenarioRead,
    ScenarioResultSchema,
    ScenarioUpdate,
    SpendCategoryRead,
    SpendCategoryUpdate,
    WalletCardCreate,
    WalletCardRead,
    WalletCreate,
    WalletRead,
    WalletResultResponseSchema,
    WalletResultSchema,
    WalletUpdate,
)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield


app = FastAPI(
    title="Credit Card Optimizer API",
    description="Credit card wallet optimizer — calculates EV for any combination of cards.",
    version="3.0.0",
    lifespan=lifespan,
)

_allowed_origins = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Common 404 helpers
# ---------------------------------------------------------------------------


def _card_404(card_id: int) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Card {card_id} not found")


def _scenario_404(scenario_id: int) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")


def _wallet_404(wallet_id: int) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Wallet {wallet_id} not found")


# ---------------------------------------------------------------------------
# Card selectinload options (reused across endpoints)
# ---------------------------------------------------------------------------


def _card_load_opts():
    return [
        selectinload(Card.issuer),
        selectinload(Card.currency_obj).selectinload(Currency.issuer),
        selectinload(Card.multipliers),
        selectinload(Card.credits),
        selectinload(Card.ecosystem_memberships)
        .selectinload(CardEcosystem.ecosystem)
        .selectinload(Ecosystem.points_currency)
        .selectinload(Currency.issuer),
        selectinload(Card.ecosystem_memberships)
        .selectinload(CardEcosystem.ecosystem)
        .selectinload(Ecosystem.cashback_currency),
        selectinload(Card.ecosystem_memberships)
        .selectinload(CardEcosystem.ecosystem)
        .selectinload(Ecosystem.ecosystem_currencies)
        .selectinload(EcosystemCurrency.currency),
    ]


# ---------------------------------------------------------------------------
# Issuers
# ---------------------------------------------------------------------------


@app.get("/issuers", response_model=list[IssuerRead], tags=["issuers"])
async def list_issuers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Issuer).order_by(Issuer.name))
    return result.scalars().all()


@app.post(
    "/issuers",
    response_model=IssuerRead,
    status_code=status.HTTP_201_CREATED,
    tags=["issuers"],
)
async def create_issuer(payload: IssuerCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Issuer).where(Issuer.name == payload.name))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Issuer with name {payload.name!r} already exists",
        )
    issuer = Issuer(
        name=payload.name,
        co_brand_partner=payload.co_brand_partner,
        network=payload.network,
    )
    db.add(issuer)
    await db.commit()
    await db.refresh(issuer)
    return issuer


@app.patch("/issuers/{issuer_id}", response_model=IssuerRead, tags=["issuers"])
async def update_issuer(
    issuer_id: int, payload: IssuerUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Issuer).where(Issuer.id == issuer_id))
    issuer = result.scalar_one_or_none()
    if not issuer:
        raise HTTPException(status_code=404, detail=f"Issuer {issuer_id} not found")
    updates = payload.model_dump(exclude_none=True)
    if "name" in updates and updates["name"] != issuer.name:
        existing = await db.execute(
            select(Issuer).where(Issuer.name == updates["name"])
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail=f"Issuer with name {updates['name']!r} already exists",
            )
    for field, value in updates.items():
        setattr(issuer, field, value)
    try:
        await db.commit()
        await db.refresh(issuer)
        return issuer
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Issuer name already in use by another issuer",
        )


@app.delete(
    "/issuers/{issuer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["issuers"],
)
async def delete_issuer(issuer_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Issuer).where(Issuer.id == issuer_id))
    issuer = result.scalar_one_or_none()
    if not issuer:
        raise HTTPException(status_code=404, detail=f"Issuer {issuer_id} not found")
    try:
        await db.delete(issuer)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Cannot delete issuer that has cards",
        )


# ---------------------------------------------------------------------------
# Currencies
# ---------------------------------------------------------------------------


@app.get("/currencies", response_model=list[CurrencyRead], tags=["currencies"])
async def list_currencies(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Currency)
        .options(selectinload(Currency.issuer))
        .order_by(Currency.name)
    )
    return result.scalars().all()


@app.post(
    "/currencies",
    response_model=CurrencyRead,
    status_code=status.HTTP_201_CREATED,
    tags=["currencies"],
)
async def create_currency(
    payload: CurrencyCreate, db: AsyncSession = Depends(get_db)
):
    if payload.issuer_id is not None:
        issuer_result = await db.execute(select(Issuer).where(Issuer.id == payload.issuer_id))
        if not issuer_result.scalar_one_or_none():
            raise HTTPException(
                status_code=422, detail=f"Issuer {payload.issuer_id} not found"
            )
    existing = await db.execute(select(Currency).where(Currency.name == payload.name))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Currency with name {payload.name!r} already exists",
        )
    currency = Currency(
        issuer_id=payload.issuer_id,
        name=payload.name,
        cents_per_point=payload.cents_per_point,
        is_cashback=payload.is_cashback,
        is_transferable=payload.is_transferable,
    )
    db.add(currency)
    await db.commit()
    await db.refresh(currency)
    result = await db.execute(
        select(Currency)
        .options(selectinload(Currency.issuer))
        .where(Currency.id == currency.id)
    )
    return result.scalar_one()


@app.patch("/currencies/{currency_id}", response_model=CurrencyRead, tags=["currencies"])
async def update_currency(
    currency_id: int, payload: CurrencyUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Currency)
        .options(selectinload(Currency.issuer))
        .where(Currency.id == currency_id)
    )
    currency = result.scalar_one_or_none()
    if not currency:
        raise HTTPException(status_code=404, detail=f"Currency {currency_id} not found")
    updates = payload.model_dump(exclude_none=True)
    if "name" in updates and updates["name"] != currency.name:
        existing = await db.execute(
            select(Currency).where(Currency.name == updates["name"])
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail=f"Currency with name {updates['name']!r} already exists",
            )
    if "issuer_id" in updates and updates["issuer_id"] is not None:
        issuer_result = await db.execute(
            select(Issuer).where(Issuer.id == updates["issuer_id"])
        )
        if not issuer_result.scalar_one_or_none():
            raise HTTPException(
                status_code=422, detail=f"Issuer {updates['issuer_id']} not found"
            )
    for field, value in updates.items():
        setattr(currency, field, value)
    await db.commit()
    await db.refresh(currency)
    result = await db.execute(
        select(Currency)
        .options(selectinload(Currency.issuer))
        .where(Currency.id == currency_id)
    )
    return result.scalar_one()


@app.delete(
    "/currencies/{currency_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["currencies"],
)
async def delete_currency(currency_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Currency).where(Currency.id == currency_id))
    currency = result.scalar_one_or_none()
    if not currency:
        raise HTTPException(status_code=404, detail=f"Currency {currency_id} not found")
    try:
        await db.delete(currency)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Cannot delete currency that is referenced by a card",
        )


# ---------------------------------------------------------------------------
# Ecosystems
# ---------------------------------------------------------------------------


def _ecosystem_load_opts():
    return [
        selectinload(Ecosystem.points_currency).selectinload(Currency.issuer),
        selectinload(Ecosystem.cashback_currency),
        selectinload(Ecosystem.ecosystem_currencies).selectinload(EcosystemCurrency.currency),
    ]


@app.get("/ecosystems", response_model=list[EcosystemRead], tags=["ecosystems"])
async def list_ecosystems(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Ecosystem).options(*_ecosystem_load_opts()).order_by(Ecosystem.name)
    )
    return result.scalars().all()


@app.get("/ecosystems/{ecosystem_id}", response_model=EcosystemRead, tags=["ecosystems"])
async def get_ecosystem(ecosystem_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Ecosystem).options(*_ecosystem_load_opts()).where(Ecosystem.id == ecosystem_id)
    )
    eco = result.scalar_one_or_none()
    if not eco:
        raise HTTPException(status_code=404, detail=f"Ecosystem {ecosystem_id} not found")
    return eco


async def _cash_currency_id(db: AsyncSession) -> Optional[int]:
    """Return the id of the currency named 'Cash', or None if not found."""
    r = await db.execute(select(Currency.id).where(Currency.name == "Cash").limit(1))
    return r.scalar_one_or_none()


@app.post(
    "/ecosystems",
    response_model=EcosystemRead,
    status_code=status.HTTP_201_CREATED,
    tags=["ecosystems"],
)
async def create_ecosystem(
    payload: EcosystemCreate, db: AsyncSession = Depends(get_db)
):
    cur = await db.get(Currency, payload.points_currency_id)
    if not cur:
        raise HTTPException(
            status_code=422, detail="Points currency not found"
        )
    existing = await db.execute(
        select(Ecosystem).where(Ecosystem.name == payload.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Ecosystem with name {payload.name!r} already exists",
        )
    eco = Ecosystem(
        name=payload.name,
        points_currency_id=payload.points_currency_id,
        cashback_currency_id=payload.cashback_currency_id,
    )
    db.add(eco)
    await db.commit()
    await db.refresh(eco)
    for cid in payload.additional_currency_ids or []:
        c = await db.get(Currency, cid)
        if c:
            db.add(EcosystemCurrency(ecosystem_id=eco.id, currency_id=cid))
    await db.commit()
    result = await db.execute(
        select(Ecosystem).options(*_ecosystem_load_opts()).where(Ecosystem.id == eco.id)
    )
    return result.scalar_one()


@app.patch("/ecosystems/{ecosystem_id}", response_model=EcosystemRead, tags=["ecosystems"])
async def update_ecosystem(
    ecosystem_id: int, payload: EcosystemUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Ecosystem).options(selectinload(Ecosystem.ecosystem_currencies)).where(Ecosystem.id == ecosystem_id)
    )
    eco = result.scalar_one_or_none()
    if not eco:
        raise HTTPException(status_code=404, detail=f"Ecosystem {ecosystem_id} not found")
    updates = payload.model_dump(exclude_unset=True)
    additional_ids = updates.pop("additional_currency_ids", None)
    if "points_currency_id" in updates:
        cur = await db.get(Currency, updates["points_currency_id"])
        if not cur:
            raise HTTPException(status_code=422, detail="Points currency not found")
    for field, value in updates.items():
        setattr(eco, field, value)
    if additional_ids is not None:
        for ec in list(eco.ecosystem_currencies):
            await db.delete(ec)
        for cid in additional_ids:
            c = await db.get(Currency, cid)
            if c:
                db.add(EcosystemCurrency(ecosystem_id=eco.id, currency_id=cid))
    await db.commit()
    result = await db.execute(
        select(Ecosystem).options(*_ecosystem_load_opts()).where(Ecosystem.id == ecosystem_id)
    )
    return result.scalar_one()


@app.delete(
    "/ecosystems/{ecosystem_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["ecosystems"],
)
async def delete_ecosystem(ecosystem_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Ecosystem).where(Ecosystem.id == ecosystem_id))
    eco = result.scalar_one_or_none()
    if not eco:
        raise HTTPException(status_code=404, detail=f"Ecosystem {ecosystem_id} not found")
    await db.delete(eco)
    await db.commit()


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------


@app.get("/cards", response_model=list[CardRead], tags=["cards"])
async def list_cards(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Card).options(*_card_load_opts()))
    return result.scalars().all()


@app.get("/cards/{card_id}", response_model=CardRead, tags=["cards"])
async def get_card(card_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Card).options(*_card_load_opts()).where(Card.id == card_id)
    )
    card = result.scalar_one_or_none()
    if not card:
        raise _card_404(card_id)
    return card


@app.patch("/cards/{card_id}", response_model=CardRead, tags=["cards"])
async def update_card(
    card_id: int, payload: CardUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Card).options(*_card_load_opts()).where(Card.id == card_id)
    )
    card = result.scalar_one_or_none()
    if not card:
        raise _card_404(card_id)

    updates = payload.model_dump(exclude_none=True)

    # Validate FK targets if being updated
    new_issuer_id = updates.get("issuer_id") or card.issuer_id
    if "issuer_id" in updates:
        issuer = await db.get(Issuer, updates["issuer_id"])
        if not issuer:
            raise HTTPException(
                status_code=422, detail=f"Issuer {updates['issuer_id']} not found"
            )
    if "currency_id" in updates:
        cur = await db.get(Currency, updates["currency_id"])
        if not cur:
            raise HTTPException(status_code=422, detail=f"Currency {updates['currency_id']} not found")
        if cur.issuer_id is not None and cur.issuer_id != new_issuer_id:
            raise HTTPException(
                status_code=422,
                detail="Currency does not belong to the selected issuer",
            )
    elif "issuer_id" in updates:
        # Changing issuer only: current currency must belong to the new issuer (or have no issuer)
        cur = await db.get(Currency, card.currency_id)
        if cur and cur.issuer_id is not None and cur.issuer_id != new_issuer_id:
            raise HTTPException(
                status_code=422,
                detail="Current currency does not belong to the new issuer. Please also select a currency for the new issuer.",
            )

    ecosystem_memberships = updates.pop("ecosystem_memberships", None)
    for field, value in updates.items():
        setattr(card, field, value)

    if ecosystem_memberships is not None:
        # Replace card's ecosystem memberships
        for ce in list(card.ecosystem_memberships):
            await db.delete(ce)
        await db.flush()
        for m in ecosystem_memberships:
            eco = await db.get(Ecosystem, m["ecosystem_id"])
            if not eco:
                raise HTTPException(
                    status_code=422,
                    detail=f"Ecosystem {m['ecosystem_id']} not found",
                )
            db.add(
                CardEcosystem(
                    card_id=card.id,
                    ecosystem_id=eco.id,
                    key_card=m["key_card"],
                )
            )

    await db.commit()
    # Reload with full opts to get updated nested objects
    result = await db.execute(
        select(Card).options(*_card_load_opts()).where(Card.id == card_id)
    )
    return result.scalar_one()


@app.post(
    "/cards",
    response_model=CardRead,
    status_code=status.HTTP_201_CREATED,
    tags=["cards"],
)
async def create_card(
    payload: CardCreate, db: AsyncSession = Depends(get_db)
):
    issuer_result = await db.execute(select(Issuer).where(Issuer.id == payload.issuer_id))
    issuer = issuer_result.scalar_one_or_none()
    if not issuer:
        raise HTTPException(
            status_code=422, detail=f"Issuer {payload.issuer_id} not found"
        )
    currency_result = await db.execute(
        select(Currency)
        .options(selectinload(Currency.issuer))
        .where(Currency.id == payload.currency_id)
    )
    currency = currency_result.scalar_one_or_none()
    if not currency:
        raise HTTPException(
            status_code=422, detail=f"Currency {payload.currency_id} not found"
        )
    if currency.issuer_id is not None and currency.issuer_id != payload.issuer_id:
        raise HTTPException(
            status_code=422,
            detail="Currency does not belong to the selected issuer",
        )
    existing = await db.execute(select(Card).where(Card.name == payload.name))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Card with name {payload.name!r} already exists",
        )
    card = Card(
        name=payload.name,
        issuer_id=payload.issuer_id,
        currency_id=payload.currency_id,
        annual_fee=payload.annual_fee,
        sub_points=payload.sub_points,
        sub_min_spend=payload.sub_min_spend,
        sub_months=payload.sub_months,
        sub_spend_points=payload.sub_spend_points,
        annual_bonus_points=payload.annual_bonus_points,
    )
    db.add(card)
    await db.flush()
    for m in payload.ecosystem_memberships:
        eco = await db.get(Ecosystem, m.ecosystem_id)
        if not eco:
            raise HTTPException(
                status_code=422,
                detail=f"Ecosystem {m.ecosystem_id} not found",
            )
        db.add(
            CardEcosystem(
                card_id=card.id,
                ecosystem_id=eco.id,
                key_card=m.key_card,
            )
        )
    for m in payload.multipliers:
        db.add(
            CardCategoryMultiplier(
                card_id=card.id,
                category=m.category,
                multiplier=m.multiplier,
            )
        )
    for c in payload.credits:
        db.add(
            CardCredit(
                card_id=card.id,
                credit_name=c.credit_name,
                credit_value=c.credit_value,
            )
        )
    await db.commit()
    result = await db.execute(
        select(Card).options(*_card_load_opts()).where(Card.id == card.id)
    )
    return result.scalar_one()


@app.delete(
    "/cards/{card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["cards"],
)
async def delete_card(card_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Card).where(Card.id == card_id))
    card = result.scalar_one_or_none()
    if not card:
        raise _card_404(card_id)
    await db.delete(card)
    await db.commit()


# ---------------------------------------------------------------------------
# Spend categories
# ---------------------------------------------------------------------------


@app.get("/spend", response_model=list[SpendCategoryRead], tags=["spend"])
async def list_spend(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SpendCategory))
    return result.scalars().all()


@app.put("/spend/{category}", response_model=SpendCategoryRead, tags=["spend"])
async def update_spend(
    category: str, payload: SpendCategoryUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(SpendCategory).where(SpendCategory.category == category)
    )
    sc = result.scalar_one_or_none()
    if not sc:
        raise HTTPException(status_code=404, detail=f"Category '{category}' not found")
    sc.annual_spend = payload.annual_spend
    await db.commit()
    await db.refresh(sc)
    return sc


# ---------------------------------------------------------------------------
# Direct calculation (no spreadsheet)
# ---------------------------------------------------------------------------


@app.post("/calculate", response_model=WalletResultSchema, tags=["calculate"])
async def calculate(
    payload: CalculateRequest, db: AsyncSession = Depends(get_db)
):
    """
    Run the wallet calculation engine directly.
    Pass selected_card_ids, years_counted, and optional spend_overrides.
    """
    all_cards = await load_card_data(db)
    spend = await load_spend(db, overrides=payload.spend_overrides)
    wallet = compute_wallet(
        all_cards=all_cards,
        selected_ids=set(payload.selected_card_ids),
        spend=spend,
        years=payload.years_counted,
    )
    return _wallet_to_schema(wallet)


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


@app.get("/scenarios", response_model=list[ScenarioRead], tags=["scenarios"])
async def list_scenarios(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Scenario).options(selectinload(Scenario.scenario_cards))
    )
    return result.scalars().all()


@app.post(
    "/scenarios",
    response_model=ScenarioRead,
    status_code=status.HTTP_201_CREATED,
    tags=["scenarios"],
)
async def create_scenario(payload: ScenarioCreate, db: AsyncSession = Depends(get_db)):
    scenario = Scenario(
        name=payload.name,
        description=payload.description,
        as_of_date=payload.as_of_date,
    )
    db.add(scenario)
    await db.flush()

    for sc in payload.cards:
        card_result = await db.execute(select(Card).where(Card.id == sc.card_id))
        if not card_result.scalar_one_or_none():
            raise HTTPException(
                status_code=422, detail=f"Card id={sc.card_id} not found"
            )
        db.add(
            ScenarioCard(
                scenario_id=scenario.id,
                card_id=sc.card_id,
                start_date=sc.start_date,
                end_date=sc.end_date,
                years_counted=sc.years_counted,
            )
        )

    await db.commit()
    result = await db.execute(
        select(Scenario)
        .options(selectinload(Scenario.scenario_cards))
        .where(Scenario.id == scenario.id)
    )
    return result.scalar_one()


@app.get("/scenarios/{scenario_id}", response_model=ScenarioRead, tags=["scenarios"])
async def get_scenario(scenario_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Scenario)
        .options(selectinload(Scenario.scenario_cards))
        .where(Scenario.id == scenario_id)
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise _scenario_404(scenario_id)
    return scenario


@app.patch(
    "/scenarios/{scenario_id}", response_model=ScenarioRead, tags=["scenarios"]
)
async def update_scenario(
    scenario_id: int, payload: ScenarioUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Scenario)
        .options(selectinload(Scenario.scenario_cards))
        .where(Scenario.id == scenario_id)
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise _scenario_404(scenario_id)

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(scenario, field, value)

    await db.commit()
    await db.refresh(scenario)
    return scenario


@app.delete(
    "/scenarios/{scenario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["scenarios"],
)
async def delete_scenario(scenario_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Scenario).where(Scenario.id == scenario_id)
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise _scenario_404(scenario_id)
    await db.delete(scenario)
    await db.commit()


@app.post(
    "/scenarios/{scenario_id}/cards",
    response_model=ScenarioCardRead,
    status_code=status.HTTP_201_CREATED,
    tags=["scenarios"],
)
async def add_card_to_scenario(
    scenario_id: int,
    payload: ScenarioCardCreate,
    db: AsyncSession = Depends(get_db),
):
    sc_result = await db.execute(
        select(Scenario).where(Scenario.id == scenario_id)
    )
    if not sc_result.scalar_one_or_none():
        raise _scenario_404(scenario_id)

    card_result = await db.execute(select(Card).where(Card.id == payload.card_id))
    card = card_result.scalar_one_or_none()
    if not card:
        raise _card_404(payload.card_id)

    sc = ScenarioCard(
        scenario_id=scenario_id,
        card_id=payload.card_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        years_counted=payload.years_counted,
    )
    db.add(sc)
    await db.commit()
    await db.refresh(sc)

    read = ScenarioCardRead.model_validate(sc)
    read.card_name = card.name
    return read


@app.delete(
    "/scenarios/{scenario_id}/cards/{card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["scenarios"],
)
async def remove_card_from_scenario(
    scenario_id: int, card_id: int, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ScenarioCard).where(
            ScenarioCard.scenario_id == scenario_id,
            ScenarioCard.card_id == card_id,
        )
    )
    sc = result.scalar_one_or_none()
    if not sc:
        raise HTTPException(
            status_code=404,
            detail=f"Card {card_id} not in scenario {scenario_id}",
        )
    await db.delete(sc)
    await db.commit()


@app.get(
    "/scenarios/{scenario_id}/results",
    response_model=ScenarioResultSchema,
    tags=["scenarios"],
)
async def scenario_results(
    scenario_id: int,
    reference_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Compute wallet EV for a scenario.

    Cards are considered active if:
      - start_date is None OR start_date <= reference_date
      - end_date is None OR end_date > reference_date

    reference_date defaults to scenario.as_of_date, then today.
    """
    result = await db.execute(
        select(Scenario)
        .options(selectinload(Scenario.scenario_cards))
        .where(Scenario.id == scenario_id)
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise _scenario_404(scenario_id)

    ref_date = reference_date or scenario.as_of_date or date.today()

    active_years: dict[int, int] = {}
    for sc in scenario.scenario_cards:
        start_ok = sc.start_date is None or sc.start_date <= ref_date
        end_ok = sc.end_date is None or sc.end_date > ref_date
        if start_ok and end_ok:
            active_years[sc.card_id] = sc.years_counted

    if not active_years:
        return ScenarioResultSchema(
            scenario_id=scenario_id,
            scenario_name=scenario.name,
            as_of_date=ref_date,
            wallet=WalletResultSchema(
                years_counted=2,
                total_annual_ev=0,
                total_points_earned=0,
                total_annual_pts=0,
            ),
        )

    years_counted = max(set(active_years.values()), key=list(active_years.values()).count)

    all_cards = await load_card_data(db)
    spend = await load_spend(db)

    wallet = compute_wallet(
        all_cards=all_cards,
        selected_ids=set(active_years.keys()),
        spend=spend,
        years=years_counted,
    )

    return ScenarioResultSchema(
        scenario_id=scenario_id,
        scenario_name=scenario.name,
        as_of_date=ref_date,
        wallet=_wallet_to_schema(wallet),
    )


# ---------------------------------------------------------------------------
# Wallets (Wallet Tool)
# ---------------------------------------------------------------------------

DEFAULT_USER_ID = 1


@app.get("/wallets", response_model=list[WalletRead], tags=["wallets"])
async def list_wallets(
    user_id: int = DEFAULT_USER_ID,
    db: AsyncSession = Depends(get_db),
):
    """List wallets for the given user (default user_id=1 for single-tenant)."""
    result = await db.execute(
        select(Wallet)
        .options(
            selectinload(Wallet.wallet_cards).selectinload(WalletCard.card),
        )
        .where(Wallet.user_id == user_id)
        .order_by(Wallet.id)
    )
    wallets = result.scalars().all()
    # Populate card_name on each WalletCardRead for response
    out = []
    for w in wallets:
        read = WalletRead.model_validate(w)
        read.wallet_cards = [
            WalletCardRead(
                id=wc.id,
                wallet_id=wc.wallet_id,
                card_id=wc.card_id,
                card_name=wc.card.name,
                added_date=wc.added_date,
                sub_points=wc.sub_points,
                sub_min_spend=wc.sub_min_spend,
                sub_months=wc.sub_months,
                sub_spend_points=wc.sub_spend_points,
                years_counted=wc.years_counted,
            )
            for wc in w.wallet_cards
        ]
        out.append(read)
    return out


@app.post(
    "/wallets",
    response_model=WalletRead,
    status_code=status.HTTP_201_CREATED,
    tags=["wallets"],
)
async def create_wallet(payload: WalletCreate, db: AsyncSession = Depends(get_db)):
    user_result = await db.execute(select(User).where(User.id == payload.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        # Auto-create default user so wallet creation works without running seed
        if payload.user_id == DEFAULT_USER_ID:
            user = User(id=DEFAULT_USER_ID, name="Default User")
            db.add(user)
            await db.flush()
        else:
            raise HTTPException(status_code=400, detail=f"User id={payload.user_id} not found")
    wallet = Wallet(
        user_id=payload.user_id,
        name=payload.name,
        description=payload.description,
        as_of_date=payload.as_of_date,
    )
    db.add(wallet)
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


@app.get("/wallets/{wallet_id}", response_model=WalletRead, tags=["wallets"])
async def get_wallet(wallet_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Wallet)
        .options(
            selectinload(Wallet.wallet_cards).selectinload(WalletCard.card),
        )
        .where(Wallet.id == wallet_id)
    )
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise _wallet_404(wallet_id)
    read = WalletRead.model_validate(wallet)
    read.wallet_cards = [
        WalletCardRead(
            id=wc.id,
            wallet_id=wc.wallet_id,
            card_id=wc.card_id,
            card_name=wc.card.name,
            added_date=wc.added_date,
            sub_points=wc.sub_points,
            sub_min_spend=wc.sub_min_spend,
            sub_months=wc.sub_months,
            sub_spend_points=wc.sub_spend_points,
            years_counted=wc.years_counted,
        )
        for wc in wallet.wallet_cards
    ]
    return read


@app.patch(
    "/wallets/{wallet_id}", response_model=WalletRead, tags=["wallets"]
)
async def update_wallet(
    wallet_id: int, payload: WalletUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Wallet)
        .options(
            selectinload(Wallet.wallet_cards).selectinload(WalletCard.card),
        )
        .where(Wallet.id == wallet_id)
    )
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise _wallet_404(wallet_id)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(wallet, field, value)
    await db.commit()
    await db.refresh(wallet)
    read = WalletRead.model_validate(wallet)
    read.wallet_cards = [
        WalletCardRead(
            id=wc.id,
            wallet_id=wc.wallet_id,
            card_id=wc.card_id,
            card_name=wc.card.name,
            added_date=wc.added_date,
            sub_points=wc.sub_points,
            sub_min_spend=wc.sub_min_spend,
            sub_months=wc.sub_months,
            sub_spend_points=wc.sub_spend_points,
            years_counted=wc.years_counted,
        )
        for wc in wallet.wallet_cards
    ]
    return read


@app.delete(
    "/wallets/{wallet_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["wallets"],
)
async def delete_wallet(wallet_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise _wallet_404(wallet_id)
    await db.delete(wallet)
    await db.commit()


@app.post(
    "/wallets/{wallet_id}/cards",
    response_model=WalletCardRead,
    status_code=status.HTTP_201_CREATED,
    tags=["wallets"],
)
async def add_card_to_wallet(
    wallet_id: int,
    payload: WalletCardCreate,
    db: AsyncSession = Depends(get_db),
):
    w_result = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
    if not w_result.scalar_one_or_none():
        raise _wallet_404(wallet_id)
    card_result = await db.execute(select(Card).where(Card.id == payload.card_id))
    card = card_result.scalar_one_or_none()
    if not card:
        raise _card_404(payload.card_id)
    wc = WalletCard(
        wallet_id=wallet_id,
        card_id=payload.card_id,
        added_date=payload.added_date,
        sub_points=payload.sub_points,
        sub_min_spend=payload.sub_min_spend,
        sub_months=payload.sub_months,
        sub_spend_points=payload.sub_spend_points,
        years_counted=payload.years_counted,
    )
    db.add(wc)
    await db.commit()
    await db.refresh(wc)
    return WalletCardRead(
        id=wc.id,
        wallet_id=wc.wallet_id,
        card_id=wc.card_id,
        card_name=card.name,
        added_date=wc.added_date,
        sub_points=wc.sub_points,
        sub_min_spend=wc.sub_min_spend,
        sub_months=wc.sub_months,
        sub_spend_points=wc.sub_spend_points,
        years_counted=wc.years_counted,
    )


@app.delete(
    "/wallets/{wallet_id}/cards/{card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["wallets"],
)
async def remove_card_from_wallet(
    wallet_id: int, card_id: int, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(WalletCard).where(
            WalletCard.wallet_id == wallet_id,
            WalletCard.card_id == card_id,
        )
    )
    wc = result.scalar_one_or_none()
    if not wc:
        raise HTTPException(
            status_code=404,
            detail=f"Card {card_id} not in wallet {wallet_id}",
        )
    await db.delete(wc)
    await db.commit()


@app.get(
    "/wallets/{wallet_id}/results",
    response_model=WalletResultResponseSchema,
    tags=["wallets"],
)
async def wallet_results(
    wallet_id: int,
    reference_date: Optional[date] = None,
    projection_years: int = 2,
    projection_months: int = 0,
    spend_overrides: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Compute wallet EV and opportunity cost for the wallet over the given time frame.
    Cards with added_date <= reference_date are active. SUB amortization uses
    years_counted derived from projection_years + projection_months.
    spend_overrides: optional JSON object of category name -> annual spend.
    """
    overrides: dict[str, float] = {}
    if spend_overrides:
        try:
            overrides = json.loads(spend_overrides)
        except (json.JSONDecodeError, TypeError):
            pass
    result = await db.execute(
        select(Wallet)
        .options(selectinload(Wallet.wallet_cards))
        .where(Wallet.id == wallet_id)
    )
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise _wallet_404(wallet_id)

    ref_date = reference_date or wallet.as_of_date or date.today()
    # Cards active as of reference date (already in the wallet by then)
    active_wallet_cards = [wc for wc in wallet.wallet_cards if wc.added_date <= ref_date]
    # Integer years for SUB amortization: projection_years + round(projection_months/12) or simple
    years_counted = max(1, projection_years + (1 if projection_months >= 6 else 0))

    if not active_wallet_cards:
        return WalletResultResponseSchema(
            wallet_id=wallet_id,
            wallet_name=wallet.name,
            as_of_date=ref_date,
            projection_years=projection_years,
            projection_months=projection_months,
            years_counted=years_counted,
            wallet=WalletResultSchema(
                years_counted=years_counted,
                total_annual_ev=0,
                total_points_earned=0,
                total_annual_pts=0,
            ),
        )

    all_cards = await load_card_data(db)
    modified_cards = apply_wallet_card_overrides(all_cards, active_wallet_cards)
    selected_ids = {wc.card_id for wc in active_wallet_cards}
    spend = await load_spend(db, overrides=overrides)

    wallet_result = compute_wallet(
        all_cards=modified_cards,
        selected_ids=selected_ids,
        spend=spend,
        years=years_counted,
    )

    return WalletResultResponseSchema(
        wallet_id=wallet_id,
        wallet_name=wallet.name,
        as_of_date=ref_date,
        projection_years=projection_years,
        projection_months=projection_months,
        years_counted=wallet_result.years_counted,
        wallet=_wallet_to_schema(wallet_result),
    )


# ---------------------------------------------------------------------------
# Schema conversion helper
# ---------------------------------------------------------------------------


def _wallet_to_schema(wallet) -> WalletResultSchema:
    card_schemas = [
        CardResultSchema(
            card_id=cr.card_id,
            card_name=cr.card_name,
            selected=cr.selected,
            annual_ev=cr.annual_ev,
            second_year_ev=cr.second_year_ev,
            total_points=cr.total_points,
            annual_point_earn=cr.annual_point_earn,
            credit_valuation=cr.credit_valuation,
            annual_fee=cr.annual_fee,
            sub_points=cr.sub_points,
            annual_bonus_points=cr.annual_bonus_points,
            sub_extra_spend=cr.sub_extra_spend,
            sub_spend_points=cr.sub_spend_points,
            sub_opp_cost_dollars=cr.sub_opp_cost_dollars,
            sub_opp_cost_gross_dollars=cr.sub_opp_cost_gross_dollars,
            avg_spend_multiplier=cr.avg_spend_multiplier,
            cents_per_point=cr.cents_per_point,
            effective_currency_name=cr.effective_currency_name,
        )
        for cr in wallet.card_results
    ]

    return WalletResultSchema(
        years_counted=wallet.years_counted,
        total_annual_ev=wallet.total_annual_ev,
        total_points_earned=wallet.total_points_earned,
        total_annual_pts=wallet.total_annual_pts,
        currency_pts=wallet.currency_pts,
        card_results=card_schemas,
    )


# ---------------------------------------------------------------------------
# Serve React SPA (must come last — catches all unmatched routes)
# ---------------------------------------------------------------------------

_FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"

if _FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str):
    index = _FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    raise HTTPException(
        status_code=404,
        detail="Frontend not built. Run: cd frontend && npm run build",
    )
