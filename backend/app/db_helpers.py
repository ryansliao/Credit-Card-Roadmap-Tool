"""
Runtime DB -> calculator projection helpers.

These helpers do not own reference data or seed content; they only read the
current database state produced by the workbook sync and the running app.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .calculator import CardData, CreditLine, CurrencyData
from .constants import ALL_OTHER_CATEGORY
from .models import (
    Card,
    CardCategoryMultiplier,
    CardMultiplierGroup,
    CardRotatingHistory,
    Currency,
    SpendCategory,
    Wallet,
    WalletCardCredit,
    WalletCardGroupSelection,
    WalletCardMultiplier,
    WalletCardRotationOverride,
    WalletCurrencyCpp,
    WalletPortalShare,
    WalletSpendCategory,
    WalletSpendCategoryMapping,
    WalletSpendItem,
)

# Re-export for callers that import this name from db_helpers.
ALL_OTHER_SPEND_NAME = ALL_OTHER_CATEGORY

if TYPE_CHECKING:
    from .models import WalletCard


def _currency_data(
    orm_currency: Currency,
    cpp_overrides: dict[int, float] | None = None,
) -> CurrencyData:
    """Convert a Currency ORM object to a CurrencyData (optional CPP overrides by currency id).

    Overrides apply to this row and any nested ``converts_to_currency`` (same as the calculator's
    effective-currency CPP when a card upgrades).
    """
    oid = orm_currency.id
    cpp_override = cpp_overrides.get(oid) if cpp_overrides else None
    rk = getattr(orm_currency, "reward_kind", None) or "points"
    default_cpp = float(orm_currency.cents_per_point)
    if rk == "cash":
        cpp = default_cpp
    else:
        cpp = (
            float(cpp_override)
            if cpp_override is not None
            else default_cpp
        )
    converts_to: CurrencyData | None = None
    if orm_currency.converts_to_currency is not None:
        converts_to = _currency_data(orm_currency.converts_to_currency, cpp_overrides)
    converts_at_rate = getattr(orm_currency, "converts_at_rate", None)
    return CurrencyData(
        id=orm_currency.id,
        name=orm_currency.name,
        reward_kind=rk,
        cents_per_point=cpp,
        comparison_cpp=default_cpp,
        cash_transfer_rate=orm_currency.cash_transfer_rate if orm_currency.cash_transfer_rate is not None else 1.0,
        partner_transfer_rate=orm_currency.partner_transfer_rate,
        converts_to_currency=converts_to,
        converts_at_rate=converts_at_rate if converts_at_rate is not None else 1.0,
        no_transfer_cpp=getattr(orm_currency, "no_transfer_cpp", None),
        no_transfer_rate=getattr(orm_currency, "no_transfer_rate", None),
    )


async def load_wallet_cpp_overrides(
    session: AsyncSession, wallet_id: int
) -> dict[int, float]:
    """Load wallet-scoped cents-per-point overrides: currency_id -> cents_per_point."""
    result = await session.execute(
        select(WalletCurrencyCpp).where(WalletCurrencyCpp.wallet_id == wallet_id)
    )
    rows = result.scalars().all()
    return {row.currency_id: row.cents_per_point for row in rows}


async def load_card_data(
    session: AsyncSession, cpp_overrides: dict[int, float] | None = None
) -> list[CardData]:
    """Load all cards with their full relationship tree as CardData objects.
    If cpp_overrides is provided, those values override each card's currency CPP.
    """
    result = await session.execute(
        select(Card).options(
            selectinload(Card.issuer),
            selectinload(Card.currency_obj)
            .selectinload(Currency.converts_to_currency),
            selectinload(Card.multipliers).selectinload(CardCategoryMultiplier.spend_category),
            selectinload(Card.multiplier_groups).selectinload(CardMultiplierGroup.categories).selectinload(CardCategoryMultiplier.spend_category),
            selectinload(Card.rotating_history).selectinload(CardRotatingHistory.spend_category),
            selectinload(Card.credits),
        )
    )
    cards = result.scalars().all()

    # Build a parent-id → descendants map of spend categories so portal
    # multipliers can expand through the hierarchy. The user typically has
    # a "Travel" parent with leaves like Hotels / Airlines / Rideshare /
    # Transit; the wallet's spend lives on the leaves, so a portal premium
    # registered against "Travel" needs to be replicated to each descendant
    # for the slider to actually move EAF.
    sc_rows = await session.execute(select(SpendCategory))
    sc_by_id: dict[int, SpendCategory] = {sc.id: sc for sc in sc_rows.scalars()}
    children_by_parent: dict[int, list[SpendCategory]] = {}
    for sc in sc_by_id.values():
        if sc.parent_id is not None:
            children_by_parent.setdefault(sc.parent_id, []).append(sc)

    def _descendant_names(root_id: int) -> list[str]:
        """Return [root.category, …all descendant categories…] for use in
        portal_premiums expansion. Walks the tree breadth-first."""
        out: list[str] = []
        root = sc_by_id.get(root_id)
        if root is None:
            return out
        out.append(root.category)
        stack = [root_id]
        while stack:
            pid = stack.pop()
            for child in children_by_parent.get(pid, []):
                out.append(child.category)
                stack.append(child.id)
        return out

    out: list[CardData] = []
    for card in cards:
        currency = _currency_data(card.currency_obj, cpp_overrides)

        # ----- Multiplier aggregation (additive-aware) -----
        # A category may now have multiple rows on a single card: one
        # standalone (non-additive replacement OR additive premium), plus one
        # row per group it belongs to. Aggregate them so the calculator sees:
        #   - multipliers[cat] = always-on rate per dollar
        #         = standalone non-additive (if any) OR base + Σ standalone additive premiums
        #   - card.multiplier_groups carries grouped rows separately (capped premiums)
        # Only standalone rows (multiplier_group_id IS NULL) are considered here.
        # All Other (case-insensitive) is the implicit base for the additive sum.
        all_other_rate = 1.0
        for m in card.multipliers:
            if (m.category or "").strip().lower() == "all other" and getattr(m, "multiplier_group_id", None) is None:
                all_other_rate = float(m.multiplier)
                break

        # Standalone rows: classify into non-additive overrides vs additive premiums.
        # Portal-flagged standalone rows are EXCLUDED from the always-on dict —
        # they're collected separately into portal_premiums and gated by the
        # wallet's per-issuer portal share at calc time. Each portal row is
        # ALSO replicated across the descendants of the named spend category
        # in the hierarchy, so a "Travel" portal multiplier covers Hotels,
        # Airlines, Rideshare, Transit, etc. — wherever the user actually
        # has spend on the leaf categories.
        non_add_overrides: dict[str, float] = {}
        additive_premiums: dict[str, float] = {}
        portal_premiums_list: list[tuple[str, float, bool]] = []
        for m in card.multipliers:
            if getattr(m, "multiplier_group_id", None) is not None:
                continue  # grouped rows are aggregated below
            cat = m.category
            if not cat:
                continue
            if (cat or "").strip().lower() == "all other":
                continue  # the base is captured by all_other_rate above
            is_add = bool(getattr(m, "is_additive", False))
            if bool(getattr(m, "is_portal", False)):
                # Expand to the named category + all descendants in the
                # spend-category hierarchy. If the named category has no
                # children we still get a single entry (the named row).
                names = _descendant_names(m.category_id) or [cat]
                for name in names:
                    portal_premiums_list.append(
                        (name.strip().lower(), float(m.multiplier), is_add)
                    )
                continue
            if is_add:
                additive_premiums[cat] = additive_premiums.get(cat, 0.0) + float(m.multiplier)
            else:
                # Non-additive replaces the base for this category.
                non_add_overrides[cat] = float(m.multiplier)

        multipliers: dict[str, float] = {}
        # Always re-emit the base under "All Other" so callers can read it.
        multipliers["All Other"] = all_other_rate
        # Categories with a non-additive standalone use that value directly.
        for cat, val in non_add_overrides.items():
            multipliers[cat] = val
        # Categories with additive premiums layer onto the base (unless a
        # non-additive override exists for the same category — that wins).
        for cat, premium in additive_premiums.items():
            if cat in non_add_overrides:
                continue
            multipliers[cat] = all_other_rate + premium

        portal_categories: set[str] = {
            m.category for m in card.multipliers
            if getattr(m, "is_portal", False) and m.category
        }
        # Per-category activation probabilities computed once from this card's
        # rotating_history rows: p_C = (active quarters for C) / (distinct quarters in history).
        # Used by the calculator to size per-category caps on rotating groups.
        history_rows = getattr(card, "rotating_history", []) or []
        rotation_quarters = {(h.year, h.quarter) for h in history_rows}
        total_history_q = len(rotation_quarters) or 1
        rotation_counts: dict[int, int] = {}
        for h in history_rows:
            rotation_counts[h.spend_category_id] = rotation_counts.get(h.spend_category_id, 0) + 1
        # Map category_id -> name (lowercase keys for case-insensitive matching downstream)
        cat_id_to_name: dict[int, str] = {}
        for h in history_rows:
            sc = getattr(h, "spend_category", None)
            if sc is not None:
                cat_id_to_name[h.spend_category_id] = sc.category

        # Group metadata: (multiplier, categories, top_n, group_id, cap_amount,
        # cap_period_months, is_rotating, rotation_weights, is_additive)
        # rotation_weights is keyed by exact category name as it appears in spend_categories.
        multiplier_groups_list: list[
            tuple[
                float,
                list[str],
                int | None,
                int | None,
                float | None,
                int | None,
                bool,
                dict[str, float],
                bool,
            ]
        ] = []
        for grp in getattr(card, "multiplier_groups", []) or []:
            top_n = getattr(grp, "top_n_categories", None)
            if top_n is None and getattr(grp, "top_category_only", False):
                top_n = 1
            cats = [c.category for c in getattr(grp, "categories", []) if getattr(c, "category", None)]
            cap_amount = getattr(grp, "cap_per_billing_cycle", None)
            cap_months = getattr(grp, "cap_period_months", None)
            is_rotating = bool(getattr(grp, "is_rotating", False))
            is_additive = bool(getattr(grp, "is_additive", False))

            rotation_weights: dict[str, float] = {}
            if is_rotating and history_rows:
                group_cat_ids = {c.category_id for c in getattr(grp, "categories", [])}
                for cm in getattr(grp, "categories", []):
                    cat_name = getattr(cm, "category", None)
                    if not cat_name:
                        continue
                    count = rotation_counts.get(cm.category_id, 0)
                    if cm.category_id in group_cat_ids:
                        rotation_weights[cat_name] = count / total_history_q

            multiplier_groups_list.append(
                (grp.multiplier, cats, top_n, grp.id, cap_amount, cap_months,
                 is_rotating, rotation_weights, is_additive)
            )
        credit_lines = [
            CreditLine(
                library_credit_id=c.id,
                name=c.credit_name,
                value=c.credit_value,
                one_time=bool(getattr(c, "is_one_time", False)),
            )
            for c in card.credits
        ]

        out.append(
            CardData(
                id=card.id,
                name=card.name,
                issuer_name=card.issuer.name,
                currency=currency,
                annual_fee=card.annual_fee,
                first_year_fee=card.first_year_fee,
                sub=card.sub if card.sub is not None else 0,
                sub_min_spend=card.sub_min_spend,
                sub_months=card.sub_months,
                sub_spend_earn=card.sub_spend_earn if card.sub_spend_earn is not None else 0,
                annual_bonus=card.annual_bonus if card.annual_bonus is not None else 0,
                multipliers=multipliers,
                multiplier_groups=multiplier_groups_list,
                credit_lines=credit_lines,
                portal_categories=portal_categories,
                portal_premiums=portal_premiums_list,
                transfer_enabler=bool(getattr(card, "transfer_enabler", False)),
            )
        )
    return out


async def ensure_all_other_wallet_spend_category(session: AsyncSession, wallet_id: int) -> None:
    """
    If the wallet has no spend category named 'All Other', create one with amount 0
    and a single mapping: 100% to the global SpendCategory 'All Other'.
    """
    wallet_row = await session.execute(select(Wallet).where(Wallet.id == wallet_id))
    if wallet_row.scalar_one_or_none() is None:
        return
    sc_result = await session.execute(
        select(SpendCategory).where(SpendCategory.category == ALL_OTHER_SPEND_NAME)
    )
    sc = sc_result.scalar_one_or_none()
    if sc is None:
        return
    existing = await session.execute(
        select(WalletSpendCategory).where(
            WalletSpendCategory.wallet_id == wallet_id,
            WalletSpendCategory.name == ALL_OTHER_SPEND_NAME,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return
    wsc = WalletSpendCategory(
        wallet_id=wallet_id, name=ALL_OTHER_SPEND_NAME, amount=0.0
    )
    session.add(wsc)
    await session.flush()
    session.add(
        WalletSpendCategoryMapping(
            wallet_spend_category_id=wsc.id,
            spend_category_id=sc.id,
            allocation=0.0,
        )
    )


async def load_wallet_spend(
    session: AsyncSession,
    wallet_id: int,
) -> dict[str, float]:
    """
    Load spend dict for a wallet by summing WalletSpendCategoryMapping allocations per card category.
    Legacy function for backward compatibility with old WalletSpendCategory rows.
    """
    result = await session.execute(
        select(WalletSpendCategory)
        .options(
            selectinload(WalletSpendCategory.mappings).selectinload(WalletSpendCategoryMapping.spend_category)
        )
        .where(WalletSpendCategory.wallet_id == wallet_id)
    )
    wallet_spend_categories = result.scalars().all()
    spend: dict[str, float] = {}
    for wsc in wallet_spend_categories:
        for mapping in wsc.mappings:
            if mapping.spend_category:
                cat_name = mapping.spend_category.category
                spend[cat_name] = spend.get(cat_name, 0.0) + mapping.allocation
    return spend


async def ensure_all_other_wallet_spend_item(session: AsyncSession, wallet_id: int) -> None:
    """
    Ensure the wallet has a WalletSpendItem for the 'All Other' SpendCategory.
    Creates one with amount=0 if missing.
    """
    wallet_row = await session.execute(select(Wallet).where(Wallet.id == wallet_id))
    if wallet_row.scalar_one_or_none() is None:
        return
    sc_result = await session.execute(
        select(SpendCategory).where(SpendCategory.category == ALL_OTHER_SPEND_NAME)
    )
    sc = sc_result.scalar_one_or_none()
    if sc is None:
        return
    existing = await session.execute(
        select(WalletSpendItem).where(
            WalletSpendItem.wallet_id == wallet_id,
            WalletSpendItem.spend_category_id == sc.id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return
    session.add(WalletSpendItem(wallet_id=wallet_id, spend_category_id=sc.id, amount=0.0))


async def load_wallet_spend_items(
    session: AsyncSession,
    wallet_id: int,
) -> dict[str, float]:
    """
    Load spend dict for a wallet from WalletSpendItem rows.
    SpendCategory.category is directly the card multiplier category name.
    """
    result = await session.execute(
        select(WalletSpendItem)
        .options(selectinload(WalletSpendItem.spend_category))
        .where(WalletSpendItem.wallet_id == wallet_id)
    )
    items = result.scalars().all()
    spend: dict[str, float] = {}
    for item in items:
        cat_name = item.spend_category.category if item.spend_category else ALL_OTHER_SPEND_NAME
        spend[cat_name] = spend.get(cat_name, 0.0) + item.amount
    return spend


async def load_wallet_card_credits(
    session: AsyncSession,
    wallet_id: int,
) -> dict[int, list[WalletCardCredit]]:
    """
    Load all WalletCardCredit rows for cards in the given wallet.
    Returns dict keyed by wallet_card_id.
    """
    from .models import WalletCard as WalletCardModel
    result = await session.execute(
        select(WalletCardCredit)
        .join(WalletCardModel, WalletCardModel.id == WalletCardCredit.wallet_card_id)
        .where(WalletCardModel.wallet_id == wallet_id)
    )
    rows = result.scalars().all()
    out: dict[int, list[WalletCardCredit]] = {}
    for row in rows:
        out.setdefault(row.wallet_card_id, []).append(row)
    return out


async def load_wallet_card_multipliers(
    session: AsyncSession,
    wallet_id: int,
) -> list[WalletCardMultiplier]:
    """Load all WalletCardMultiplier rows for the given wallet."""
    result = await session.execute(
        select(WalletCardMultiplier)
        .options(selectinload(WalletCardMultiplier.spend_category))
        .where(WalletCardMultiplier.wallet_id == wallet_id)
    )
    return list(result.scalars().all())


def apply_wallet_card_overrides(
    card_data_list: list[CardData],
    wallet_cards: list["WalletCard"],
    library_cards_by_id: dict[int, Card] | None = None,
    wallet_credit_rows: dict[int, list[WalletCardCredit]] | None = None,
) -> list[CardData]:
    """
    Return CardData copies with wallet-level overrides: SUB fields, fees, statement credits.
    Null wallet fields keep the library Card value.
    wallet_credit_rows: dict keyed by wallet_card_id -> list of WalletCardCredit rows.
    """
    wc_by_card_id: dict[int, "WalletCard"] = {wc.card_id: wc for wc in wallet_cards}
    # Build credit override lookup: (wallet_card_id, library_credit_id) -> (value, is_one_time)
    credit_lookup: dict[tuple[int, int], tuple[float, bool]] = {}
    if wallet_credit_rows:
        for wc_id, rows in wallet_credit_rows.items():
            for row in rows:
                credit_lookup[(wc_id, row.library_credit_id)] = (row.value, row.is_one_time)

    out: list[CardData] = []
    for cd in card_data_list:
        wc = wc_by_card_id.get(cd.id)
        if not wc:
            out.append(cd)
            continue

        annual_fee = (
            wc.annual_fee if wc.annual_fee is not None else cd.annual_fee
        )
        first_year_fee = (
            wc.first_year_fee if wc.first_year_fee is not None else cd.first_year_fee
        )

        lib = library_cards_by_id.get(wc.card_id) if library_cards_by_id else None
        lib_by_id = {cr.id: cr for cr in lib.credits} if lib is not None else {}
        merged_lines: list[CreditLine] = []
        for line in cd.credit_lines:
            cr = lib_by_id.get(line.library_credit_id)
            # Check wallet-level credit row first, then fall back to library
            override_key = (wc.id, line.library_credit_id)
            if override_key in credit_lookup:
                val, one_time = credit_lookup[override_key]
            else:
                val = line.value
                one_time = bool(cr.is_one_time) if cr is not None else line.one_time
            merged_lines.append(
                CreditLine(
                    library_credit_id=line.library_credit_id,
                    name=line.name,
                    value=val,
                    one_time=one_time,
                )
            )

        out.append(
            dataclasses.replace(
                cd,
                sub=wc.sub if wc.sub is not None else cd.sub,
                sub_min_spend=(
                    wc.sub_min_spend
                    if wc.sub_min_spend is not None
                    else cd.sub_min_spend
                ),
                sub_months=(
                    wc.sub_months if wc.sub_months is not None else cd.sub_months
                ),
                sub_spend_earn=(
                    wc.sub_spend_earn
                    if wc.sub_spend_earn is not None
                    else cd.sub_spend_earn
                ),
                annual_bonus=(
                    wc.annual_bonus if wc.annual_bonus is not None else cd.annual_bonus
                ),
                annual_fee=annual_fee,
                first_year_fee=first_year_fee,
                credit_lines=merged_lines,
                wallet_added_date=wc.added_date,
                wallet_closed_date=wc.closed_date,
                sub_projected_earn_date=wc.sub_projected_earn_date,
            )
        )
    return out


def apply_wallet_card_multiplier_overrides(
    card_data_list: list[CardData],
    wallet_multipliers: list[WalletCardMultiplier],
) -> list[CardData]:
    """
    Return CardData copies with wallet-level multiplier overrides applied.
    For each WalletCardMultiplier row, patches card_data.multipliers[category] = override_multiplier.
    Applied before the calculator runs, so top-N group logic sees the patched values.
    """
    if not wallet_multipliers:
        return card_data_list

    # Build lookup: card_id -> {category_name: multiplier}
    overrides_by_card: dict[int, dict[str, float]] = {}
    for wm in wallet_multipliers:
        cat = wm.category
        if cat:
            overrides_by_card.setdefault(wm.card_id, {})[cat] = wm.multiplier

    out: list[CardData] = []
    for cd in card_data_list:
        card_overrides = overrides_by_card.get(cd.id)
        if not card_overrides:
            out.append(cd)
            continue
        patched_multipliers = dict(cd.multipliers)
        patched_multipliers.update(card_overrides)
        out.append(dataclasses.replace(cd, multipliers=patched_multipliers))
    return out


async def load_wallet_card_group_selections(
    session: AsyncSession,
    wallet_id: int,
) -> dict[int, dict[int, set[str]]]:
    """
    Load manual group category selections for cards in a wallet.
    Returns: {card_id: {group_id: {category_name, ...}}}
    """
    from .models import WalletCard as WalletCardModel

    result = await session.execute(
        select(WalletCardGroupSelection)
        .options(selectinload(WalletCardGroupSelection.spend_category))
        .join(WalletCardModel, WalletCardModel.id == WalletCardGroupSelection.wallet_card_id)
        .where(WalletCardModel.wallet_id == wallet_id)
    )
    rows = result.scalars().all()
    # Build: card_id -> {group_id -> {category_name, ...}}
    # We need card_id from the wallet_card relationship
    wc_ids: set[int] = {r.wallet_card_id for r in rows}
    if not wc_ids:
        return {}
    wc_result = await session.execute(
        select(WalletCardModel).where(WalletCardModel.id.in_(wc_ids))
    )
    wc_map = {wc.id: wc.card_id for wc in wc_result.scalars().all()}

    out: dict[int, dict[int, set[str]]] = {}
    for r in rows:
        card_id = wc_map.get(r.wallet_card_id)
        if card_id is None:
            continue
        cat_name = r.spend_category.category if r.spend_category else ""
        if not cat_name:
            continue
        out.setdefault(card_id, {}).setdefault(r.multiplier_group_id, set()).add(cat_name)
    return out


def apply_wallet_card_group_selections(
    card_data_list: list[CardData],
    selections: dict[int, dict[int, set[str]]],
) -> list[CardData]:
    """
    Return CardData copies with manual group category selections applied.
    Sets CardData.group_selected_categories for each card that has selections.
    """
    if not selections:
        return card_data_list
    out: list[CardData] = []
    for cd in card_data_list:
        card_sels = selections.get(cd.id)
        if not card_sels:
            out.append(cd)
            continue
        out.append(dataclasses.replace(cd, group_selected_categories=card_sels))
    return out


async def load_wallet_card_rotation_overrides(
    session: AsyncSession,
    wallet_id: int,
) -> dict[int, dict[tuple[int, int], set[str]]]:
    """
    Load rotation overrides for cards in a wallet.
    Returns: {card_id: {(year, quarter): {category_name_lower, ...}}}.
    """
    from .models import WalletCard as WalletCardModel

    result = await session.execute(
        select(WalletCardRotationOverride)
        .options(selectinload(WalletCardRotationOverride.spend_category))
        .join(
            WalletCardModel,
            WalletCardModel.id == WalletCardRotationOverride.wallet_card_id,
        )
        .where(WalletCardModel.wallet_id == wallet_id)
    )
    rows = result.scalars().all()
    if not rows:
        return {}

    wc_ids = {r.wallet_card_id for r in rows}
    wc_result = await session.execute(
        select(WalletCardModel).where(WalletCardModel.id.in_(wc_ids))
    )
    wc_to_card = {wc.id: wc.card_id for wc in wc_result.scalars().all()}

    out: dict[int, dict[tuple[int, int], set[str]]] = {}
    for r in rows:
        card_id = wc_to_card.get(r.wallet_card_id)
        if card_id is None:
            continue
        cat = r.spend_category.category if r.spend_category else ""
        if not cat:
            continue
        out.setdefault(card_id, {}).setdefault((r.year, r.quarter), set()).add(
            cat.strip().lower()
        )
    return out


def apply_wallet_card_rotation_overrides(
    card_data_list: list[CardData],
    overrides: dict[int, dict[tuple[int, int], set[str]]],
) -> list[CardData]:
    """
    Return CardData copies with rotation_overrides populated for any card with
    pinned (year, quarter) → category(s) selections in this wallet.
    """
    if not overrides:
        return card_data_list
    out: list[CardData] = []
    for cd in card_data_list:
        card_overrides = overrides.get(cd.id)
        if not card_overrides:
            out.append(cd)
            continue
        out.append(dataclasses.replace(cd, rotation_overrides=card_overrides))
    return out


async def load_wallet_portal_shares(
    session: AsyncSession,
    wallet_id: int,
) -> dict[int, float]:
    """Load per-issuer portal shares for one wallet. Returns {issuer_id: share}.
    Issuers without a row default to share=0 (the calculator's behavior is to
    not credit portal multipliers in that case)."""
    result = await session.execute(
        select(WalletPortalShare).where(WalletPortalShare.wallet_id == wallet_id)
    )
    return {row.issuer_id: float(row.share) for row in result.scalars()}


def apply_wallet_portal_shares(
    card_data_list: list[CardData],
    shares_by_issuer: dict[int, float],
    cards_orm_by_id: dict[int, "CardLike"] | None = None,
) -> list[CardData]:
    """
    Return CardData copies with `portal_share` set from the wallet's per-issuer
    shares. Cards whose issuer has no share row keep portal_share=0 (default).

    The CardData itself doesn't carry an issuer_id (just an issuer_name string),
    so the caller passes a `cards_orm_by_id` mapping for issuer lookup. If not
    supplied, falls back to matching by lowercased issuer_name against any
    issuer name we can resolve from `shares_by_issuer` keys — but that's
    rarely available, so the orm map is the recommended path.
    """
    if not shares_by_issuer or not card_data_list:
        return card_data_list
    out: list[CardData] = []
    for cd in card_data_list:
        share = 0.0
        if cards_orm_by_id is not None:
            orm = cards_orm_by_id.get(cd.id)
            if orm is not None:
                issuer_id = getattr(orm, "issuer_id", None)
                if issuer_id is not None:
                    share = shares_by_issuer.get(issuer_id, 0.0)
        if share <= 0.0:
            out.append(cd)
            continue
        out.append(dataclasses.replace(cd, portal_share=share))
    return out


# Marker for the orm map type — kept loose to avoid a circular import on Card.
class CardLike:  # pragma: no cover
    issuer_id: int
