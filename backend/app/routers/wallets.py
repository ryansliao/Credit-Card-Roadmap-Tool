"""Wallet CRUD and wallet card management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..auth import get_current_user
from ..database import get_db
from ..db_helpers import ensure_all_other_wallet_spend_item
from ..helpers import (
    card_404,
    effective_earn_currency_ids_for_wallet,
    ensure_wallet_currency_rows_for_earning_currencies,
    get_user_wallet,
    wc_read,
    wallet_load_opts,
)
from ..models import (
    Card,
    Credit,
    User,
    Wallet,
    WalletCard,
    WalletCardCredit,
    WalletCurrencyBalance,
)
from ..schemas import (
    WalletCardCreate,
    WalletCardRead,
    WalletCardUpdate,
    WalletCreate,
    WalletRead,
    WalletUpdate,
)

router = APIRouter(tags=["wallets"])


@router.get("/wallets", response_model=list[WalletRead])
async def list_wallets(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List wallets for the authenticated user."""
    result = await db.execute(
        select(Wallet)
        .options(*wallet_load_opts())
        .where(Wallet.user_id == user.id)
        .order_by(Wallet.id)
    )
    wallets = result.scalars().all()
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
):
    wallet = Wallet(
        user_id=user.id,
        name=payload.name,
        description=payload.description,
        as_of_date=payload.as_of_date,
    )
    db.add(wallet)
    await db.flush()
    await ensure_all_other_wallet_spend_item(db, wallet.id)
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
    db: AsyncSession = Depends(get_db),
):
    await get_user_wallet(wallet_id, user, db)
    result = await db.execute(
        select(Wallet)
        .options(*wallet_load_opts())
        .where(Wallet.id == wallet_id)
    )
    wallet = result.scalar_one()
    read = WalletRead.model_validate(wallet)
    read.wallet_cards = [wc_read(wc_item, wc_item.card) for wc_item in wallet.wallet_cards]
    return read


@router.patch("/wallets/{wallet_id}", response_model=WalletRead)
async def update_wallet(
    wallet_id: int,
    payload: WalletUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_user_wallet(wallet_id, user, db)
    result = await db.execute(
        select(Wallet)
        .options(*wallet_load_opts())
        .where(Wallet.id == wallet_id)
    )
    wallet = result.scalar_one()
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(wallet, field, value)
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
):
    wallet = await get_user_wallet(wallet_id, user, db)
    await db.delete(wallet)
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
):
    await get_user_wallet(wallet_id, user, db)
    card_result = await db.execute(
        select(Card)
        .where(Card.id == payload.card_id)
        .options(selectinload(Card.issuer), selectinload(Card.network_tier))
    )
    card = card_result.scalar_one_or_none()
    if not card:
        raise card_404(payload.card_id)
    existing = await db.execute(
        select(WalletCard).where(
            WalletCard.wallet_id == wallet_id,
            WalletCard.card_id == payload.card_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Card {payload.card_id} is already in wallet {wallet_id}",
        )
    wc_obj = WalletCard(
        wallet_id=wallet_id,
        card_id=payload.card_id,
        added_date=payload.added_date,
        sub_points=payload.sub_points,
        sub_min_spend=payload.sub_min_spend,
        sub_months=payload.sub_months,
        sub_spend_earn=payload.sub_spend_earn,
        annual_bonus=payload.annual_bonus,
        annual_bonus_percent=payload.annual_bonus_percent,
        annual_bonus_first_year_only=payload.annual_bonus_first_year_only,
        years_counted=payload.years_counted,
        annual_fee=payload.annual_fee,
        first_year_fee=payload.first_year_fee,
        sub_earned_date=payload.sub_earned_date,
        closed_date=payload.closed_date,
        acquisition_type=payload.acquisition_type,
        panel=payload.panel,
    )
    db.add(wc_obj)
    await db.flush()

    if payload.credits:
        lib_ids = {c.library_credit_id for c in payload.credits}
        lib_rows = await db.execute(select(Credit).where(Credit.id.in_(lib_ids)))
        valid_ids = {row.id for row in lib_rows.scalars()}
        for entry in payload.credits:
            if entry.library_credit_id not in valid_ids:
                raise HTTPException(
                    status_code=404,
                    detail=f"Credit id={entry.library_credit_id} not found in library",
                )
            db.add(
                WalletCardCredit(
                    wallet_card_id=wc_obj.id,
                    library_credit_id=entry.library_credit_id,
                    value=entry.value,
                )
            )

    await ensure_wallet_currency_rows_for_earning_currencies(db, wallet_id)
    await db.commit()
    await db.refresh(wc_obj, attribute_names=["credit_overrides_rows"])
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
):
    """
    Partially update a wallet card. Supports updating SUB overrides, years_counted,
    sub_earned_date (mark when the SUB was earned), and closed_date (mark card as closed).
    """
    await get_user_wallet(wallet_id, user, db)
    result = await db.execute(
        select(WalletCard).where(
            WalletCard.wallet_id == wallet_id,
            WalletCard.card_id == card_id,
        )
    )
    wc_obj = result.scalar_one_or_none()
    if not wc_obj:
        raise HTTPException(
            status_code=404, detail=f"Card {card_id} not in wallet {wallet_id}"
        )
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(wc_obj, field, value)

    await db.commit()
    await db.refresh(wc_obj, attribute_names=["credit_overrides_rows"])
    card_result = await db.execute(
        select(Card)
        .where(Card.id == wc_obj.card_id)
        .options(selectinload(Card.issuer), selectinload(Card.network_tier))
    )
    card = card_result.scalar_one()
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
):
    await get_user_wallet(wallet_id, user, db)
    result = await db.execute(
        select(WalletCard).where(
            WalletCard.wallet_id == wallet_id,
            WalletCard.card_id == card_id,
        )
    )
    wc_obj = result.scalar_one_or_none()
    if not wc_obj:
        raise HTTPException(
            status_code=404,
            detail=f"Card {card_id} not in wallet {wallet_id}",
        )
    await db.delete(wc_obj)
    await db.flush()

    remaining_currency_ids = await effective_earn_currency_ids_for_wallet(db, wallet_id)
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
