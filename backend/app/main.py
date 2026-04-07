"""
FastAPI application entry point.

Endpoints
---------
GET  /issuers                                               List all issuers
GET  /issuers/application-rules                             List all issuer velocity/eligibility rules
GET  /currencies                                            List all currencies
GET  /cards                                                 List all cards
PATCH /cards/{id}                                           Update card library fields (SUB, fees)
PATCH /cards/{id}/credits/{credit_id}                       Update a card statement credit (value, name, one-time flag)

GET  /spend                                                 Get card-level spend categories (reference)
GET  /app-spend-categories                                  Get app-level spend category hierarchy (user-facing)

GET  /wallets                                               List wallets (by user_id, default 1)
POST /wallets                                               Create a wallet
GET  /wallets/{id}                                          Get one wallet
PATCH /wallets/{id}                                         Update wallet metadata
DELETE /wallets/{id}                                        Delete wallet
POST /wallets/{id}/cards                                    Add a card to a wallet
PATCH /wallets/{id}/cards/{card_id}                         Update a wallet card (SUB earned, closed, overrides)
DELETE /wallets/{id}/cards/{cid}                            Remove a card from a wallet
GET  /wallets/{id}/results                                  Wallet results and opportunity cost
GET  /wallets/{id}/roadmap                                  Compute roadmap: 5/24, SUB status, eligibility
GET  /wallets/{id}/currency-balances                       List tracked / earned currency rows for this wallet
POST /wallets/{id}/currency-balances                       Track a currency (optional initial balance)
PUT    /wallets/{id}/currencies/{currency_id}/balance       Set initial balance (total = initial + projection earn)
DELETE /wallets/{id}/currencies/{currency_id}/balance      Remove tracking row
GET    /wallets/{id}/currencies                             List currencies with wallet CPP overrides
PUT    /wallets/{id}/currencies/{currency_id}/cpp           Set wallet CPP override
DELETE /wallets/{id}/currencies/{currency_id}/cpp           Remove wallet CPP override

GET    /wallets/{id}/spend-items                            List wallet spend items (new hierarchy system)
POST   /wallets/{id}/spend-items                            Add a wallet spend item
PUT    /wallets/{id}/spend-items/{item_id}                  Update wallet spend item amount
DELETE /wallets/{id}/spend-items/{item_id}                  Remove a wallet spend item

GET    /wallets/{id}/spend-categories                       List wallet spend categories (legacy)
POST   /wallets/{id}/spend-categories                       Create wallet spend category (legacy)
PUT    /wallets/{id}/spend-categories/{usc_id}              Update wallet spend category (legacy)
DELETE /wallets/{id}/spend-categories/{usc_id}              Delete wallet spend category (legacy)

GET    /wallets/{id}/cards/{card_id}/credits                List wallet card credit overrides
PUT    /wallets/{id}/cards/{card_id}/credits/{lib_id}       Upsert a credit override
DELETE /wallets/{id}/cards/{card_id}/credits/{lib_id}       Remove a credit override

GET    /wallets/{id}/card-multipliers                       List all wallet-level multiplier overrides
PUT    /wallets/{id}/cards/{card_id}/multipliers/{cat_id}   Upsert a multiplier override
DELETE /wallets/{id}/cards/{card_id}/multipliers/{cat_id}   Remove a multiplier override

POST /admin/issuers                                         Create an issuer
POST /admin/currencies                                      Create a currency
POST /admin/spend-categories                                Create a spend category
POST /admin/cards                                           Create a card
DELETE /admin/cards/{id}                                    Delete a card
POST /admin/cards/{id}/multipliers                          Add a card category multiplier
DELETE /admin/cards/{id}/multipliers/{category_id}          Remove a card category multiplier
POST /admin/cards/{id}/credits                              Add a card statement credit
DELETE /admin/cards/{id}/credits/{credit_id}                Remove a card statement credit
"""

from __future__ import annotations

import contextlib
import dataclasses
import json
import logging
import math
import os
from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path
from typing import Literal, Optional, cast

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .calculator import calc_annual_allocated_spend, compute_wallet, plan_sub_targeting
from .constants import ALLOCATION_SUM_TOLERANCE, ALL_OTHER_CATEGORY as ALL_OTHER_SPEND_NAME, DEFAULT_USER_ID
from .database import AsyncSessionLocal, create_tables, get_db

logger = logging.getLogger(__name__)
from .db_helpers import (
    apply_wallet_card_group_selections,
    apply_wallet_card_multiplier_overrides,
    apply_wallet_card_overrides,
    apply_wallet_card_rotation_overrides,
    apply_wallet_portal_shares,
    ensure_all_other_wallet_spend_category,
    ensure_all_other_wallet_spend_item,
    load_card_data,
    load_wallet_card_credits,
    load_wallet_card_group_selections,
    load_wallet_card_multipliers,
    load_wallet_card_rotation_overrides,
    load_wallet_cpp_overrides,
    load_wallet_portal_shares,
    load_wallet_spend,
    load_wallet_spend_items,
)
from .models import (
    Card,
    CardCategoryMultiplier,
    CardCredit,
    CardMultiplierGroup,
    CardRotatingHistory,
    CoBrand,
    Currency,
    Issuer,
    IssuerApplicationRule,
    NetworkTier,
    SpendCategory,
    User,
    Wallet,
    WalletCard,
    WalletCardCredit,
    WalletCardGroupSelection,
    WalletCardMultiplier,
    WalletCardRotationOverride,
    WalletCurrencyBalance,
    WalletCurrencyCpp,
    WalletPortalShare,
    WalletSpendCategory,
    WalletSpendCategoryMapping,
    WalletSpendItem,
)
from .schemas import (
    AdminAddCardCreditPayload,
    AdminAddCardMultiplierPayload,
    AdminAddRotatingHistoryPayload,
    AdminCreateCardMultiplierGroupPayload,
    AdminCreateCardPayload,
    AdminCreateCurrencyPayload,
    AdminCreateIssuerPayload,
    AdminCreateSpendCategoryPayload,
    AdminUpdateCardMultiplierGroupPayload,
    CardMultiplierGroupRead,
    CardRotatingHistoryRead,
    CardCreditRead,
    CardRead,
    WalletPortalSharePayload,
    WalletPortalShareRead,
    WalletRotationOverridePayload,
    WalletRotationOverrideRead,
    CardResultSchema,
    CategoryEarnItem,
    CurrencyRead,
    IssuerApplicationRuleRead,
    IssuerRead,
    RoadmapCardStatus,
    RoadmapResponse,
    RoadmapRuleStatus,
    SpendCategoryRead,
    UpdateCardCreditPayload,
    UpdateCardLibraryPayload,
    WalletCardCreditRead,
    WalletCardCreditUpsert,
    WalletCardCreate,
    WalletCardGroupSelectionRead,
    WalletCardGroupSelectionSet,
    WalletCardMultiplierRead,
    WalletCardMultiplierUpsert,
    WalletCardRead,
    WalletCardUpdate,
    WalletCreate,
    WalletCurrencyCppSet,
    WalletRead,
    WalletResultResponseSchema,
    WalletResultSchema,
    WalletSettingsCurrencyIds,
    WalletSpendCategoryCreate,
    WalletSpendCategoryRead,
    WalletSpendCategoryUpdate,
    WalletSpendItemCreate,
    WalletSpendItemRead,
    WalletSpendItemUpdate,
    WalletUpdate,
    WalletCurrencyBalanceRead,
    WalletCurrencyInitialSet,
    WalletCurrencyTrackCreate,
)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


def _add_months(d: date, months: int) -> date:
    """Add N months to a date, clamping to end of month as needed."""
    month = d.month + months
    year = d.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    day = min(d.day, monthrange(year, month)[1])
    return date(year, month, day)


def _is_sub_earnable(
    sub_min_spend: Optional[int],
    sub_months: Optional[int],
    daily_spend_rate: float,
) -> bool:
    """Return True if the SUB min spend can be reached within the SUB window."""
    if not sub_min_spend:
        return True  # No min spend = always earnable
    if daily_spend_rate <= 0:
        return False
    if not sub_months:
        return True  # No time limit = earnable given enough time
    reachable = daily_spend_rate * (sub_months * 30.44)
    return reachable >= sub_min_spend


def _projected_sub_earn_date(
    added_date: date,
    sub_min_spend: Optional[int],
    sub_months: Optional[int],
    daily_spend_rate: float,
) -> Optional[date]:
    """
    Project the date when the SUB will be earned based on daily spend rate.
    Returns None if not earnable within the SUB window or spend is zero.
    """
    if not sub_min_spend or daily_spend_rate <= 0:
        return None
    days_to_earn = math.ceil(sub_min_spend / daily_spend_rate)
    projected = added_date + timedelta(days=days_to_earn)
    if sub_months:
        window_end = _add_months(added_date, sub_months)
        if projected > window_end:
            return None  # Not earnable within the window
    return projected


def _months_in_half_open_interval(start: date, end: date) -> int:
    """
    Number of calendar months spanned by [start, end) for day-level start/end.
    Same month and day-of-month alignment as relativedelta-style month deltas.
    """
    if end <= start:
        raise ValueError("end must be after start")
    total = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        total -= 1
    return max(1, total)


def _years_counted_from_total_months(total_months: int) -> int:
    full = total_months // 12
    rem = total_months % 12
    return max(1, full + (1 if rem >= 6 else 0))


# ---------------------------------------------------------------------------
# Rotating-bonus card + history seed
# ---------------------------------------------------------------------------
#
# Hardcoded structure for the major rotating-category cards (Discover IT,
# Chase Freedom Flex, Chase Freedom). The seed runs on every startup and is
# idempotent — existing rows are left alone. The seed creates, in order:
#
#   1. Issuers ("Discover", "Chase") if missing
#   2. Currencies ("Discover Cashback Bonus" cash, "Chase UR" points) if missing
#   3. Spend categories referenced by the historical rotation (Wholesale Clubs,
#      Drug Stores, Public Transit, EV Charging, Streaming Services, …) if missing
#   4. Card rows for each rotating card if missing
#   5. A CardMultiplierGroup per card with cap_per_billing_cycle=1500,
#      cap_period_months=3, is_rotating=True, multiplier=5.0, top_n_categories=None
#   6. CardCategoryMultiplier rows linking the group to every category that
#      has ever appeared in that card's historical rotation
#   7. CardRotatingHistory rows for every (year, quarter, category) tuple
#
# Sources: Bankrate, The Points Guy, Reddit summaries linked in commit history.

_DISCOVER_IT_HISTORY: list[tuple[int, int, list[str]]] = [
    # 2023
    (2023, 1, ["Grocery Stores", "Drug Stores", "Streaming Services"]),
    (2023, 2, ["Gas", "Wholesale Clubs"]),
    (2023, 3, ["Restaurants"]),
    (2023, 4, ["Amazon", "Target"]),
    # 2024
    (2024, 1, ["Restaurants", "Drug Stores"]),
    (2024, 2, ["Gas", "Public Transit", "Utilities"]),
    (2024, 3, ["Restaurants"]),
    (2024, 4, ["Amazon", "Target"]),
    # 2025
    (2025, 1, ["Restaurants", "Home Improvement", "Streaming Services"]),
    (2025, 2, ["Gas", "Public Transit", "EV Charging"]),
    (2025, 3, ["Restaurants"]),
    (2025, 4, ["Amazon", "Target"]),
]

_CHASE_FREEDOM_FLEX_HISTORY: list[tuple[int, int, list[str]]] = [
    # 2023
    (2023, 1, ["Grocery Stores", "Fitness Clubs"]),
    (2023, 2, ["Amazon", "Lowe's"]),
    (2023, 3, ["Gas", "EV Charging", "Movies"]),
    (2023, 4, ["PayPal", "Wholesale Clubs"]),
    # 2024
    (2024, 1, ["Grocery Stores", "Fitness Clubs"]),
    (2024, 2, ["Hotels", "Restaurants"]),
    (2024, 3, ["Gas", "EV Charging", "Movies"]),
    (2024, 4, ["PayPal", "McDonald's"]),
    # 2025
    (2025, 1, ["Grocery Stores", "Fitness Clubs"]),
    (2025, 2, ["Hotels", "Amazon"]),
    (2025, 3, ["Gas", "EV Charging", "Restaurants"]),
    (2025, 4, ["PayPal", "Wholesale Clubs"]),
]

# Chase Freedom (legacy, no longer issued) shared rotations with Freedom Flex
# pre-2021. Anyone still holding one would use the same recent rotations.
_CHASE_FREEDOM_HISTORY = _CHASE_FREEDOM_FLEX_HISTORY


# Static card definitions. Currencies are looked up by exact name first, then
# fall back through the alias list — adapts to whatever the user named their
# Chase UR / Discover Cashback currency rows.
#
# rotating_group_multiplier and rotating_is_additive control how the rotating
# group is materialized. For non-additive cards (Discover IT, legacy Freedom)
# the multiplier is the *full* rate (5x). For additive cards (Freedom Flex)
# the multiplier is a *premium* (4x) that stacks onto the card's base + any
# always-on premiums on the same category, so dining-during-restaurants-Q
# earns 1 (base) + 2 (always-on dining premium) + 4 (rotating premium) = 7x.
#
# always_on_premiums is a list of (category_name, premium_value, is_portal)
# tuples that get materialized as STANDALONE additive CardCategoryMultiplier
# rows on the card. Each premium adds onto the card's base for the matching
# category. Categories that don't yet exist as SpendCategory rows are
# auto-created.
_ROTATING_CARD_SPECS: list[dict] = [
    {
        "name": "Discover it Cash Back",
        "issuer": "Discover",
        "currency_aliases": ["Discover Cashback Bonus", "Discover Cashback", "Cash"],
        "currency_default_kind": "cash",
        "currency_default_cpp": 1.0,
        "annual_fee": 0.0,
        "first_year_fee": None,
        "business": False,
        "history": _DISCOVER_IT_HISTORY,
        "rotating_group_multiplier": 5.0,
        "rotating_is_additive": False,
        "always_on_premiums": [],
    },
    {
        "name": "Chase Freedom Flex",
        "issuer": "Chase",
        "currency_aliases": ["Chase Ultimate Rewards", "Chase UR", "Chase Cash", "Cash"],
        "currency_default_kind": "points",
        "currency_default_cpp": 1.0,
        "annual_fee": 0.0,
        "first_year_fee": None,
        "business": False,
        "history": _CHASE_FREEDOM_FLEX_HISTORY,
        # Rotating premium = 4x (advertised 5x = 1 base + 4 premium).
        "rotating_group_multiplier": 4.0,
        "rotating_is_additive": True,
        # Permanent additive premiums on top of the 1x base:
        #   Restaurants +2x → 3x always-on (advertised "3% on dining")
        #   Drug Stores +2x → 3x always-on (advertised "3% on drugstores")
        #   Travel      +4x → 5x portal-only (advertised "5% on Chase Travel")
        # Travel is_portal=True so the calculator's portal-share path
        # (Phase B) gates the +4 to the configured Chase Travel share.
        "always_on_premiums": [
            ("Restaurants", 2.0, False),
            ("Drug Stores", 2.0, False),
            ("Travel", 4.0, True),
        ],
    },
    {
        "name": "Chase Freedom",
        "issuer": "Chase",
        "currency_aliases": ["Chase Ultimate Rewards", "Chase UR", "Chase Cash", "Cash"],
        "currency_default_kind": "points",
        "currency_default_cpp": 1.0,
        "annual_fee": 0.0,
        "first_year_fee": None,
        "business": False,
        "history": _CHASE_FREEDOM_HISTORY,
        "rotating_group_multiplier": 5.0,
        "rotating_is_additive": False,
        "always_on_premiums": [],
    },
]


async def _ensure_issuer(session, name: str) -> Issuer:
    from sqlalchemy import func

    row = await session.execute(
        select(Issuer).where(func.lower(Issuer.name) == name.lower())
    )
    obj = row.scalar_one_or_none()
    if obj is not None:
        return obj
    obj = Issuer(name=name)
    session.add(obj)
    await session.flush()
    logger.info("rotating seed: created issuer %r", name)
    return obj


async def _ensure_currency(
    session,
    aliases: list[str],
    default_kind: str,
    default_cpp: float,
) -> Currency:
    from sqlalchemy import func

    for alias in aliases:
        row = await session.execute(
            select(Currency).where(func.lower(Currency.name) == alias.lower())
        )
        obj = row.scalar_one_or_none()
        if obj is not None:
            return obj
    # None of the aliases exist; create the canonical (first alias).
    canonical = aliases[0]
    obj = Currency(
        name=canonical,
        reward_kind=default_kind,
        cents_per_point=default_cpp,
        cash_transfer_rate=1.0 if default_kind == "cash" else None,
    )
    session.add(obj)
    await session.flush()
    logger.info("rotating seed: created currency %r (%s)", canonical, default_kind)
    return obj


async def _ensure_spend_category(session, name: str) -> SpendCategory:
    from sqlalchemy import func

    row = await session.execute(
        select(SpendCategory).where(func.lower(SpendCategory.category) == name.lower())
    )
    obj = row.scalar_one_or_none()
    if obj is not None:
        return obj
    obj = SpendCategory(category=name, is_system=False)
    session.add(obj)
    await session.flush()
    logger.info("rotating seed: created spend category %r", name)
    return obj


async def _seed_rotating_cards_and_history() -> None:
    """
    Idempotently materialize the rotating-card universe: issuers, currencies,
    spend categories, the Card rows themselves, their rotating multiplier
    groups, and the (year, quarter, category) history rows.

    Every step skips work that's already been done. Safe to run on every
    startup. Each card's seed runs in its own transaction so a failure on one
    card doesn't roll back the others.
    """
    async with AsyncSessionLocal() as session:
        for spec in _ROTATING_CARD_SPECS:
            try:
                await _seed_one_rotating_card(session, spec)
                await session.commit()
            except Exception:
                logger.exception(
                    "rotating seed: failed to seed %r — rolling back this card",
                    spec["name"],
                )
                await session.rollback()
                continue


async def _seed_one_rotating_card(session, spec: dict) -> None:
    from sqlalchemy import func

    # 1. Issuer
    issuer = await _ensure_issuer(session, spec["issuer"])

    # 2. Currency
    currency = await _ensure_currency(
        session,
        spec["currency_aliases"],
        spec["currency_default_kind"],
        spec["currency_default_cpp"],
    )

    # 3. Spend categories — collect the universe from the history.
    universe_names: list[str] = []
    seen: set[str] = set()
    for _y, _q, cats in spec["history"]:
        for cat_name in cats:
            key = cat_name.strip().lower()
            if key not in seen:
                seen.add(key)
                universe_names.append(cat_name)

    universe_categories: list[SpendCategory] = []
    for cat_name in universe_names:
        sc = await _ensure_spend_category(session, cat_name)
        universe_categories.append(sc)

    # 4. Card row
    card_row = await session.execute(
        select(Card).where(func.lower(Card.name) == spec["name"].lower())
    )
    card = card_row.scalar_one_or_none()
    if card is None:
        card = Card(
            name=spec["name"],
            issuer_id=issuer.id,
            currency_id=currency.id,
            annual_fee=spec["annual_fee"],
            first_year_fee=spec["first_year_fee"],
            business=spec["business"],
        )
        session.add(card)
        await session.flush()
        logger.info("rotating seed: created card %r", spec["name"])

    # 5. Rotating multiplier group — find existing or create. Synchronize the
    # multiplier value and is_additive flag from the spec so existing seeded
    # groups switch to additive mode on next startup if the spec changes.
    rotating_group_mult = float(spec.get("rotating_group_multiplier", 5.0))
    rotating_is_additive = bool(spec.get("rotating_is_additive", False))
    existing_groups = await session.execute(
        select(CardMultiplierGroup).where(
            CardMultiplierGroup.card_id == card.id,
            CardMultiplierGroup.is_rotating == True,  # noqa: E712
        )
    )
    group = existing_groups.scalars().first()
    if group is None:
        group = CardMultiplierGroup(
            card_id=card.id,
            multiplier=rotating_group_mult,
            cap_per_billing_cycle=1500.0,
            cap_period_months=3,
            is_rotating=True,
            is_additive=rotating_is_additive,
            top_n_categories=None,
        )
        session.add(group)
        await session.flush()
        logger.info(
            "rotating seed: created rotating group on %r (%sx, additive=%s)",
            card.name, rotating_group_mult, rotating_is_additive,
        )
    else:
        # Sync spec → existing row in case the spec changed.
        if abs(group.multiplier - rotating_group_mult) > 1e-6:
            group.multiplier = rotating_group_mult
        if bool(group.is_additive) != rotating_is_additive:
            group.is_additive = rotating_is_additive

    # 6. Group category memberships — one CardCategoryMultiplier per universe
    # category, linked to the rotating group. The standalone always-on premium
    # rows (added in step 6b) live as separate rows on the same (card, category)
    # pair, allowed by the partial unique indexes from migration 024.
    existing_grouped = await session.execute(
        select(CardCategoryMultiplier).where(
            CardCategoryMultiplier.card_id == card.id,
            CardCategoryMultiplier.multiplier_group_id == group.id,
        )
    )
    grouped_by_cat_id = {m.category_id: m for m in existing_grouped.scalars()}
    for sc in universe_categories:
        existing = grouped_by_cat_id.get(sc.id)
        if existing is None:
            session.add(
                CardCategoryMultiplier(
                    card_id=card.id,
                    category_id=sc.id,
                    multiplier=rotating_group_mult,
                    multiplier_group_id=group.id,
                    is_additive=rotating_is_additive,
                )
            )
            logger.info(
                "rotating seed: linked %r → %r in rotating group",
                card.name, sc.category,
            )
        else:
            # Sync existing rows so spec changes propagate (e.g., switching
            # Freedom Flex from non-additive 5x to additive 4x premium).
            if abs(existing.multiplier - rotating_group_mult) > 1e-6:
                existing.multiplier = rotating_group_mult
            if bool(existing.is_additive) != rotating_is_additive:
                existing.is_additive = rotating_is_additive
    await session.flush()

    # 6b. Always-on additive premiums — Freedom Flex's permanent +2 dining,
    # +2 drugstores, +4 portal travel etc. Each row is a STANDALONE
    # (multiplier_group_id IS NULL) is_additive=True CardCategoryMultiplier.
    always_on: list[tuple[str, float, bool]] = list(spec.get("always_on_premiums", []))
    if always_on:
        # Pull existing standalone rows for this card so we can update or skip.
        existing_standalone = await session.execute(
            select(CardCategoryMultiplier).where(
                CardCategoryMultiplier.card_id == card.id,
                CardCategoryMultiplier.multiplier_group_id.is_(None),
            )
        )
        standalone_by_cat_id = {m.category_id: m for m in existing_standalone.scalars()}
        for cat_name, premium, is_portal in always_on:
            sc = await _ensure_spend_category(session, cat_name)
            existing = standalone_by_cat_id.get(sc.id)
            if existing is None:
                session.add(
                    CardCategoryMultiplier(
                        card_id=card.id,
                        category_id=sc.id,
                        multiplier=float(premium),
                        is_additive=True,
                        is_portal=bool(is_portal),
                        multiplier_group_id=None,
                    )
                )
                logger.info(
                    "rotating seed: added always-on +%sx %r on %r%s",
                    premium, cat_name, card.name, " (portal)" if is_portal else "",
                )
            else:
                # Only sync if the existing row is also additive — never
                # clobber a user-set non-additive standalone.
                if existing.is_additive:
                    if abs(existing.multiplier - float(premium)) > 1e-6:
                        existing.multiplier = float(premium)
                    if bool(existing.is_portal) != bool(is_portal):
                        existing.is_portal = bool(is_portal)
        await session.flush()

    # 7. History rows
    sc_by_lower_name = {sc.category.lower(): sc.id for sc in universe_categories}
    existing_history = await session.execute(
        select(
            CardRotatingHistory.year,
            CardRotatingHistory.quarter,
            CardRotatingHistory.spend_category_id,
        ).where(CardRotatingHistory.card_id == card.id)
    )
    existing_keys = {(r[0], r[1], r[2]) for r in existing_history.all()}
    for year, quarter, cat_names in spec["history"]:
        for cat_name in cat_names:
            sc_id = sc_by_lower_name.get(cat_name.lower())
            if sc_id is None:
                continue
            key = (year, quarter, sc_id)
            if key in existing_keys:
                continue
            session.add(
                CardRotatingHistory(
                    card_id=card.id,
                    year=year,
                    quarter=quarter,
                    spend_category_id=sc_id,
                )
            )


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    try:
        await _seed_rotating_cards_and_history()
    except Exception:  # pragma: no cover — defensive
        logger.exception("rotating seed failed")
    yield


app = FastAPI(
    title="Credit Card Optimizer API",
    description="Credit card wallet optimizer — fees, points, credits, and SUB opportunity cost.",
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
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ---------------------------------------------------------------------------
# Common 404 helpers
# ---------------------------------------------------------------------------


def _card_404(card_id: int) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Card {card_id} not found")


def _wallet_404(wallet_id: int) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Wallet {wallet_id} not found")


def _wc_read(wc: WalletCard, card: Card) -> WalletCardRead:
    """
    Build a WalletCardRead for API responses.

    SUB and fee fields fall back to the library Card when the wallet row stores
    null (inherit defaults). The database row is unchanged; only the read model
    exposes effective values for clients.
    """
    def _inh(wv, cv):
        return wv if wv is not None else cv

    return WalletCardRead(
        id=wc.id,
        wallet_id=wc.wallet_id,
        card_id=wc.card_id,
        card_name=card.name,
        transfer_enabler=bool(getattr(card, "transfer_enabler", False)),
        added_date=wc.added_date,
        sub=_inh(wc.sub, card.sub),
        sub_min_spend=_inh(wc.sub_min_spend, card.sub_min_spend),
        sub_months=_inh(wc.sub_months, card.sub_months),
        sub_spend_earn=_inh(wc.sub_spend_earn, card.sub_spend_earn),
        annual_bonus=_inh(wc.annual_bonus, card.annual_bonus),
        years_counted=wc.years_counted,
        annual_fee=_inh(wc.annual_fee, card.annual_fee),
        first_year_fee=_inh(wc.first_year_fee, card.first_year_fee),
        sub_earned_date=wc.sub_earned_date,
        sub_projected_earn_date=wc.sub_projected_earn_date,
        closed_date=wc.closed_date,
        acquisition_type=cast(Literal["opened", "product_change"], wc.acquisition_type),
        panel=cast(Literal["on_deck", "in_wallet"], wc.panel),
    )


# ---------------------------------------------------------------------------
# Card selectinload options (reused across endpoints)
# ---------------------------------------------------------------------------


def _card_load_opts():
    return [
        selectinload(Card.issuer),
        selectinload(Card.co_brand),
        selectinload(Card.currency_obj),
        selectinload(Card.currency_obj).selectinload(Currency.converts_to_currency),
        selectinload(Card.network_tier),
        selectinload(Card.multipliers).selectinload(CardCategoryMultiplier.spend_category),
        selectinload(Card.multiplier_groups).selectinload(CardMultiplierGroup.categories).selectinload(CardCategoryMultiplier.spend_category),
        selectinload(Card.rotating_history).selectinload(CardRotatingHistory.spend_category),
        selectinload(Card.credits),
    ]


def _wallet_load_opts():
    return [
        selectinload(Wallet.wallet_cards).selectinload(WalletCard.card),
    ]


# ---------------------------------------------------------------------------
# Issuers
# ---------------------------------------------------------------------------


@app.get("/issuers", response_model=list[IssuerRead], tags=["issuers"])
async def list_issuers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Issuer).order_by(Issuer.name))
    return result.scalars().all()


@app.get("/issuers/application-rules", response_model=list[IssuerApplicationRuleRead], tags=["issuers"])
async def list_issuer_application_rules(db: AsyncSession = Depends(get_db)):
    """List all known issuer velocity/eligibility rules (e.g. Chase 5/24, Amex 1/90)."""
    result = await db.execute(
        select(IssuerApplicationRule)
        .options(selectinload(IssuerApplicationRule.issuer))
        .order_by(IssuerApplicationRule.issuer_id, IssuerApplicationRule.rule_name)
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Currencies
# ---------------------------------------------------------------------------


@app.get("/currencies", response_model=list[CurrencyRead], tags=["currencies"])
async def list_currencies(db: AsyncSession = Depends(get_db)):
    """List all currencies."""
    result = await db.execute(
        select(Currency)
        .options(
            selectinload(Currency.converts_to_currency),
        )
        .order_by(Currency.name)
    )
    return result.scalars().all()



# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------


@app.get("/cards", response_model=list[CardRead], tags=["cards"])
async def list_cards(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Card).options(*_card_load_opts()))
    return result.scalars().all()


_CARD_LIBRARY_PATCH_FIELDS = frozenset(
    {"sub", "sub_min_spend", "sub_months", "annual_fee", "first_year_fee", "transfer_enabler"}
)


@app.patch("/cards/{card_id}", response_model=CardRead, tags=["cards"])
async def update_card_library(
    card_id: int,
    payload: UpdateCardLibraryPayload,
    db: AsyncSession = Depends(get_db),
):
    """Update editable card library fields (SUB, min spend, months, fees)."""
    result = await db.execute(select(Card).where(Card.id == card_id))
    card = result.scalar_one_or_none()
    if not card:
        raise _card_404(card_id)
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    for key, value in data.items():
        if key not in _CARD_LIBRARY_PATCH_FIELDS:
            continue
        setattr(card, key, value)
    await db.commit()
    refreshed = await db.execute(
        select(Card).where(Card.id == card_id).options(*_card_load_opts())
    )
    return refreshed.scalar_one()


@app.patch(
    "/cards/{card_id}/credits/{credit_id}",
    response_model=CardCreditRead,
    tags=["cards"],
)
async def update_card_credit(
    card_id: int,
    credit_id: int,
    payload: UpdateCardCreditPayload,
    db: AsyncSession = Depends(get_db),
):
    """Update statement credit value, label, and/or one-time vs annual flag (library-wide)."""
    result = await db.execute(
        select(CardCredit).where(
            CardCredit.id == credit_id,
            CardCredit.card_id == card_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credit not found for this card",
        )
    if payload.credit_value is not None:
        row.credit_value = payload.credit_value
    if payload.is_one_time is not None:
        row.is_one_time = payload.is_one_time
    if payload.credit_name is not None:
        new_name = payload.credit_name.strip()
        if not new_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="credit_name cannot be empty",
            )
        if new_name != row.credit_name:
            clash = await db.execute(
                select(CardCredit).where(
                    CardCredit.card_id == card_id,
                    CardCredit.credit_name == new_name,
                    CardCredit.id != credit_id,
                )
            )
            if clash.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Credit name {new_name!r} already exists on this card",
                )
        row.credit_name = new_name
    await db.commit()
    await db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Spend categories
# ---------------------------------------------------------------------------


@app.get("/spend", response_model=list[SpendCategoryRead], tags=["spend"])
async def list_spend(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SpendCategory).order_by(SpendCategory.category))
    return result.scalars().all()


@app.get(
    "/app-spend-categories",
    response_model=list[SpendCategoryRead],
    tags=["spend"],
)
async def list_app_spend_categories(db: AsyncSession = Depends(get_db)):
    """Return top-level spend categories with their children nested (excludes system catch-all)."""
    result = await db.execute(
        select(SpendCategory)
        .options(
            selectinload(SpendCategory.children).selectinload(SpendCategory.children),
        )
        .where(SpendCategory.parent_id == None, SpendCategory.is_system == False)  # noqa: E711,E712
        .order_by(SpendCategory.category)
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Wallet spend categories (wallet-scoped, replaces user-scoped)
# ---------------------------------------------------------------------------


@app.get(
    "/wallets/{wallet_id}/spend-categories",
    response_model=list[WalletSpendCategoryRead],
    tags=["wallet-spend"],
)
async def list_wallet_spend_categories(
    wallet_id: int,
    db: AsyncSession = Depends(get_db),
):
    """List all wallet spend categories with their card category mappings."""
    wallet_result = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
    if not wallet_result.scalar_one_or_none():
        raise _wallet_404(wallet_id)
    await ensure_all_other_wallet_spend_category(db, wallet_id)
    await db.commit()
    result = await db.execute(
        select(WalletSpendCategory)
        .options(
            selectinload(WalletSpendCategory.mappings).selectinload(WalletSpendCategoryMapping.spend_category)
        )
        .where(WalletSpendCategory.wallet_id == wallet_id)
        .order_by(WalletSpendCategory.name)
    )
    return result.scalars().all()


@app.post(
    "/wallets/{wallet_id}/spend-categories",
    response_model=WalletSpendCategoryRead,
    status_code=status.HTTP_201_CREATED,
    tags=["wallet-spend"],
)
async def create_wallet_spend_category(
    wallet_id: int,
    payload: WalletSpendCategoryCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a wallet spend category with optional card category mappings."""
    wallet_result = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
    if not wallet_result.scalar_one_or_none():
        raise _wallet_404(wallet_id)

    existing = await db.execute(
        select(WalletSpendCategory).where(
            WalletSpendCategory.wallet_id == wallet_id,
            WalletSpendCategory.name == payload.name.strip(),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Spend category '{payload.name}' already exists")

    if payload.name.strip() == ALL_OTHER_SPEND_NAME:
        raise HTTPException(
            status_code=403,
            detail=f"'{ALL_OTHER_SPEND_NAME}' is a reserved system category",
        )

    wsc = WalletSpendCategory(wallet_id=wallet_id, name=payload.name.strip(), amount=payload.amount)
    db.add(wsc)
    await db.flush()

    for m in payload.mappings:
        sc_result = await db.execute(select(SpendCategory).where(SpendCategory.id == m.spend_category_id))
        if not sc_result.scalar_one_or_none():
            raise HTTPException(status_code=422, detail=f"SpendCategory id={m.spend_category_id} not found")
        db.add(WalletSpendCategoryMapping(
            wallet_spend_category_id=wsc.id,
            spend_category_id=m.spend_category_id,
            allocation=m.allocation,
        ))

    await db.commit()
    result = await db.execute(
        select(WalletSpendCategory)
        .options(selectinload(WalletSpendCategory.mappings).selectinload(WalletSpendCategoryMapping.spend_category))
        .where(WalletSpendCategory.id == wsc.id)
    )
    return result.scalar_one()


@app.put(
    "/wallets/{wallet_id}/spend-categories/{wsc_id}",
    response_model=WalletSpendCategoryRead,
    tags=["wallet-spend"],
)
async def update_wallet_spend_category(
    wallet_id: int,
    wsc_id: int,
    payload: WalletSpendCategoryUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a wallet spend category's name, amount, or card category mappings."""
    result = await db.execute(
        select(WalletSpendCategory)
        .options(selectinload(WalletSpendCategory.mappings))
        .where(WalletSpendCategory.id == wsc_id, WalletSpendCategory.wallet_id == wallet_id)
    )
    wsc = result.scalar_one_or_none()
    if not wsc:
        raise HTTPException(status_code=404, detail=f"Wallet spend category {wsc_id} not found")

    locked = wsc.name == ALL_OTHER_SPEND_NAME
    if locked:
        if payload.name is not None and payload.name.strip() != ALL_OTHER_SPEND_NAME:
            raise HTTPException(
                status_code=403,
                detail=f"The '{ALL_OTHER_SPEND_NAME}' category cannot be renamed",
            )
        if payload.mappings is not None:
            raise HTTPException(
                status_code=403,
                detail=f"Mappings for '{ALL_OTHER_SPEND_NAME}' cannot be changed",
            )

    if payload.name is not None:
        new_name = payload.name.strip()
        if new_name != wsc.name:
            dup = await db.execute(
                select(WalletSpendCategory).where(
                    WalletSpendCategory.wallet_id == wallet_id,
                    WalletSpendCategory.name == new_name,
                    WalletSpendCategory.id != wsc_id,
                )
            )
            if dup.scalar_one_or_none():
                raise HTTPException(status_code=409, detail=f"Spend category '{new_name}' already exists")
        wsc.name = new_name

    if payload.amount is not None:
        wsc.amount = payload.amount

    if payload.mappings is not None:
        effective_amount = wsc.amount
        total_alloc = sum(m.allocation for m in payload.mappings)
        if payload.mappings and abs(total_alloc - effective_amount) > ALLOCATION_SUM_TOLERANCE:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Mapping allocations must sum to annual amount ${effective_amount:.2f} "
                    f"(got ${total_alloc:.2f})"
                ),
            )
        for m in list(wsc.mappings):
            await db.delete(m)
        await db.flush()
        for m in payload.mappings:
            sc_result = await db.execute(select(SpendCategory).where(SpendCategory.id == m.spend_category_id))
            if not sc_result.scalar_one_or_none():
                raise HTTPException(status_code=422, detail=f"SpendCategory id={m.spend_category_id} not found")
            db.add(WalletSpendCategoryMapping(
                wallet_spend_category_id=wsc.id,
                spend_category_id=m.spend_category_id,
                allocation=m.allocation,
            ))

    await db.commit()
    result = await db.execute(
        select(WalletSpendCategory)
        .options(selectinload(WalletSpendCategory.mappings).selectinload(WalletSpendCategoryMapping.spend_category))
        .where(WalletSpendCategory.id == wsc_id)
    )
    return result.scalar_one()


@app.delete(
    "/wallets/{wallet_id}/spend-categories/{wsc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["wallet-spend"],
)
async def delete_wallet_spend_category(
    wallet_id: int,
    wsc_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WalletSpendCategory).where(
            WalletSpendCategory.id == wsc_id,
            WalletSpendCategory.wallet_id == wallet_id,
        )
    )
    wsc = result.scalar_one_or_none()
    if not wsc:
        raise HTTPException(status_code=404, detail=f"Wallet spend category {wsc_id} not found")
    if wsc.name == ALL_OTHER_SPEND_NAME:
        raise HTTPException(
            status_code=403,
            detail=f"The '{ALL_OTHER_SPEND_NAME}' category cannot be deleted",
        )
    await db.delete(wsc)
    await db.commit()


# ---------------------------------------------------------------------------
# Wallet spend items (new app-level hierarchy system)
# ---------------------------------------------------------------------------


def _load_spend_item_opts():
    return [
        selectinload(WalletSpendItem.spend_category).selectinload(SpendCategory.children).selectinload(SpendCategory.children),
    ]


@app.get(
    "/wallets/{wallet_id}/spend-items",
    response_model=list[WalletSpendItemRead],
    tags=["wallet-spend"],
)
async def list_wallet_spend_items(
    wallet_id: int,
    db: AsyncSession = Depends(get_db),
):
    """List wallet spend items. Auto-creates the 'All Other' item if missing."""
    wallet_result = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
    if not wallet_result.scalar_one_or_none():
        raise _wallet_404(wallet_id)
    await ensure_all_other_wallet_spend_item(db, wallet_id)
    await db.commit()
    result = await db.execute(
        select(WalletSpendItem)
        .options(*_load_spend_item_opts())
        .where(WalletSpendItem.wallet_id == wallet_id)
        .join(WalletSpendItem.spend_category)
        .order_by(WalletSpendItem.amount.desc(), SpendCategory.category)
    )
    return result.scalars().all()


@app.post(
    "/wallets/{wallet_id}/spend-items",
    response_model=WalletSpendItemRead,
    status_code=status.HTTP_201_CREATED,
    tags=["wallet-spend"],
)
async def create_wallet_spend_item(
    wallet_id: int,
    payload: WalletSpendItemCreate,
    db: AsyncSession = Depends(get_db),
):
    """Add a spend item to a wallet for a given app spend category."""
    wallet_result = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
    if not wallet_result.scalar_one_or_none():
        raise _wallet_404(wallet_id)

    sc_result = await db.execute(
        select(SpendCategory).where(SpendCategory.id == payload.spend_category_id)
    )
    sc = sc_result.scalar_one_or_none()
    if not sc:
        raise HTTPException(status_code=422, detail=f"SpendCategory id={payload.spend_category_id} not found")
    if sc.is_system:
        raise HTTPException(status_code=403, detail=f"'{sc.category}' is a system category; update its amount via PUT instead")

    existing = await db.execute(
        select(WalletSpendItem).where(
            WalletSpendItem.wallet_id == wallet_id,
            WalletSpendItem.spend_category_id == payload.spend_category_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"A spend item for '{sc.category}' already exists in this wallet")

    item = WalletSpendItem(
        wallet_id=wallet_id,
        spend_category_id=payload.spend_category_id,
        amount=payload.amount,
    )
    db.add(item)
    await db.commit()
    result = await db.execute(
        select(WalletSpendItem)
        .options(*_load_spend_item_opts())
        .where(WalletSpendItem.id == item.id)
    )
    return result.scalar_one()


@app.put(
    "/wallets/{wallet_id}/spend-items/{item_id}",
    response_model=WalletSpendItemRead,
    tags=["wallet-spend"],
)
async def update_wallet_spend_item(
    wallet_id: int,
    item_id: int,
    payload: WalletSpendItemUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update the annual spend amount for a wallet spend item."""
    result = await db.execute(
        select(WalletSpendItem).where(
            WalletSpendItem.id == item_id,
            WalletSpendItem.wallet_id == wallet_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail=f"Spend item {item_id} not found")
    item.amount = payload.amount
    await db.commit()
    result = await db.execute(
        select(WalletSpendItem)
        .options(*_load_spend_item_opts())
        .where(WalletSpendItem.id == item_id)
    )
    return result.scalar_one()


@app.delete(
    "/wallets/{wallet_id}/spend-items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["wallet-spend"],
)
async def delete_wallet_spend_item(
    wallet_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Remove a spend item from a wallet. The 'All Other' item cannot be deleted."""
    result = await db.execute(
        select(WalletSpendItem)
        .options(selectinload(WalletSpendItem.spend_category))
        .where(WalletSpendItem.id == item_id, WalletSpendItem.wallet_id == wallet_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail=f"Spend item {item_id} not found")
    if item.spend_category and item.spend_category.is_system:
        raise HTTPException(
            status_code=403,
            detail=f"The '{item.spend_category.category}' item cannot be deleted",
        )
    await db.delete(item)
    await db.commit()


# ---------------------------------------------------------------------------
# Wallets (Wallet Tool)
# ---------------------------------------------------------------------------

@app.get("/wallets", response_model=list[WalletRead], tags=["wallets"])
async def list_wallets(
    user_id: int = DEFAULT_USER_ID,
    db: AsyncSession = Depends(get_db),
):
    """List wallets for the given user (default user_id=1 for single-tenant)."""
    result = await db.execute(
        select(Wallet)
        .options(*_wallet_load_opts())
        .where(Wallet.user_id == user_id)
        .order_by(Wallet.id)
    )
    wallets = result.scalars().all()
    # Populate card_name on each WalletCardRead for response
    out = []
    for w in wallets:
        read = WalletRead.model_validate(w)
        read.wallet_cards = [_wc_read(wc, wc.card) for wc in w.wallet_cards]
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
    await db.flush()
    await ensure_all_other_wallet_spend_category(db, wallet.id)
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
        .options(*_wallet_load_opts())
        .where(Wallet.id == wallet_id)
    )
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise _wallet_404(wallet_id)
    read = WalletRead.model_validate(wallet)
    read.wallet_cards = [_wc_read(wc, wc.card) for wc in wallet.wallet_cards]
    return read


@app.patch(
    "/wallets/{wallet_id}", response_model=WalletRead, tags=["wallets"]
)
async def update_wallet(
    wallet_id: int, payload: WalletUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Wallet)
        .options(*_wallet_load_opts())
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
    read.wallet_cards = [_wc_read(wc, wc.card) for wc in wallet.wallet_cards]
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
        sub=payload.sub,
        sub_min_spend=payload.sub_min_spend,
        sub_months=payload.sub_months,
        sub_spend_earn=payload.sub_spend_earn,
        annual_bonus=payload.annual_bonus,
        years_counted=payload.years_counted,
        annual_fee=payload.annual_fee,
        first_year_fee=payload.first_year_fee,
        sub_earned_date=payload.sub_earned_date,
        closed_date=payload.closed_date,
        acquisition_type=payload.acquisition_type,
        panel=payload.panel,
    )
    db.add(wc)
    await db.flush()
    await _ensure_wallet_currency_rows_for_earning_currencies(db, wallet_id)
    await db.commit()
    await db.refresh(wc)
    return _wc_read(wc, card)


@app.patch(
    "/wallets/{wallet_id}/cards/{card_id}",
    response_model=WalletCardRead,
    tags=["wallets"],
)
async def update_wallet_card(
    wallet_id: int,
    card_id: int,
    payload: WalletCardUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Partially update a wallet card. Supports updating SUB overrides, years_counted,
    sub_earned_date (mark when the SUB was earned), and closed_date (mark card as closed).
    Use sub_earned_date=null in the JSON body to clear the earned date.
    """
    result = await db.execute(
        select(WalletCard).where(
            WalletCard.wallet_id == wallet_id,
            WalletCard.card_id == card_id,
        )
    )
    wc = result.scalar_one_or_none()
    if not wc:
        raise HTTPException(
            status_code=404, detail=f"Card {card_id} not in wallet {wallet_id}"
        )
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(wc, field, value)

    await db.commit()
    await db.refresh(wc)
    card_result = await db.execute(select(Card).where(Card.id == wc.card_id))
    card = card_result.scalar_one()
    return _wc_read(wc, card)


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
    await db.flush()

    # Clean up currency balance rows for currencies no longer earned by any remaining card.
    remaining_currency_ids = await _effective_earn_currency_ids_for_wallet(db, wallet_id)
    balance_q = select(WalletCurrencyBalance).where(
        WalletCurrencyBalance.wallet_id == wallet_id,
    )
    if remaining_currency_ids:
        balance_q = balance_q.where(
            WalletCurrencyBalance.currency_id.not_in(remaining_currency_ids)
        )
    orphaned_balances = await db.execute(balance_q)
    for balance_row in orphaned_balances.scalars().all():
        await db.delete(balance_row)

    await db.commit()


async def _effective_earn_currency_ids_for_wallet(
    db: AsyncSession,
    wallet_id: int,
) -> set[int]:
    """
    Currency IDs this wallet's in-wallet cards effectively earn (upgrade rule
    matches calculator: e.g. UR Cash → UR when a UR card is also in the wallet).
    On-deck cards are excluded — only cards actively in the wallet count.
    """
    result = await db.execute(
        select(WalletCard)
        .options(
            selectinload(WalletCard.card)
            .selectinload(Card.currency_obj)
            .selectinload(Currency.converts_to_currency),
        )
        .where(WalletCard.wallet_id == wallet_id, WalletCard.panel == "in_wallet")
    )
    wcs = list(result.scalars().all())
    if not wcs:
        return set()

    wallet_currency_ids = {wc.card.currency_id for wc in wcs}
    effective_ids: set[int] = set()
    for wc in wcs:
        cur = wc.card.currency_obj
        conv = cur.converts_to_currency
        if conv is not None and conv.id in wallet_currency_ids:
            effective_ids.add(conv.id)
        else:
            effective_ids.add(cur.id)
    return effective_ids


async def _ensure_wallet_currency_rows_for_earning_currencies(
    db: AsyncSession,
    wallet_id: int,
) -> None:
    """
    Create WalletCurrencyBalance rows (if missing) for each effective earn currency
    for cards in this wallet — same upgrade rule as the calculator (e.g. UR Cash → UR
    when a UR card is also in the wallet).
    """
    effective_ids = await _effective_earn_currency_ids_for_wallet(db, wallet_id)
    if not effective_ids:
        return

    today = date.today()
    for cid in effective_ids:
        ex = await db.execute(
            select(WalletCurrencyBalance).where(
                WalletCurrencyBalance.wallet_id == wallet_id,
                WalletCurrencyBalance.currency_id == cid,
            )
        )
        if ex.scalar_one_or_none():
            continue
        db.add(
            WalletCurrencyBalance(
                wallet_id=wallet_id,
                currency_id=cid,
                initial_balance=0.0,
                projection_earn=0.0,
                balance=0.0,
                user_tracked=False,
                updated_date=today,
            )
        )


async def _sync_wallet_balances_from_currency_pts(
    db: AsyncSession,
    wallet_id: int,
    currency_pts_by_id: dict[int, float],
) -> None:
    """
    Persist projection-period earn per currency and set balance = initial + earn.
    Keys are currency ids (same as calculator effective earn). Existing rows get
    projection_earn updated from the latest calculate; new rows are created for
    positive earn not yet present.

    Non-user-tracked balance rows for currencies no longer earned by any
    in-wallet card are removed so they don't clutter the currencies list.
    """
    today = date.today()
    valid_ids = set((await db.execute(select(Currency.id))).scalars().all())
    active_currency_ids = await _effective_earn_currency_ids_for_wallet(db, wallet_id)

    res = await db.execute(
        select(WalletCurrencyBalance)
        .options(selectinload(WalletCurrencyBalance.currency))
        .where(WalletCurrencyBalance.wallet_id == wallet_id)
    )
    rows = list(res.scalars().all())
    by_cid = {r.currency_id: r for r in rows}

    for row in rows:
        # Remove stale rows for currencies no longer earned by in-wallet cards
        # (unless the user explicitly tracks them).
        if row.currency_id not in active_currency_ids and not row.user_tracked:
            await db.delete(row)
            continue
        earn = float(currency_pts_by_id.get(row.currency_id, 0.0))
        row.projection_earn = earn
        row.balance = round(row.initial_balance + earn, 4)
        row.updated_date = today

    for cid, earn in currency_pts_by_id.items():
        if earn <= 0 or cid not in valid_ids:
            continue
        if cid in by_cid:
            continue
        new_row = WalletCurrencyBalance(
            wallet_id=wallet_id,
            currency_id=cid,
            initial_balance=0.0,
            projection_earn=float(earn),
            balance=float(earn),
            user_tracked=False,
            updated_date=today,
        )
        db.add(new_row)
        by_cid[cid] = new_row


@app.get(
    "/wallets/{wallet_id}/results",
    response_model=WalletResultResponseSchema,
    tags=["wallets"],
)
async def wallet_results(
    wallet_id: int,
    start_date: Optional[date] = None,
    reference_date: Optional[date] = None,
    end_date: Optional[date] = None,
    duration_years: int = Query(0, ge=0),
    duration_months: int = Query(0, ge=0),
    projection_years: int = 2,
    projection_months: int = 0,
    spend_overrides: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Compute wallet results (effective fees, points, credits) and SUB opportunity cost.

    Start: optional ``start_date`` (preferred) or legacy ``reference_date`` — must not both
    disagree. Default start is wallet ``as_of_date`` or today.

    Window length (exactly one mode):
    - ``end_date`` (after start): months in [start, end_date) map to ``years_counted``.
    - ``duration_years`` + ``duration_months`` (total months > 0): same mapping.
    - Otherwise legacy ``projection_years`` / ``projection_months`` with the original
      ``years_counted = projection_years + (1 if projection_months >= 6 else 0)``.

    Do not send ``end_date`` together with a non-zero duration.

    spend_overrides: optional JSON object of category name -> annual spend.
    """
    overrides: dict[str, float] = {}
    if spend_overrides:
        try:
            overrides = json.loads(spend_overrides)
        except (json.JSONDecodeError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="spend_overrides must be valid JSON (e.g. '{\"Dining\": 5000}')",
            )
    result = await db.execute(
        select(Wallet)
        .options(selectinload(Wallet.wallet_cards))
        .where(Wallet.id == wallet_id)
    )
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise _wallet_404(wallet_id)

    if start_date is not None and reference_date is not None and start_date != reference_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_date and reference_date disagree; send only one.",
        )
    user_provided_start = start_date if start_date is not None else reference_date
    ref_date = user_provided_start or date.today()

    duration_span = duration_years * 12 + duration_months
    if end_date is not None and duration_span > 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Do not send end_date together with duration_years/duration_months.",
        )

    resp_end: Optional[date] = None
    resp_dur_y, resp_dur_m = 0, 0
    total_months: int
    today_dt = date.today()

    if end_date is not None:
        try:
            total_months = _months_in_half_open_interval(ref_date, end_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="end_date must be after start_date.",
            ) from None
        years_counted = _years_counted_from_total_months(total_months)
        resp_end = end_date
        window_end = end_date
    elif duration_span > 0:
        # Duration is forward-looking from today; window_start anchors at oldest card date.
        window_end = _add_months(today_dt, duration_span)
        total_months = _months_in_half_open_interval(ref_date, window_end)
        years_counted = _years_counted_from_total_months(total_months)
        resp_dur_y, resp_dur_m = duration_years, duration_months
    else:
        window_end = _add_months(today_dt, projection_years * 12 + projection_months)
        total_months = _months_in_half_open_interval(ref_date, window_end)
        years_counted = max(1, projection_years + (1 if projection_months >= 6 else 0))

    # Include cards that overlap the selected calculation window.
    # The calculator still models the chosen window at wallet level, but cards opened
    # later in that window must not be excluded entirely or only the earliest card(s)
    # contribute to projected balances and value.
    active_wallet_cards = [
        wc
        for wc in wallet.wallet_cards
        if wc.panel == "in_wallet"
        and wc.added_date < window_end
        and (wc.closed_date is None or wc.closed_date >= ref_date)
    ]

    _save_calc_window = "end" if end_date is not None else "duration"
    wallet.calc_start_date = ref_date
    wallet.calc_end_date = resp_end
    wallet.calc_duration_years = resp_dur_y
    wallet.calc_duration_months = resp_dur_m
    wallet.calc_window_mode = _save_calc_window

    if not active_wallet_cards:
        await _sync_wallet_balances_from_currency_pts(db, wallet_id, {})
        await db.commit()
        return WalletResultResponseSchema(
            wallet_id=wallet_id,
            wallet_name=wallet.name,
            start_date=ref_date,
            end_date=resp_end,
            duration_years=resp_dur_y,
            duration_months=resp_dur_m,
            total_months=total_months,
            as_of_date=ref_date,
            projection_years=projection_years,
            projection_months=projection_months,
            years_counted=years_counted,
            wallet=WalletResultSchema(
                years_counted=years_counted,
                total_effective_annual_fee=0,
                total_points_earned=0,
                total_annual_pts=0,
                total_cash_reward_dollars=0,
                total_reward_value_usd=0,
            ),
        )

    cpp_overrides = await load_wallet_cpp_overrides(db, wallet_id)
    all_cards = await load_card_data(db, cpp_overrides=cpp_overrides)
    card_ids_sel = {wc.card_id for wc in active_wallet_cards}
    lib_for_overrides = await db.execute(
        select(Card).options(selectinload(Card.credits)).where(Card.id.in_(card_ids_sel))
    )
    library_cards_by_id = {c.id: c for c in lib_for_overrides.scalars().all()}
    wallet_credit_rows = await load_wallet_card_credits(db, wallet_id)
    modified_cards = apply_wallet_card_overrides(
        all_cards, active_wallet_cards, library_cards_by_id, wallet_credit_rows
    )
    wallet_multiplier_rows = await load_wallet_card_multipliers(db, wallet_id)
    modified_cards = apply_wallet_card_multiplier_overrides(modified_cards, wallet_multiplier_rows)
    group_selections = await load_wallet_card_group_selections(db, wallet_id)
    modified_cards = apply_wallet_card_group_selections(modified_cards, group_selections)
    rotation_overrides = await load_wallet_card_rotation_overrides(db, wallet_id)
    modified_cards = apply_wallet_card_rotation_overrides(modified_cards, rotation_overrides)
    portal_shares = await load_wallet_portal_shares(db, wallet_id)
    if portal_shares:
        # Need an issuer_id lookup for each selected card; load minimal Card rows.
        issuer_lookup = await db.execute(
            select(Card).where(Card.id.in_(card_ids_sel))
        )
        cards_orm_by_id = {c.id: c for c in issuer_lookup.scalars().all()}
        modified_cards = apply_wallet_portal_shares(
            modified_cards, portal_shares, cards_orm_by_id
        )
    selected_ids = card_ids_sel
    spend = await load_wallet_spend_items(db, wallet_id)
    if overrides:
        spend.update(overrides)

    # Identify cards with active SUB windows for priority allocation.
    # A card has an active SUB window if it has a SUB, min spend requirement,
    # and the window hasn't expired yet.
    selected_card_data = [c for c in modified_cards if c.id in card_ids_sel]
    wcids = {c.currency.id for c in selected_card_data}

    # Cards whose SUB has already been earned (user toggled in UI) need no
    # spend allocation — exclude them from priority/planning entirely.
    sub_already_earned_ids = {wc.card_id for wc in active_wallet_cards if wc.sub_earned_date}

    def _has_sub_window(cd: "CardData") -> bool:
        if cd.id in sub_already_earned_ids:
            return False
        if not cd.sub or not cd.sub_min_spend or not cd.wallet_added_date:
            return False
        if cd.sub_months:
            window_end_dt = _add_months(cd.wallet_added_date, cd.sub_months)
            if ref_date >= window_end_dt:
                return False
        return True

    sub_priority_card_ids = {cd.id for cd in selected_card_data if _has_sub_window(cd)}

    # Plan SUB spend: check if all SUBs can be hit simultaneously (parallel),
    # otherwise find a sequential schedule (earliest deadline first).
    sub_cards_for_plan = [cd for cd in selected_card_data if _has_sub_window(cd)]
    sub_plan = plan_sub_targeting(sub_cards_for_plan, spend, ref_date, wcids)

    # Build per-card daily rates from the plan.  Cards in the plan get their
    # planned allocation; non-SUB cards get their normal allocated spend.
    plan_rates: dict[int, float] = {s.card_id: s.daily_spend_allocated for s in sub_plan.schedules}
    card_daily_rates: dict[int, float] = {}
    for cd in selected_card_data:
        if cd.id in plan_rates:
            card_daily_rates[cd.id] = plan_rates[cd.id]
        else:
            allocated = calc_annual_allocated_spend(cd, selected_card_data, spend, wcids, sub_priority_card_ids)
            card_daily_rates[cd.id] = allocated / 365.0

    # Auto-project SUB earn dates from the plan schedule, falling back to the
    # old per-card projection for cards not covered by the plan.
    plan_earn_dates: dict[int, date] = {s.card_id: s.projected_earn_date for s in sub_plan.schedules}
    projected_dates: dict[int, Optional[date]] = {}
    for wc in active_wallet_cards:
        lib = library_cards_by_id.get(wc.card_id)
        eff_min = wc.sub_min_spend if wc.sub_min_spend is not None else (lib.sub_min_spend if lib else None)
        eff_months = wc.sub_months if wc.sub_months is not None else (lib.sub_months if lib else None)
        eff_sub = wc.sub if wc.sub is not None else (lib.sub if lib else None)
        if wc.card_id in plan_earn_dates:
            proj = plan_earn_dates[wc.card_id]
        elif not eff_sub or not eff_min:
            proj = None
        else:
            daily_rate = card_daily_rates.get(wc.card_id, 0.0)
            proj = _projected_sub_earn_date(wc.added_date, eff_min, eff_months, daily_rate)
        projected_dates[wc.card_id] = proj
        if wc.sub_projected_earn_date != proj:
            wc.sub_projected_earn_date = proj

    # Patch sub_earnable, sub_already_earned, and sub_projected_earn_date onto
    # each CardData.  Cards whose SUB was already earned keep sub_earnable=True
    # (the bonus still counts) and sub_already_earned=True (no spend redirection).
    # Cards in the plan get sub_earnable from plan membership.  Others use the
    # per-card spend rate check.
    plan_card_ids = {s.card_id for s in sub_plan.schedules}
    modified_cards = [
        dataclasses.replace(
            c,
            sub_already_earned=c.id in sub_already_earned_ids,
            sub_earnable=(
                True
                if c.id in sub_already_earned_ids
                else (
                    (c.id in plan_card_ids)
                    if c.id in sub_priority_card_ids
                    else _is_sub_earnable(c.sub_min_spend, c.sub_months, card_daily_rates.get(c.id, 0.0))
                )
            ),
            sub_projected_earn_date=projected_dates.get(c.id, c.sub_projected_earn_date),
        )
        for c in modified_cards
    ]

    wallet_result = compute_wallet(
        all_cards=modified_cards,
        selected_ids=selected_ids,
        spend=spend,
        years=years_counted,
        window_start=ref_date,
        window_end=window_end,
        sub_priority_card_ids=sub_priority_card_ids,
    )

    await _sync_wallet_balances_from_currency_pts(
        db, wallet_id, wallet_result.currency_pts_by_id
    )
    await db.commit()

    return WalletResultResponseSchema(
        wallet_id=wallet_id,
        wallet_name=wallet.name,
        start_date=ref_date,
        end_date=resp_end,
        duration_years=resp_dur_y,
        duration_months=resp_dur_m,
        total_months=total_months,
        as_of_date=ref_date,
        projection_years=projection_years,
        projection_months=projection_months,
        years_counted=wallet_result.years_counted,
        wallet=_wallet_to_schema(wallet_result),
    )


@app.get(
    "/wallets/{wallet_id}/roadmap",
    response_model=RoadmapResponse,
    tags=["wallets"],
)
async def wallet_roadmap(
    wallet_id: int,
    as_of_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Compute roadmap status for the wallet: 5/24 count, per-card SUB status and
    next eligibility dates, and any issuer velocity rule violations.
    """
    result = await db.execute(
        select(Wallet)
        .options(
            selectinload(Wallet.wallet_cards).selectinload(WalletCard.card).selectinload(Card.issuer),
        )
        .where(Wallet.id == wallet_id)
    )
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise _wallet_404(wallet_id)

    today = as_of_date or date.today()

    # Load all application rules
    rules_result = await db.execute(
        select(IssuerApplicationRule)
        .options(selectinload(IssuerApplicationRule.issuer))
    )
    rules = rules_result.scalars().all()

    # Load spend items to compute daily spend rate for SUB projections
    roadmap_spend = await load_wallet_spend_items(db, wallet_id)
    roadmap_daily_rate = sum(roadmap_spend.values()) / 365.0

    # ── Per-card status ──────────────────────────────────────────────────────
    card_statuses: list[RoadmapCardStatus] = []
    personal_cards_24mo: list[str] = []
    cutoff_24mo = today - timedelta(days=730)

    in_wallet_cards = [wc for wc in wallet.wallet_cards if wc.panel == "in_wallet"]

    for wc in in_wallet_cards:
        card = wc.card
        is_active = wc.closed_date is None

        # 5/24: count non-business cards opened (not product-changed) in last 24 months
        if not card.business and wc.added_date >= cutoff_24mo and wc.acquisition_type == "opened":
            personal_cards_24mo.append(card.name)

        # Effective SUB value and months (wallet override takes precedence)
        eff_sub = wc.sub if wc.sub is not None else (card.sub or 0)
        eff_sub_months = wc.sub_months if wc.sub_months is not None else card.sub_months
        eff_sub_min = wc.sub_min_spend if wc.sub_min_spend is not None else card.sub_min_spend

        # Auto-compute projected earn date for display (uses stored value if already set)
        sub_projected = wc.sub_projected_earn_date
        if sub_projected is None and eff_sub and eff_sub_min and not wc.sub_earned_date:
            sub_projected = _projected_sub_earn_date(wc.added_date, eff_sub_min, eff_sub_months, roadmap_daily_rate)

        # Determine SUB status
        if not eff_sub:
            sub_status = "no_sub"
            sub_window_end = None
            sub_days_remaining = None
        elif wc.sub_earned_date:
            sub_status = "earned"
            sub_window_end = None
            sub_days_remaining = None
        elif sub_projected is not None and sub_projected <= today:
            # Projected earn date has passed — treat as earned
            sub_status = "earned"
            sub_window_end = None
            sub_days_remaining = None
        elif eff_sub_months:
            sub_window_end = _add_months(wc.added_date, eff_sub_months)
            remaining = (sub_window_end - today).days
            if remaining < 0:
                sub_status = "expired"
                sub_days_remaining = None
            else:
                sub_status = "pending"
                sub_days_remaining = remaining
        else:
            sub_status = "pending"
            sub_window_end = None
            sub_days_remaining = None

        # Next eligible date for this card's SUB
        recurrence = card.sub_recurrence_months
        next_eligible: Optional[date] = None
        if recurrence:
            effective_earned = wc.sub_earned_date or (sub_projected if sub_projected and sub_projected <= today else None)
            if effective_earned:
                next_eligible = _add_months(effective_earned, recurrence)
            else:
                # No earned date: next eligible is opening date + recurrence (conservative)
                next_eligible = _add_months(wc.added_date, recurrence)

        card_statuses.append(
            RoadmapCardStatus(
                wallet_card_id=wc.id,
                card_id=card.id,
                card_name=card.name,
                issuer_name=card.issuer.name,
                is_business=card.business,
                added_date=wc.added_date,
                closed_date=wc.closed_date,
                is_active=is_active,
                sub_earned_date=wc.sub_earned_date,
                sub_projected_earn_date=sub_projected,
                sub_status=sub_status,
                sub_window_end=sub_window_end,
                next_sub_eligible_date=next_eligible,
                sub_days_remaining=sub_days_remaining,
            )
        )

    # ── Issuer rule violation checks ─────────────────────────────────────────
    rule_statuses: list[RoadmapRuleStatus] = []
    for rule in rules:
        cutoff = today - timedelta(days=rule.period_days)
        counted: list[str] = []
        for wc in in_wallet_cards:
            card = wc.card
            if wc.added_date < cutoff:
                continue
            # Scope: all issuers OR only this rule's issuer
            if not rule.scope_all_issuers and card.issuer_id != rule.issuer_id:
                continue
            # personal_only: skip business cards
            if rule.personal_only and card.business:
                continue
            # product changes are not new applications; skip them for velocity rules
            if wc.acquisition_type == "product_change":
                continue
            counted.append(card.name)

        rule_statuses.append(
            RoadmapRuleStatus(
                rule_id=rule.id,
                rule_name=rule.rule_name,
                issuer_name=rule.issuer.name if rule.issuer else None,
                description=rule.description,
                max_count=rule.max_count,
                period_days=rule.period_days,
                current_count=len(counted),
                is_violated=len(counted) >= rule.max_count,
                personal_only=rule.personal_only,
                scope_all_issuers=rule.scope_all_issuers,
                counted_cards=counted,
            )
        )

    five_twenty_four_count = len(personal_cards_24mo)

    return RoadmapResponse(
        wallet_id=wallet_id,
        wallet_name=wallet.name,
        as_of_date=today,
        five_twenty_four_count=five_twenty_four_count,
        five_twenty_four_eligible=five_twenty_four_count < 5,
        personal_cards_24mo=personal_cards_24mo,
        rule_statuses=rule_statuses,
        cards=card_statuses,
    )


@app.get(
    "/wallets/{wallet_id}/currency-balances",
    response_model=list[WalletCurrencyBalanceRead],
    tags=["wallets"],
)
async def list_wallet_currency_balances(
    wallet_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Currencies you track or that have projection earn from the last calculate."""
    w_result = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
    if not w_result.scalar_one_or_none():
        raise _wallet_404(wallet_id)
    await _ensure_wallet_currency_rows_for_earning_currencies(db, wallet_id)
    await db.commit()
    result = await db.execute(
        select(WalletCurrencyBalance)
        .options(selectinload(WalletCurrencyBalance.currency))
        .where(WalletCurrencyBalance.wallet_id == wallet_id)
        .order_by(WalletCurrencyBalance.currency_id)
    )
    return list(result.scalars().all())


@app.get(
    "/wallets/{wallet_id}/settings-currency-ids",
    response_model=WalletSettingsCurrencyIds,
    tags=["wallets"],
)
async def wallet_settings_currency_ids(wallet_id: int, db: AsyncSession = Depends(get_db)):
    """
    IDs for currencies shown in wallet settings: earned by cards in this wallet,
    or explicitly user-tracked (added manually).
    """
    w_result = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
    if not w_result.scalar_one_or_none():
        raise _wallet_404(wallet_id)
    earn = await _effective_earn_currency_ids_for_wallet(db, wallet_id)
    tr = await db.execute(
        select(WalletCurrencyBalance.currency_id).where(
            WalletCurrencyBalance.wallet_id == wallet_id,
            WalletCurrencyBalance.user_tracked.is_(True),
        )
    )
    tracked = set(tr.scalars().all())
    merged = earn | tracked
    return WalletSettingsCurrencyIds(currency_ids=sorted(merged))


@app.post(
    "/wallets/{wallet_id}/currency-balances",
    response_model=WalletCurrencyBalanceRead,
    status_code=status.HTTP_201_CREATED,
    tags=["wallets"],
)
async def track_wallet_currency_balance(
    wallet_id: int,
    payload: WalletCurrencyTrackCreate,
    db: AsyncSession = Depends(get_db),
):
    """Start tracking a currency for this wallet (optional starting balance)."""
    w_result = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
    if not w_result.scalar_one_or_none():
        raise _wallet_404(wallet_id)
    currency_result = await db.execute(
        select(Currency).where(Currency.id == payload.currency_id)
    )
    if not currency_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Currency id={payload.currency_id} not found")

    existing = await db.execute(
        select(WalletCurrencyBalance).where(
            WalletCurrencyBalance.wallet_id == wallet_id,
            WalletCurrencyBalance.currency_id == payload.currency_id,
        )
    )
    row = existing.scalar_one_or_none()
    today = date.today()
    if row:
        row.user_tracked = True
        row.initial_balance = payload.initial_balance
        row.balance = round(row.initial_balance + row.projection_earn, 4)
        row.updated_date = today
    else:
        row = WalletCurrencyBalance(
            wallet_id=wallet_id,
            currency_id=payload.currency_id,
            initial_balance=payload.initial_balance,
            projection_earn=0.0,
            balance=payload.initial_balance,
            user_tracked=True,
            updated_date=today,
        )
        db.add(row)
    await db.commit()
    await db.refresh(row)
    res = await db.execute(
        select(WalletCurrencyBalance)
        .options(selectinload(WalletCurrencyBalance.currency))
        .where(WalletCurrencyBalance.id == row.id)
    )
    return res.scalar_one()


@app.put(
    "/wallets/{wallet_id}/currencies/{currency_id}/balance",
    response_model=WalletCurrencyBalanceRead,
    tags=["wallets"],
)
async def set_wallet_currency_initial_balance(
    wallet_id: int,
    currency_id: int,
    payload: WalletCurrencyInitialSet,
    db: AsyncSession = Depends(get_db),
):
    """Update starting balance; total = initial + last projection earn from Calculate."""
    w_result = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
    if not w_result.scalar_one_or_none():
        raise _wallet_404(wallet_id)
    currency_result = await db.execute(select(Currency).where(Currency.id == currency_id))
    if not currency_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Currency id={currency_id} not found")

    existing = await db.execute(
        select(WalletCurrencyBalance).where(
            WalletCurrencyBalance.wallet_id == wallet_id,
            WalletCurrencyBalance.currency_id == currency_id,
        )
    )
    row = existing.scalar_one_or_none()
    if not row:
        raise HTTPException(
            status_code=404,
            detail="Track this currency first (POST /currency-balances) before editing initial balance",
        )
    row.initial_balance = payload.initial_balance
    row.balance = round(row.initial_balance + row.projection_earn, 4)
    row.updated_date = date.today()
    await db.commit()
    res = await db.execute(
        select(WalletCurrencyBalance)
        .options(selectinload(WalletCurrencyBalance.currency))
        .where(WalletCurrencyBalance.id == row.id)
    )
    return res.scalar_one()


@app.delete(
    "/wallets/{wallet_id}/currencies/{currency_id}/balance",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["wallets"],
)
async def delete_wallet_currency_balance(
    wallet_id: int,
    currency_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Remove the wallet's balance record for a currency."""
    result = await db.execute(
        select(WalletCurrencyBalance).where(
            WalletCurrencyBalance.wallet_id == wallet_id,
            WalletCurrencyBalance.currency_id == currency_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(
            status_code=404,
            detail="No balance record found for this wallet and currency",
        )
    await db.delete(row)
    await db.commit()


# ---------------------------------------------------------------------------
# Wallet CPP overrides
# ---------------------------------------------------------------------------


@app.get(
    "/wallets/{wallet_id}/currencies",
    response_model=list[CurrencyRead],
    tags=["wallet-cpp"],
)
async def list_wallet_currencies_with_cpp(
    wallet_id: int,
    db: AsyncSession = Depends(get_db),
):
    """List all currencies with wallet-scoped CPP overrides applied."""
    w_result = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
    if not w_result.scalar_one_or_none():
        raise _wallet_404(wallet_id)

    cpp_result = await db.execute(
        select(WalletCurrencyCpp).where(WalletCurrencyCpp.wallet_id == wallet_id)
    )
    overrides = {row.currency_id: row.cents_per_point for row in cpp_result.scalars().all()}

    cur_result = await db.execute(
        select(Currency)
        .order_by(Currency.name)
    )
    currencies = cur_result.scalars().all()
    out = []
    for c in currencies:
        schema = CurrencyRead.model_validate(c)
        if c.id in overrides:
            schema.user_cents_per_point = overrides[c.id]
        else:
            schema.user_cents_per_point = c.cents_per_point
        out.append(schema)
    return out


@app.put(
    "/wallets/{wallet_id}/currencies/{currency_id}/cpp",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["wallet-cpp"],
)
async def set_wallet_cpp(
    wallet_id: int,
    currency_id: int,
    payload: WalletCurrencyCppSet,
    db: AsyncSession = Depends(get_db),
):
    """Set or update wallet-scoped cents-per-point for a currency."""
    w_result = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
    if not w_result.scalar_one_or_none():
        raise _wallet_404(wallet_id)
    cur_result = await db.execute(select(Currency).where(Currency.id == currency_id))
    if not cur_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Currency id={currency_id} not found")

    existing = await db.execute(
        select(WalletCurrencyCpp).where(
            WalletCurrencyCpp.wallet_id == wallet_id,
            WalletCurrencyCpp.currency_id == currency_id,
        )
    )
    row = existing.scalar_one_or_none()
    if row:
        row.cents_per_point = payload.cents_per_point
    else:
        db.add(WalletCurrencyCpp(
            wallet_id=wallet_id,
            currency_id=currency_id,
            cents_per_point=payload.cents_per_point,
        ))
    await db.commit()


@app.delete(
    "/wallets/{wallet_id}/currencies/{currency_id}/cpp",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["wallet-cpp"],
)
async def delete_wallet_cpp(
    wallet_id: int,
    currency_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Remove wallet-scoped CPP override (reverts to currency default)."""
    result = await db.execute(
        select(WalletCurrencyCpp).where(
            WalletCurrencyCpp.wallet_id == wallet_id,
            WalletCurrencyCpp.currency_id == currency_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No CPP override for this wallet/currency")
    await db.delete(row)
    await db.commit()


# ---------------------------------------------------------------------------
# Wallet card credit overrides
# ---------------------------------------------------------------------------


@app.get(
    "/wallets/{wallet_id}/cards/{card_id}/credits",
    response_model=list[WalletCardCreditRead],
    tags=["wallet-credits"],
)
async def list_wallet_card_credits(
    wallet_id: int,
    card_id: int,
    db: AsyncSession = Depends(get_db),
):
    """List credit overrides for a card in this wallet."""
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


@app.put(
    "/wallets/{wallet_id}/cards/{card_id}/credits/{library_credit_id}",
    response_model=WalletCardCreditRead,
    tags=["wallet-credits"],
)
async def upsert_wallet_card_credit(
    wallet_id: int,
    card_id: int,
    library_credit_id: int,
    payload: WalletCardCreditUpsert,
    db: AsyncSession = Depends(get_db),
):
    """Set or update a credit override for a card in this wallet."""
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
        select(CardCredit).where(
            CardCredit.id == library_credit_id,
            CardCredit.card_id == card_id,
        )
    )
    lib_credit = lib_result.scalar_one_or_none()
    if not lib_credit:
        raise HTTPException(status_code=404, detail=f"CardCredit id={library_credit_id} not found for card {card_id}")

    existing = await db.execute(
        select(WalletCardCredit).where(
            WalletCardCredit.wallet_card_id == wc.id,
            WalletCardCredit.library_credit_id == library_credit_id,
        )
    )
    row = existing.scalar_one_or_none()
    is_one_time = payload.is_one_time if payload.is_one_time is not None else lib_credit.is_one_time
    if row:
        row.value = payload.value
        row.is_one_time = is_one_time
    else:
        row = WalletCardCredit(
            wallet_card_id=wc.id,
            library_credit_id=library_credit_id,
            value=payload.value,
            is_one_time=is_one_time,
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


@app.delete(
    "/wallets/{wallet_id}/cards/{card_id}/credits/{library_credit_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["wallet-credits"],
)
async def delete_wallet_card_credit(
    wallet_id: int,
    card_id: int,
    library_credit_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Remove a credit override (reverts to library value)."""
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


# ---------------------------------------------------------------------------
# Wallet card multiplier overrides
# ---------------------------------------------------------------------------


@app.get(
    "/wallets/{wallet_id}/card-multipliers",
    response_model=list[WalletCardMultiplierRead],
    tags=["wallet-multipliers"],
)
async def list_wallet_card_multipliers(
    wallet_id: int,
    db: AsyncSession = Depends(get_db),
):
    """List all wallet-level multiplier overrides."""
    w_result = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
    if not w_result.scalar_one_or_none():
        raise _wallet_404(wallet_id)

    result = await db.execute(
        select(WalletCardMultiplier)
        .options(selectinload(WalletCardMultiplier.spend_category))
        .where(WalletCardMultiplier.wallet_id == wallet_id)
        .order_by(WalletCardMultiplier.card_id, WalletCardMultiplier.category_id)
    )
    return list(result.scalars().all())


@app.put(
    "/wallets/{wallet_id}/cards/{card_id}/multipliers/{category_id}",
    response_model=WalletCardMultiplierRead,
    tags=["wallet-multipliers"],
)
async def upsert_wallet_card_multiplier(
    wallet_id: int,
    card_id: int,
    category_id: int,
    payload: WalletCardMultiplierUpsert,
    db: AsyncSession = Depends(get_db),
):
    """Set or update a multiplier override for a card/category in this wallet."""
    w_result = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
    if not w_result.scalar_one_or_none():
        raise _wallet_404(wallet_id)
    card_result = await db.execute(select(Card).where(Card.id == card_id))
    if not card_result.scalar_one_or_none():
        raise _card_404(card_id)
    sc_result = await db.execute(select(SpendCategory).where(SpendCategory.id == category_id))
    if not sc_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"SpendCategory id={category_id} not found")

    existing = await db.execute(
        select(WalletCardMultiplier).where(
            WalletCardMultiplier.wallet_id == wallet_id,
            WalletCardMultiplier.card_id == card_id,
            WalletCardMultiplier.category_id == category_id,
        )
    )
    row = existing.scalar_one_or_none()
    if row:
        row.multiplier = payload.multiplier
    else:
        row = WalletCardMultiplier(
            wallet_id=wallet_id,
            card_id=card_id,
            category_id=category_id,
            multiplier=payload.multiplier,
        )
        db.add(row)
    await db.commit()
    await db.refresh(row)
    res = await db.execute(
        select(WalletCardMultiplier)
        .options(selectinload(WalletCardMultiplier.spend_category))
        .where(WalletCardMultiplier.id == row.id)
    )
    return res.scalar_one()


@app.delete(
    "/wallets/{wallet_id}/cards/{card_id}/multipliers/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["wallet-multipliers"],
)
async def delete_wallet_card_multiplier(
    wallet_id: int,
    card_id: int,
    category_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Remove a multiplier override (reverts to library value)."""
    result = await db.execute(
        select(WalletCardMultiplier).where(
            WalletCardMultiplier.wallet_id == wallet_id,
            WalletCardMultiplier.card_id == card_id,
            WalletCardMultiplier.category_id == category_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No multiplier override found")
    await db.delete(row)
    await db.commit()


# ---------------------------------------------------------------------------
# Wallet card group category selections
# ---------------------------------------------------------------------------


@app.get(
    "/wallets/{wallet_id}/cards/{card_id}/group-selections",
    response_model=list[WalletCardGroupSelectionRead],
)
async def list_wallet_card_group_selections(
    wallet_id: int,
    card_id: int,
    db: AsyncSession = Depends(get_db),
):
    wc = await db.execute(
        select(WalletCard).where(
            WalletCard.wallet_id == wallet_id,
            WalletCard.card_id == card_id,
        )
    )
    wc_row = wc.scalar_one_or_none()
    if not wc_row:
        raise HTTPException(status_code=404, detail="Wallet card not found")
    result = await db.execute(
        select(WalletCardGroupSelection)
        .options(selectinload(WalletCardGroupSelection.spend_category))
        .where(WalletCardGroupSelection.wallet_card_id == wc_row.id)
    )
    return result.scalars().all()


@app.put(
    "/wallets/{wallet_id}/cards/{card_id}/group-selections/{group_id}",
    response_model=list[WalletCardGroupSelectionRead],
)
async def set_wallet_card_group_selections(
    wallet_id: int,
    card_id: int,
    group_id: int,
    payload: WalletCardGroupSelectionSet,
    db: AsyncSession = Depends(get_db),
):
    wc = await db.execute(
        select(WalletCard).where(
            WalletCard.wallet_id == wallet_id,
            WalletCard.card_id == card_id,
        )
    )
    wc_row = wc.scalar_one_or_none()
    if not wc_row:
        raise HTTPException(status_code=404, detail="Wallet card not found")

    # Validate group belongs to this card
    grp = await db.execute(
        select(CardMultiplierGroup)
        .options(
            selectinload(CardMultiplierGroup.categories).selectinload(
                CardCategoryMultiplier.spend_category
            ),
            selectinload(CardMultiplierGroup.card)
            .selectinload(Card.rotating_history)
            .selectinload(CardRotatingHistory.spend_category),
        )
        .where(
            CardMultiplierGroup.id == group_id,
            CardMultiplierGroup.card_id == card_id,
        )
    )
    grp_row = grp.scalar_one_or_none()
    if not grp_row:
        raise HTTPException(status_code=404, detail="Multiplier group not found for this card")

    # Delete existing selections for this group
    existing = await db.execute(
        select(WalletCardGroupSelection).where(
            WalletCardGroupSelection.wallet_card_id == wc_row.id,
            WalletCardGroupSelection.multiplier_group_id == group_id,
        )
    )
    for row in existing.scalars().all():
        await db.delete(row)
    # Flush deletes before inserts so the unique constraint on
    # (wallet_card_id, multiplier_group_id, spend_category_id) doesn't trip
    # when the new selection set overlaps the old one.
    await db.flush()

    # If empty list, revert to auto-pick
    if not payload.spend_category_ids:
        await db.commit()
        return []

    # Validate: count matches top_n
    top_n = grp_row.top_n_categories
    if top_n is None and getattr(grp_row, "top_category_only", False):
        top_n = 1
    if top_n and len(payload.spend_category_ids) != top_n:
        raise HTTPException(
            status_code=422,
            detail=f"Must select exactly {top_n} categories, got {len(payload.spend_category_ids)}",
        )

    # Validate: each category is in the group
    valid_cat_ids = {c.category_id for c in grp_row.categories}
    for cat_id in payload.spend_category_ids:
        if cat_id not in valid_cat_ids:
            raise HTTPException(
                status_code=422,
                detail=f"Category {cat_id} is not in this multiplier group",
            )

    # Insert new selections
    for cat_id in payload.spend_category_ids:
        db.add(
            WalletCardGroupSelection(
                wallet_card_id=wc_row.id,
                multiplier_group_id=group_id,
                spend_category_id=cat_id,
            )
        )
    await db.commit()

    # Return the new selections
    result = await db.execute(
        select(WalletCardGroupSelection)
        .options(selectinload(WalletCardGroupSelection.spend_category))
        .where(
            WalletCardGroupSelection.wallet_card_id == wc_row.id,
            WalletCardGroupSelection.multiplier_group_id == group_id,
        )
    )
    return result.scalars().all()


@app.delete(
    "/wallets/{wallet_id}/cards/{card_id}/group-selections/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_wallet_card_group_selections(
    wallet_id: int,
    card_id: int,
    group_id: int,
    db: AsyncSession = Depends(get_db),
):
    wc = await db.execute(
        select(WalletCard).where(
            WalletCard.wallet_id == wallet_id,
            WalletCard.card_id == card_id,
        )
    )
    wc_row = wc.scalar_one_or_none()
    if not wc_row:
        raise HTTPException(status_code=404, detail="Wallet card not found")
    existing = await db.execute(
        select(WalletCardGroupSelection).where(
            WalletCardGroupSelection.wallet_card_id == wc_row.id,
            WalletCardGroupSelection.multiplier_group_id == group_id,
        )
    )
    for row in existing.scalars().all():
        await db.delete(row)
    await db.commit()


# ---- Wallet card rotation overrides ----


@app.get(
    "/wallets/{wallet_id}/cards/{card_id}/rotation-overrides",
    response_model=list[WalletRotationOverrideRead],
)
async def list_wallet_card_rotation_overrides(
    wallet_id: int,
    card_id: int,
    db: AsyncSession = Depends(get_db),
):
    wc = await db.execute(
        select(WalletCard).where(
            WalletCard.wallet_id == wallet_id,
            WalletCard.card_id == card_id,
        )
    )
    wc_row = wc.scalar_one_or_none()
    if not wc_row:
        raise HTTPException(status_code=404, detail="Wallet card not found")
    result = await db.execute(
        select(WalletCardRotationOverride)
        .options(selectinload(WalletCardRotationOverride.spend_category))
        .where(WalletCardRotationOverride.wallet_card_id == wc_row.id)
        .order_by(
            WalletCardRotationOverride.year.desc(),
            WalletCardRotationOverride.quarter.desc(),
        )
    )
    return result.scalars().all()


@app.post(
    "/wallets/{wallet_id}/cards/{card_id}/rotation-overrides",
    response_model=WalletRotationOverrideRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_wallet_card_rotation_override(
    wallet_id: int,
    card_id: int,
    payload: WalletRotationOverridePayload,
    db: AsyncSession = Depends(get_db),
):
    wc = await db.execute(
        select(WalletCard).where(
            WalletCard.wallet_id == wallet_id,
            WalletCard.card_id == card_id,
        )
    )
    wc_row = wc.scalar_one_or_none()
    if not wc_row:
        raise HTTPException(status_code=404, detail="Wallet card not found")
    sc = await db.execute(
        select(SpendCategory).where(SpendCategory.id == payload.spend_category_id)
    )
    if not sc.scalar_one_or_none():
        raise HTTPException(
            status_code=404,
            detail=f"SpendCategory id={payload.spend_category_id} not found",
        )
    existing = await db.execute(
        select(WalletCardRotationOverride).where(
            WalletCardRotationOverride.wallet_card_id == wc_row.id,
            WalletCardRotationOverride.year == payload.year,
            WalletCardRotationOverride.quarter == payload.quarter,
            WalletCardRotationOverride.spend_category_id == payload.spend_category_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Rotation override already exists for {payload.year}Q{payload.quarter}",
        )
    row = WalletCardRotationOverride(
        wallet_card_id=wc_row.id,
        year=payload.year,
        quarter=payload.quarter,
        spend_category_id=payload.spend_category_id,
    )
    db.add(row)
    await db.commit()
    result = await db.execute(
        select(WalletCardRotationOverride)
        .options(selectinload(WalletCardRotationOverride.spend_category))
        .where(WalletCardRotationOverride.id == row.id)
    )
    return result.scalar_one()


@app.delete(
    "/wallets/{wallet_id}/cards/{card_id}/rotation-overrides/{override_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_wallet_card_rotation_override(
    wallet_id: int,
    card_id: int,
    override_id: int,
    db: AsyncSession = Depends(get_db),
):
    wc = await db.execute(
        select(WalletCard).where(
            WalletCard.wallet_id == wallet_id,
            WalletCard.card_id == card_id,
        )
    )
    wc_row = wc.scalar_one_or_none()
    if not wc_row:
        raise HTTPException(status_code=404, detail="Wallet card not found")
    result = await db.execute(
        select(WalletCardRotationOverride).where(
            WalletCardRotationOverride.id == override_id,
            WalletCardRotationOverride.wallet_card_id == wc_row.id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Rotation override not found")
    await db.delete(row)
    await db.commit()


# ---- Wallet portal shares (per-issuer travel-portal share for the wallet) ----


@app.get(
    "/wallets/{wallet_id}/portal-shares",
    response_model=list[WalletPortalShareRead],
)
async def list_wallet_portal_shares(
    wallet_id: int,
    db: AsyncSession = Depends(get_db),
):
    wallet_row = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
    if not wallet_row.scalar_one_or_none():
        raise _wallet_404(wallet_id)
    result = await db.execute(
        select(WalletPortalShare)
        .options(selectinload(WalletPortalShare.issuer))
        .where(WalletPortalShare.wallet_id == wallet_id)
        .order_by(WalletPortalShare.issuer_id)
    )
    return result.scalars().all()


@app.put(
    "/wallets/{wallet_id}/portal-shares",
    response_model=WalletPortalShareRead,
)
async def upsert_wallet_portal_share(
    wallet_id: int,
    payload: WalletPortalSharePayload,
    db: AsyncSession = Depends(get_db),
):
    wallet_row = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
    if not wallet_row.scalar_one_or_none():
        raise _wallet_404(wallet_id)
    iss_row = await db.execute(select(Issuer).where(Issuer.id == payload.issuer_id))
    if not iss_row.scalar_one_or_none():
        raise HTTPException(
            status_code=404, detail=f"Issuer id={payload.issuer_id} not found"
        )
    existing = await db.execute(
        select(WalletPortalShare).where(
            WalletPortalShare.wallet_id == wallet_id,
            WalletPortalShare.issuer_id == payload.issuer_id,
        )
    )
    row = existing.scalar_one_or_none()
    if row is None:
        row = WalletPortalShare(
            wallet_id=wallet_id,
            issuer_id=payload.issuer_id,
            share=payload.share,
        )
        db.add(row)
    else:
        row.share = payload.share
    await db.commit()
    result = await db.execute(
        select(WalletPortalShare)
        .options(selectinload(WalletPortalShare.issuer))
        .where(WalletPortalShare.id == row.id)
    )
    return result.scalar_one()


@app.delete(
    "/wallets/{wallet_id}/portal-shares/{issuer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_wallet_portal_share(
    wallet_id: int,
    issuer_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WalletPortalShare).where(
            WalletPortalShare.wallet_id == wallet_id,
            WalletPortalShare.issuer_id == issuer_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Portal share not found")
    await db.delete(row)
    await db.commit()


# ---------------------------------------------------------------------------
# Admin: Reference data CRUD
# ---------------------------------------------------------------------------


@app.post(
    "/admin/issuers",
    response_model=IssuerRead,
    status_code=status.HTTP_201_CREATED,
    tags=["admin"],
)
async def admin_create_issuer(
    payload: AdminCreateIssuerPayload,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(Issuer).where(Issuer.name == payload.name.strip()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Issuer '{payload.name}' already exists")
    issuer = Issuer(name=payload.name.strip())
    db.add(issuer)
    await db.commit()
    await db.refresh(issuer)
    return issuer


@app.post(
    "/admin/currencies",
    response_model=CurrencyRead,
    status_code=status.HTTP_201_CREATED,
    tags=["admin"],
)
async def admin_create_currency(
    payload: AdminCreateCurrencyPayload,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(Currency).where(Currency.name == payload.name.strip()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Currency '{payload.name}' already exists")
    if payload.converts_to_currency_id is not None:
        tgt = await db.execute(select(Currency).where(Currency.id == payload.converts_to_currency_id))
        if not tgt.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"Target currency id={payload.converts_to_currency_id} not found")

    currency = Currency(
        name=payload.name.strip(),
        reward_kind=payload.reward_kind,
        cents_per_point=payload.cents_per_point,
        partner_transfer_rate=payload.partner_transfer_rate,
        cash_transfer_rate=payload.cash_transfer_rate,
        converts_to_currency_id=payload.converts_to_currency_id,
        converts_at_rate=payload.converts_at_rate,
        no_transfer_cpp=payload.no_transfer_cpp,
        no_transfer_rate=payload.no_transfer_rate,
    )
    db.add(currency)
    await db.commit()
    await db.refresh(currency)
    return currency


@app.post(
    "/admin/spend-categories",
    response_model=SpendCategoryRead,
    status_code=status.HTTP_201_CREATED,
    tags=["admin"],
)
async def admin_create_spend_category(
    payload: AdminCreateSpendCategoryPayload,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(SpendCategory).where(SpendCategory.category == payload.category.strip()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"SpendCategory '{payload.category}' already exists")
    sc = SpendCategory(category=payload.category.strip())
    db.add(sc)
    await db.commit()
    await db.refresh(sc)
    return sc


@app.post(
    "/admin/cards",
    response_model=CardRead,
    status_code=status.HTTP_201_CREATED,
    tags=["admin"],
)
async def admin_create_card(
    payload: AdminCreateCardPayload,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(Card).where(Card.name == payload.name.strip()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Card '{payload.name}' already exists")
    iss = await db.execute(select(Issuer).where(Issuer.id == payload.issuer_id))
    if not iss.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Issuer id={payload.issuer_id} not found")
    cur = await db.execute(select(Currency).where(Currency.id == payload.currency_id))
    if not cur.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Currency id={payload.currency_id} not found")
    if payload.co_brand_id is not None:
        cb = await db.execute(select(CoBrand).where(CoBrand.id == payload.co_brand_id))
        if not cb.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"CoBrand id={payload.co_brand_id} not found")
    if payload.network_tier_id is not None:
        nt = await db.execute(select(NetworkTier).where(NetworkTier.id == payload.network_tier_id))
        if not nt.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"NetworkTier id={payload.network_tier_id} not found")

    card = Card(
        name=payload.name.strip(),
        issuer_id=payload.issuer_id,
        co_brand_id=payload.co_brand_id,
        currency_id=payload.currency_id,
        annual_fee=payload.annual_fee,
        first_year_fee=payload.first_year_fee,
        business=payload.business,
        network_tier_id=payload.network_tier_id,
        sub=payload.sub,
        sub_min_spend=payload.sub_min_spend,
        sub_months=payload.sub_months,
        sub_spend_earn=payload.sub_spend_earn,
        annual_bonus=payload.annual_bonus,
        transfer_enabler=payload.transfer_enabler,
        sub_recurrence_months=payload.sub_recurrence_months,
        sub_family=payload.sub_family,
    )
    db.add(card)
    await db.commit()
    res = await db.execute(
        select(Card).options(*_card_load_opts()).where(Card.id == card.id)
    )
    return res.scalar_one()


@app.delete(
    "/admin/cards/{card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["admin"],
)
async def admin_delete_card(
    card_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Card).where(Card.id == card_id))
    card = result.scalar_one_or_none()
    if not card:
        raise _card_404(card_id)
    wc_count = await db.execute(select(WalletCard.id).where(WalletCard.card_id == card_id))
    if wc_count.scalars().first() is not None:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete card — it is used in one or more wallets. Remove it from all wallets first.",
        )
    await db.delete(card)
    await db.commit()


@app.post(
    "/admin/cards/{card_id}/multipliers",
    response_model=CardRead,
    status_code=status.HTTP_201_CREATED,
    tags=["admin"],
)
async def admin_add_card_multiplier(
    card_id: int,
    payload: AdminAddCardMultiplierPayload,
    db: AsyncSession = Depends(get_db),
):
    card_result = await db.execute(select(Card).where(Card.id == card_id))
    if not card_result.scalar_one_or_none():
        raise _card_404(card_id)
    sc_result = await db.execute(select(SpendCategory).where(SpendCategory.id == payload.category_id))
    if not sc_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"SpendCategory id={payload.category_id} not found")

    existing = await db.execute(
        select(CardCategoryMultiplier).where(
            CardCategoryMultiplier.card_id == card_id,
            CardCategoryMultiplier.category_id == payload.category_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Multiplier for this card/category already exists")

    if payload.multiplier_group_id is not None:
        grp = await db.execute(
            select(CardMultiplierGroup).where(
                CardMultiplierGroup.id == payload.multiplier_group_id,
                CardMultiplierGroup.card_id == card_id,
            )
        )
        if not grp.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"MultiplierGroup id={payload.multiplier_group_id} not found for card {card_id}")

    mult = CardCategoryMultiplier(
        card_id=card_id,
        category_id=payload.category_id,
        multiplier=payload.multiplier,
        is_portal=payload.is_portal,
        is_additive=payload.is_additive,
        cap_per_billing_cycle=payload.cap_per_billing_cycle,
        cap_period_months=payload.cap_period_months,
        multiplier_group_id=payload.multiplier_group_id,
    )
    db.add(mult)
    await db.commit()
    res = await db.execute(select(Card).options(*_card_load_opts()).where(Card.id == card_id))
    return res.scalar_one()


@app.delete(
    "/admin/cards/{card_id}/multipliers/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["admin"],
)
async def admin_delete_card_multiplier(
    card_id: int,
    category_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CardCategoryMultiplier).where(
            CardCategoryMultiplier.card_id == card_id,
            CardCategoryMultiplier.category_id == category_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Multiplier not found for this card/category")
    await db.delete(row)
    await db.commit()


# ---- Multiplier Group CRUD ----


@app.get(
    "/admin/cards/{card_id}/multiplier-groups",
    response_model=list[CardMultiplierGroupRead],
    tags=["admin"],
)
async def admin_list_card_multiplier_groups(
    card_id: int,
    db: AsyncSession = Depends(get_db),
):
    card_result = await db.execute(select(Card).where(Card.id == card_id))
    if not card_result.scalar_one_or_none():
        raise _card_404(card_id)
    result = await db.execute(
        select(CardMultiplierGroup)
        .options(
            selectinload(CardMultiplierGroup.categories).selectinload(
                CardCategoryMultiplier.spend_category
            ),
            selectinload(CardMultiplierGroup.card)
            .selectinload(Card.rotating_history)
            .selectinload(CardRotatingHistory.spend_category),
        )
        .where(CardMultiplierGroup.card_id == card_id)
    )
    return result.scalars().all()


@app.post(
    "/admin/cards/{card_id}/multiplier-groups",
    response_model=CardMultiplierGroupRead,
    status_code=status.HTTP_201_CREATED,
    tags=["admin"],
)
async def admin_create_card_multiplier_group(
    card_id: int,
    payload: AdminCreateCardMultiplierGroupPayload,
    db: AsyncSession = Depends(get_db),
):
    card_result = await db.execute(select(Card).where(Card.id == card_id))
    if not card_result.scalar_one_or_none():
        raise _card_404(card_id)

    grp = CardMultiplierGroup(
        card_id=card_id,
        multiplier=payload.multiplier,
        cap_per_billing_cycle=payload.cap_per_billing_cycle,
        cap_period_months=payload.cap_period_months,
        top_n_categories=payload.top_n_categories,
        is_rotating=payload.is_rotating,
        is_additive=payload.is_additive,
    )
    db.add(grp)
    await db.flush()

    # Create CardCategoryMultiplier rows for each category in the group
    for cat_id in payload.category_ids:
        sc_result = await db.execute(
            select(SpendCategory).where(SpendCategory.id == cat_id)
        )
        if not sc_result.scalar_one_or_none():
            raise HTTPException(
                status_code=404, detail=f"SpendCategory id={cat_id} not found"
            )
        # Check for existing multiplier on this card/category
        existing = await db.execute(
            select(CardCategoryMultiplier).where(
                CardCategoryMultiplier.card_id == card_id,
                CardCategoryMultiplier.category_id == cat_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail=f"Multiplier for card {card_id} / category {cat_id} already exists",
            )
        db.add(
            CardCategoryMultiplier(
                card_id=card_id,
                category_id=cat_id,
                multiplier=payload.multiplier,
                multiplier_group_id=grp.id,
            )
        )

    await db.commit()
    # Reload with relationships
    result = await db.execute(
        select(CardMultiplierGroup)
        .options(
            selectinload(CardMultiplierGroup.categories).selectinload(
                CardCategoryMultiplier.spend_category
            ),
            selectinload(CardMultiplierGroup.card)
            .selectinload(Card.rotating_history)
            .selectinload(CardRotatingHistory.spend_category),
        )
        .where(CardMultiplierGroup.id == grp.id)
    )
    return result.scalar_one()


@app.patch(
    "/admin/cards/{card_id}/multiplier-groups/{group_id}",
    response_model=CardMultiplierGroupRead,
    tags=["admin"],
)
async def admin_update_card_multiplier_group(
    card_id: int,
    group_id: int,
    payload: AdminUpdateCardMultiplierGroupPayload,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CardMultiplierGroup).where(
            CardMultiplierGroup.id == group_id,
            CardMultiplierGroup.card_id == card_id,
        )
    )
    grp = result.scalar_one_or_none()
    if not grp:
        raise HTTPException(
            status_code=404,
            detail=f"MultiplierGroup id={group_id} not found for card {card_id}",
        )

    if payload.multiplier is not None:
        grp.multiplier = payload.multiplier
    if payload.cap_per_billing_cycle is not None:
        grp.cap_per_billing_cycle = payload.cap_per_billing_cycle
    if payload.cap_period_months is not None:
        grp.cap_period_months = payload.cap_period_months
    if payload.top_n_categories is not None:
        grp.top_n_categories = payload.top_n_categories
    if payload.is_rotating is not None:
        grp.is_rotating = payload.is_rotating
    if payload.is_additive is not None:
        grp.is_additive = payload.is_additive

    # If category_ids provided, replace the group's category memberships
    if payload.category_ids is not None:
        # Remove existing group category multipliers
        existing = await db.execute(
            select(CardCategoryMultiplier).where(
                CardCategoryMultiplier.multiplier_group_id == group_id
            )
        )
        for row in existing.scalars().all():
            await db.delete(row)

        mult = payload.multiplier if payload.multiplier is not None else grp.multiplier
        for cat_id in payload.category_ids:
            sc_result = await db.execute(
                select(SpendCategory).where(SpendCategory.id == cat_id)
            )
            if not sc_result.scalar_one_or_none():
                raise HTTPException(
                    status_code=404, detail=f"SpendCategory id={cat_id} not found"
                )
            # Check for conflicting standalone multiplier
            conflict = await db.execute(
                select(CardCategoryMultiplier).where(
                    CardCategoryMultiplier.card_id == card_id,
                    CardCategoryMultiplier.category_id == cat_id,
                    CardCategoryMultiplier.multiplier_group_id != group_id,
                )
            )
            if conflict.scalar_one_or_none():
                raise HTTPException(
                    status_code=409,
                    detail=f"Multiplier for card {card_id} / category {cat_id} already exists outside this group",
                )
            db.add(
                CardCategoryMultiplier(
                    card_id=card_id,
                    category_id=cat_id,
                    multiplier=mult,
                    multiplier_group_id=group_id,
                )
            )
    elif payload.multiplier is not None:
        # Sync multiplier to all category rows in the group
        existing = await db.execute(
            select(CardCategoryMultiplier).where(
                CardCategoryMultiplier.multiplier_group_id == group_id
            )
        )
        for row in existing.scalars().all():
            row.multiplier = payload.multiplier

    await db.commit()
    result = await db.execute(
        select(CardMultiplierGroup)
        .options(
            selectinload(CardMultiplierGroup.categories).selectinload(
                CardCategoryMultiplier.spend_category
            ),
            selectinload(CardMultiplierGroup.card)
            .selectinload(Card.rotating_history)
            .selectinload(CardRotatingHistory.spend_category),
        )
        .where(CardMultiplierGroup.id == group_id)
    )
    return result.scalar_one()


@app.delete(
    "/admin/cards/{card_id}/multiplier-groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["admin"],
)
async def admin_delete_card_multiplier_group(
    card_id: int,
    group_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CardMultiplierGroup).where(
            CardMultiplierGroup.id == group_id,
            CardMultiplierGroup.card_id == card_id,
        )
    )
    grp = result.scalar_one_or_none()
    if not grp:
        raise HTTPException(
            status_code=404,
            detail=f"MultiplierGroup id={group_id} not found for card {card_id}",
        )
    await db.delete(grp)
    await db.commit()


# ---- Rotating-category history (reference data, drives p_C inference) ----


@app.get(
    "/admin/cards/{card_id}/rotating-history",
    response_model=list[CardRotatingHistoryRead],
    tags=["admin"],
)
async def admin_list_card_rotating_history(
    card_id: int,
    db: AsyncSession = Depends(get_db),
):
    card_result = await db.execute(select(Card).where(Card.id == card_id))
    if not card_result.scalar_one_or_none():
        raise _card_404(card_id)
    result = await db.execute(
        select(CardRotatingHistory)
        .options(selectinload(CardRotatingHistory.spend_category))
        .where(CardRotatingHistory.card_id == card_id)
        .order_by(CardRotatingHistory.year.desc(), CardRotatingHistory.quarter.desc())
    )
    return result.scalars().all()


@app.post(
    "/admin/cards/{card_id}/rotating-history",
    response_model=CardRotatingHistoryRead,
    status_code=status.HTTP_201_CREATED,
    tags=["admin"],
)
async def admin_add_card_rotating_history(
    card_id: int,
    payload: AdminAddRotatingHistoryPayload,
    db: AsyncSession = Depends(get_db),
):
    card_result = await db.execute(select(Card).where(Card.id == card_id))
    if not card_result.scalar_one_or_none():
        raise _card_404(card_id)
    sc_result = await db.execute(
        select(SpendCategory).where(SpendCategory.id == payload.spend_category_id)
    )
    if not sc_result.scalar_one_or_none():
        raise HTTPException(
            status_code=404,
            detail=f"SpendCategory id={payload.spend_category_id} not found",
        )
    existing = await db.execute(
        select(CardRotatingHistory).where(
            CardRotatingHistory.card_id == card_id,
            CardRotatingHistory.year == payload.year,
            CardRotatingHistory.quarter == payload.quarter,
            CardRotatingHistory.spend_category_id == payload.spend_category_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Rotating history already exists for card {card_id} {payload.year}Q{payload.quarter} cat={payload.spend_category_id}",
        )
    row = CardRotatingHistory(
        card_id=card_id,
        year=payload.year,
        quarter=payload.quarter,
        spend_category_id=payload.spend_category_id,
    )
    db.add(row)
    await db.commit()
    result = await db.execute(
        select(CardRotatingHistory)
        .options(selectinload(CardRotatingHistory.spend_category))
        .where(CardRotatingHistory.id == row.id)
    )
    return result.scalar_one()


@app.delete(
    "/admin/cards/{card_id}/rotating-history/{history_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["admin"],
)
async def admin_delete_card_rotating_history(
    card_id: int,
    history_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CardRotatingHistory).where(
            CardRotatingHistory.id == history_id,
            CardRotatingHistory.card_id == card_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"Rotating history id={history_id} not found for card {card_id}",
        )
    await db.delete(row)
    await db.commit()


@app.post(
    "/admin/cards/{card_id}/credits",
    response_model=CardCreditRead,
    status_code=status.HTTP_201_CREATED,
    tags=["admin"],
)
async def admin_add_card_credit(
    card_id: int,
    payload: AdminAddCardCreditPayload,
    db: AsyncSession = Depends(get_db),
):
    card_result = await db.execute(select(Card).where(Card.id == card_id))
    if not card_result.scalar_one_or_none():
        raise _card_404(card_id)
    existing = await db.execute(
        select(CardCredit).where(
            CardCredit.card_id == card_id,
            CardCredit.credit_name == payload.credit_name.strip(),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Credit '{payload.credit_name}' already exists on this card")

    credit = CardCredit(
        card_id=card_id,
        credit_name=payload.credit_name.strip(),
        credit_value=payload.credit_value,
        is_one_time=payload.is_one_time,
    )
    db.add(credit)
    await db.commit()
    await db.refresh(credit)
    return credit


@app.delete(
    "/admin/cards/{card_id}/credits/{credit_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["admin"],
)
async def admin_delete_card_credit(
    card_id: int,
    credit_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CardCredit).where(
            CardCredit.id == credit_id,
            CardCredit.card_id == card_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Credit not found on this card")
    await db.delete(row)
    await db.commit()


# ---------------------------------------------------------------------------
# Schema conversion helper
# ---------------------------------------------------------------------------


def _wallet_to_schema(wallet) -> WalletResultSchema:
    card_schemas = [
        CardResultSchema(
            card_id=cr.card_id,
            card_name=cr.card_name,
            selected=cr.selected,
            effective_annual_fee=cr.effective_annual_fee,
            total_points=cr.total_points,
            annual_point_earn=cr.annual_point_earn,
            credit_valuation=cr.credit_valuation,
            annual_fee=cr.annual_fee,
            first_year_fee=cr.first_year_fee,
            sub=cr.sub,
            annual_bonus=cr.annual_bonus,
            sub_extra_spend=cr.sub_extra_spend,
            sub_spend_earn=cr.sub_spend_earn,
            sub_opp_cost_dollars=cr.sub_opp_cost_dollars,
            sub_opp_cost_gross_dollars=cr.sub_opp_cost_gross_dollars,
            avg_spend_multiplier=cr.avg_spend_multiplier,
            cents_per_point=cr.cents_per_point,
            effective_currency_name=cr.effective_currency_name,
            effective_currency_id=cr.effective_currency_id,
            effective_reward_kind=cr.effective_reward_kind,
            category_earn=[
                CategoryEarnItem(category=cat, points=pts)
                for cat, pts in cr.category_earn
            ],
        )
        for cr in wallet.card_results
    ]

    return WalletResultSchema(
        years_counted=wallet.years_counted,
        total_effective_annual_fee=wallet.total_effective_annual_fee,
        total_points_earned=wallet.total_points_earned,
        total_annual_pts=wallet.total_annual_pts,
        total_cash_reward_dollars=wallet.total_cash_reward_dollars,
        total_reward_value_usd=wallet.total_reward_value_usd,
        currency_pts=wallet.currency_pts,
        currency_pts_by_id=wallet.currency_pts_by_id,
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
