"""Admin CRUD endpoints for reference data."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..helpers import card_404, card_load_opts
from ..models import (
    Card,
    CardCategoryMultiplier,
    CardMultiplierGroup,
    RotatingCategory,
    CoBrand,
    Currency,
    Issuer,
    NetworkTier,
    SpendCategory,
    WalletCard,
)
from ..schemas import (
    AdminAddCardMultiplierPayload,
    AdminAddRotatingHistoryPayload,
    AdminCreateCardMultiplierGroupPayload,
    AdminCreateCardPayload,
    AdminCreateCurrencyPayload,
    AdminCreateIssuerPayload,
    AdminCreateSpendCategoryPayload,
    AdminUpdateCardMultiplierGroupPayload,
    CardMultiplierGroupRead,
    CardRead,
    RotatingCategoryRead,
    CurrencyRead,
    IssuerRead,
    SpendCategoryRead,
)

router = APIRouter(tags=["admin"])


@router.post(
    "/admin/issuers",
    response_model=IssuerRead,
    status_code=status.HTTP_201_CREATED,
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


@router.post(
    "/admin/currencies",
    response_model=CurrencyRead,
    status_code=status.HTTP_201_CREATED,
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


@router.post(
    "/admin/spend-categories",
    response_model=SpendCategoryRead,
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_spend_category(
    payload: AdminCreateSpendCategoryPayload,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(SpendCategory).where(SpendCategory.category == payload.category.strip()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"SpendCategory '{payload.category}' already exists")
    sc = SpendCategory(category=payload.category.strip(), is_housing=payload.is_housing)
    db.add(sc)
    await db.commit()
    await db.refresh(sc)
    return sc


@router.post(
    "/admin/cards",
    response_model=CardRead,
    status_code=status.HTTP_201_CREATED,
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

    if payload.secondary_currency_id is not None:
        sec_cur = await db.execute(select(Currency).where(Currency.id == payload.secondary_currency_id))
        if not sec_cur.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"Secondary currency id={payload.secondary_currency_id} not found")

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
        annual_bonus_percent=payload.annual_bonus_percent,
        annual_bonus_first_year_only=payload.annual_bonus_first_year_only,
        transfer_enabler=payload.transfer_enabler,
        secondary_currency_id=payload.secondary_currency_id,
        secondary_currency_rate=payload.secondary_currency_rate,
        secondary_currency_cap_rate=payload.secondary_currency_cap_rate,
        accelerator_cost=payload.accelerator_cost,
        accelerator_spend_limit=payload.accelerator_spend_limit,
        accelerator_bonus_multiplier=payload.accelerator_bonus_multiplier,
        accelerator_max_activations=payload.accelerator_max_activations,
        sub_recurrence_months=payload.sub_recurrence_months,
        sub_family=payload.sub_family,
    )
    db.add(card)
    await db.commit()
    res = await db.execute(
        select(Card).options(*card_load_opts()).where(Card.id == card.id)
    )
    return res.scalar_one()


@router.delete(
    "/admin/cards/{card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def admin_delete_card(
    card_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Card).where(Card.id == card_id))
    card = result.scalar_one_or_none()
    if not card:
        raise card_404(card_id)
    wc_count = await db.execute(select(WalletCard.id).where(WalletCard.card_id == card_id))
    if wc_count.scalars().first() is not None:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete card — it is used in one or more wallets. Remove it from all wallets first.",
        )
    await db.delete(card)
    await db.commit()


@router.post(
    "/admin/cards/{card_id}/multipliers",
    response_model=CardRead,
    status_code=status.HTTP_201_CREATED,
)
async def admin_add_card_multiplier(
    card_id: int,
    payload: AdminAddCardMultiplierPayload,
    db: AsyncSession = Depends(get_db),
):
    card_result = await db.execute(select(Card).where(Card.id == card_id))
    if not card_result.scalar_one_or_none():
        raise card_404(card_id)
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
    res = await db.execute(select(Card).options(*card_load_opts()).where(Card.id == card_id))
    return res.scalar_one()


@router.delete(
    "/admin/cards/{card_id}/multipliers/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
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


@router.get(
    "/admin/cards/{card_id}/multiplier-groups",
    response_model=list[CardMultiplierGroupRead],
)
async def admin_list_card_multiplier_groups(
    card_id: int,
    db: AsyncSession = Depends(get_db),
):
    card_result = await db.execute(select(Card).where(Card.id == card_id))
    if not card_result.scalar_one_or_none():
        raise card_404(card_id)
    result = await db.execute(
        select(CardMultiplierGroup)
        .options(
            selectinload(CardMultiplierGroup.categories).selectinload(
                CardCategoryMultiplier.spend_category
            ),
            selectinload(CardMultiplierGroup.card)
            .selectinload(Card.rotating_categories)
            .selectinload(RotatingCategory.spend_category),
        )
        .where(CardMultiplierGroup.card_id == card_id)
    )
    return result.scalars().all()


@router.post(
    "/admin/cards/{card_id}/multiplier-groups",
    response_model=CardMultiplierGroupRead,
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_card_multiplier_group(
    card_id: int,
    payload: AdminCreateCardMultiplierGroupPayload,
    db: AsyncSession = Depends(get_db),
):
    card_result = await db.execute(select(Card).where(Card.id == card_id))
    if not card_result.scalar_one_or_none():
        raise card_404(card_id)

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

    for cat_id in payload.category_ids:
        sc_result = await db.execute(
            select(SpendCategory).where(SpendCategory.id == cat_id)
        )
        if not sc_result.scalar_one_or_none():
            raise HTTPException(
                status_code=404, detail=f"SpendCategory id={cat_id} not found"
            )
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
    result = await db.execute(
        select(CardMultiplierGroup)
        .options(
            selectinload(CardMultiplierGroup.categories).selectinload(
                CardCategoryMultiplier.spend_category
            ),
            selectinload(CardMultiplierGroup.card)
            .selectinload(Card.rotating_categories)
            .selectinload(RotatingCategory.spend_category),
        )
        .where(CardMultiplierGroup.id == grp.id)
    )
    return result.scalar_one()


@router.patch(
    "/admin/cards/{card_id}/multiplier-groups/{group_id}",
    response_model=CardMultiplierGroupRead,
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

    if payload.category_ids is not None:
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
            .selectinload(Card.rotating_categories)
            .selectinload(RotatingCategory.spend_category),
        )
        .where(CardMultiplierGroup.id == group_id)
    )
    return result.scalar_one()


@router.delete(
    "/admin/cards/{card_id}/multiplier-groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
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


# ---- Rotating-category history ----


@router.get(
    "/admin/cards/{card_id}/rotating-history",
    response_model=list[RotatingCategoryRead],
)
async def admin_list_card_rotating_history(
    card_id: int,
    db: AsyncSession = Depends(get_db),
):
    card_result = await db.execute(select(Card).where(Card.id == card_id))
    if not card_result.scalar_one_or_none():
        raise card_404(card_id)
    result = await db.execute(
        select(RotatingCategory)
        .options(selectinload(RotatingCategory.spend_category))
        .where(RotatingCategory.card_id == card_id)
        .order_by(RotatingCategory.year.desc(), RotatingCategory.quarter.desc())
    )
    return result.scalars().all()


@router.post(
    "/admin/cards/{card_id}/rotating-history",
    response_model=RotatingCategoryRead,
    status_code=status.HTTP_201_CREATED,
)
async def admin_add_card_rotating_history(
    card_id: int,
    payload: AdminAddRotatingHistoryPayload,
    db: AsyncSession = Depends(get_db),
):
    card_result = await db.execute(select(Card).where(Card.id == card_id))
    if not card_result.scalar_one_or_none():
        raise card_404(card_id)
    sc_result = await db.execute(
        select(SpendCategory).where(SpendCategory.id == payload.spend_category_id)
    )
    if not sc_result.scalar_one_or_none():
        raise HTTPException(
            status_code=404,
            detail=f"SpendCategory id={payload.spend_category_id} not found",
        )
    existing = await db.execute(
        select(RotatingCategory).where(
            RotatingCategory.card_id == card_id,
            RotatingCategory.year == payload.year,
            RotatingCategory.quarter == payload.quarter,
            RotatingCategory.spend_category_id == payload.spend_category_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Rotating history already exists for card {card_id} {payload.year}Q{payload.quarter} cat={payload.spend_category_id}",
        )
    row = RotatingCategory(
        card_id=card_id,
        year=payload.year,
        quarter=payload.quarter,
        spend_category_id=payload.spend_category_id,
    )
    db.add(row)
    await db.commit()
    result = await db.execute(
        select(RotatingCategory)
        .options(selectinload(RotatingCategory.spend_category))
        .where(RotatingCategory.id == row.id)
    )
    return result.scalar_one()


@router.delete(
    "/admin/cards/{card_id}/rotating-history/{history_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def admin_delete_card_rotating_history(
    card_id: int,
    history_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RotatingCategory).where(
            RotatingCategory.id == history_id,
            RotatingCategory.card_id == card_id,
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
