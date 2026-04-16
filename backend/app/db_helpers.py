"""Runtime DB -> calculator projection helpers.

This module contains:
- ``load_*`` functions: DB loading (DEPRECATED - use CalculatorDataService)
- ``apply_*`` functions: Pure transforms that don't access DB (still used)

The ``load_*`` functions have been migrated to ``CalculatorDataService``.
Use the service instead of calling these functions directly.
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
    NetworkTier,
    RotatingCategory,
    Currency,
    SpendCategory,
    Wallet,
    WalletCardCategoryPriority,
    WalletCardCredit,
    WalletCardGroupSelection,
    WalletCardMultiplier,
    WalletCurrencyCpp,
    WalletPortalShare,
    WalletSpendItem,
)

if TYPE_CHECKING:
    from .models import WalletCard


def _currency_data(
    orm_currency: Currency,
    cpp_overrides: dict[int, float] | None = None,
) -> CurrencyData:
    """Convert a Currency ORM object to a CurrencyData (optional CPP overrides by currency id).

    Overrides apply to this row and any nested ``converts_to_currency`` (same as the calculator's
    effective-currency CPP when a card upgrades). ``comparison_cpp`` mirrors the wallet-aware
    CPP so every wallet metric — including balance/total-points views — values points at the
    wallet's chosen CPP rather than the library default.
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
        comparison_cpp=cpp,
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


async def load_currency_defaults(session: AsyncSession) -> dict[int, float]:
    """Load default cents-per-point for all currencies: currency_id -> cents_per_point."""
    result = await session.execute(select(Currency))
    return {c.id: c.cents_per_point for c in result.scalars()}


async def load_currency_kinds(session: AsyncSession) -> dict[int, str]:
    """Load reward_kind for all currencies: currency_id -> 'cash' | 'points'."""
    result = await session.execute(select(Currency))
    return {c.id: c.reward_kind for c in result.scalars()}


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
            selectinload(Card.secondary_currency_obj)
            .selectinload(Currency.converts_to_currency),
            selectinload(Card.multipliers).selectinload(CardCategoryMultiplier.spend_category),
            selectinload(Card.multiplier_groups).selectinload(CardMultiplierGroup.categories).selectinload(CardCategoryMultiplier.spend_category),
            selectinload(Card.rotating_categories).selectinload(RotatingCategory.spend_category),
            selectinload(Card.network_tier).selectinload(NetworkTier.network),
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

    def _expand_portal_row(
        root_id: int,
        explicit_ids: set[int],
    ) -> list[str]:
        """Return category names covered by a portal row at root_id.

        Walks the spend-category subtree rooted at root_id, but stops descending
        into any child that has its own explicit portal row on the same card —
        that more-specific row takes precedence and will be expanded separately.
        Returns [] if root_id is unknown.
        """
        out: list[str] = []
        root = sc_by_id.get(root_id)
        if root is None:
            return out
        out.append(root.category)
        stack = [root_id]
        while stack:
            pid = stack.pop()
            for child in children_by_parent.get(pid, []):
                if child.id in explicit_ids and child.id != root_id:
                    continue  # more-specific portal row wins this subtree
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
        # Collect portal rows up front so per-sub-category rows can shadow a
        # broader parent row in the same card. Issuers like Capital One / Amex
        # / Citi advertise different portal multipliers for different travel
        # sub-categories (e.g. Hotels @ 10x, Flights @ 5x); the most specific
        # row wins for each leaf in the spend-category hierarchy.
        portal_rows: list[tuple[int, str, float, bool]] = []  # (cat_id, cat, mult, is_add)
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
                portal_rows.append((m.category_id, cat, float(m.multiplier), is_add))
                continue
            if is_add:
                additive_premiums[cat] = additive_premiums.get(cat, 0.0) + float(m.multiplier)
            else:
                # Non-additive replaces the base for this category.
                non_add_overrides[cat] = float(m.multiplier)

        # Materialize portal rows now that we know the full set of explicit
        # portal category ids on this card. Each row expands across its
        # descendant subtree, but stops at any descendant that owns its own
        # explicit portal row (handled in _expand_portal_row).
        portal_premiums_list: list[tuple[str, float, bool]] = []
        explicit_portal_ids: set[int] = {cid for cid, _c, _m, _a in portal_rows}
        for cid, cat_label, mult, is_add in portal_rows:
            names = _expand_portal_row(cid, explicit_portal_ids) or [cat_label]
            for name in names:
                portal_premiums_list.append(
                    (name.strip().lower(), mult, is_add)
                )

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
        # rotating_categories rows: p_C = (active quarters for C) / (distinct quarters in history).
        # Used by the calculator to size per-category caps on rotating groups.
        history_rows = getattr(card, "rotating_categories", []) or []
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

                # Hierarchical expansion: every ancestor of a rotating leaf
                # is *also* eligible for the bonus at the same p_C, summed
                # across siblings that share the ancestor. This makes the
                # parent category (e.g. "Online Shopping") inherit the rotating
                # bonus when its children (e.g. "Amazon", "PayPal") are in the
                # rotating universe — so a user who tracks general "Online
                # Shopping" spend rather than per-merchant spend still gets
                # credited.
                #
                # Sibling p_C values are summed because rotating quarters are
                # approximately mutually exclusive: in any given quarter at
                # most one of {Amazon, PayPal} is the active leaf, so
                # P(any active) ≈ p_C(Amazon) + p_C(PayPal). Capped at 1.0
                # for safety. Existing entries (the leaves themselves) are
                # left alone.
                ancestor_weights: dict[str, float] = {}
                for cm in getattr(grp, "categories", []):
                    if cm.category_id not in group_cat_ids:
                        continue
                    leaf_count = rotation_counts.get(cm.category_id, 0)
                    if leaf_count <= 0:
                        continue
                    leaf_weight = leaf_count / total_history_q
                    # Walk up the parent chain.
                    current = sc_by_id.get(cm.category_id)
                    visited: set[int] = set()
                    while current is not None and current.parent_id is not None:
                        parent = sc_by_id.get(current.parent_id)
                        if parent is None or parent.id in visited:
                            break
                        visited.add(parent.id)
                        # Skip "All Other" — it's the implicit base, not a
                        # bonus-eligible parent.
                        if (parent.category or "").strip().lower() == "all other":
                            current = parent
                            continue
                        ancestor_weights[parent.category] = (
                            ancestor_weights.get(parent.category, 0.0) + leaf_weight
                        )
                        current = parent

                for ancestor_name, w in ancestor_weights.items():
                    # Don't clobber a leaf entry with the same name (e.g. a
                    # rotating leaf that happens to be its own root).
                    if ancestor_name in rotation_weights:
                        continue
                    rotation_weights[ancestor_name] = min(1.0, w)
                    if ancestor_name not in cats:
                        cats.append(ancestor_name)

            multiplier_groups_list.append(
                (grp.multiplier, cats, top_n, grp.id, cap_amount, cap_months,
                 is_rotating, rotation_weights, is_additive)
            )
        # Statement credits live exclusively on wallet cards now (see
        # apply_wallet_card_overrides), so the library card has no credit_lines.
        credit_lines: list[CreditLine] = []

        # Resolve network name from the card's network tier relationship.
        _net_tier = getattr(card, "network_tier", None)
        _network = getattr(_net_tier, "network", None) if _net_tier else None
        _network_name = _network.name if _network else None

        out.append(
            CardData(
                id=card.id,
                name=card.name,
                issuer_name=card.issuer.name,
                currency=currency,
                annual_fee=card.annual_fee,
                first_year_fee=card.first_year_fee,
                sub_points=card.sub_points if card.sub_points is not None else 0,
                sub_min_spend=card.sub_min_spend,
                sub_months=card.sub_months,
                sub_spend_earn=card.sub_spend_earn if card.sub_spend_earn is not None else 0,
                sub_cash=card.sub_cash if card.sub_cash is not None else 0.0,
                sub_secondary_points=card.sub_secondary_points if card.sub_secondary_points is not None else 0,
                annual_bonus=card.annual_bonus if card.annual_bonus is not None else 0,
                annual_bonus_percent=card.annual_bonus_percent if card.annual_bonus_percent is not None else 0.0,
                annual_bonus_first_year_only=bool(card.annual_bonus_first_year_only) if card.annual_bonus_first_year_only is not None else False,
                multipliers=multipliers,
                multiplier_groups=multiplier_groups_list,
                credit_lines=credit_lines,
                portal_categories=portal_categories,
                portal_premiums=portal_premiums_list,
                transfer_enabler=bool(getattr(card, "transfer_enabler", False)),
                secondary_currency=_currency_data(card.secondary_currency_obj, cpp_overrides) if card.secondary_currency_obj else None,
                secondary_currency_rate=float(card.secondary_currency_rate) if card.secondary_currency_rate else 0.0,
                secondary_currency_cap_rate=float(card.secondary_currency_cap_rate) if card.secondary_currency_cap_rate else 0.0,
                accelerator_cost=card.accelerator_cost or 0,
                accelerator_spend_limit=float(card.accelerator_spend_limit) if card.accelerator_spend_limit else 0.0,
                accelerator_bonus_multiplier=float(card.accelerator_bonus_multiplier) if card.accelerator_bonus_multiplier else 0.0,
                accelerator_max_activations=card.accelerator_max_activations or 0,
                housing_tiered_enabled=bool(getattr(card, "housing_tiered_enabled", False)),
                has_foreign_transaction_fee=bool(getattr(card, "foreign_transaction_fee", False)),
                housing_fee_waived=bool(getattr(card, "housing_fee_waived", False)),
                network_name=_network_name,
                foreign_multiplier_bonus=multipliers.get("Foreign Transactions", 0.0),
            )
        )
    return out


async def load_housing_category_names(session: AsyncSession) -> set[str]:
    """Return the set of spend category names marked as housing (Rent, Mortgage)."""
    result = await session.execute(
        select(SpendCategory.category).where(SpendCategory.is_housing == True)  # noqa: E712
    )
    return {row[0] for row in result.all()}


async def load_foreign_eligible_category_names(session: AsyncSession) -> set[str]:
    """Return the set of spend category names that can plausibly have foreign
    spend (Travel, Dining, Gas, etc.). Used by the calculator to gate the
    wallet-level foreign-spend percentage so US-only categories like Phone,
    Internet, or Streaming are never split into a foreign bucket.
    """
    result = await session.execute(
        select(SpendCategory.category).where(SpendCategory.is_foreign_eligible == True)  # noqa: E712
    )
    return {row[0] for row in result.all()}


async def ensure_all_other_wallet_spend_item(session: AsyncSession, wallet_id: int) -> None:
    """Ensure the wallet has a WalletSpendItem for the 'All Other' SpendCategory.

    Creates one with amount=0 if missing.

    .. deprecated::
        Use WalletSpendService.ensure_all_other_item() instead.
        This function is kept for backward compatibility.
    """
    wallet_row = await session.execute(select(Wallet).where(Wallet.id == wallet_id))
    if wallet_row.scalar_one_or_none() is None:
        return
    sc_result = await session.execute(
        select(SpendCategory).where(SpendCategory.category == ALL_OTHER_CATEGORY)
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
        cat_name = item.spend_category.category if item.spend_category else ALL_OTHER_CATEGORY
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
        .options(selectinload(WalletCardCredit.library_credit))
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
    cpp_overrides: dict[int, float] | None = None,
    currency_defaults: dict[int, float] | None = None,
    currency_kinds: dict[int, str] | None = None,
) -> list[CardData]:
    """
    Return CardData copies with wallet-level overrides: SUB fields, fees, statement credits.
    Null wallet fields keep the library Card value.

    Statement credits live exclusively on wallet cards: each WalletCardCredit row
    (joined to its Credit library entry) becomes one CreditLine on the
    resulting CardData. wallet_credit_rows: dict keyed by wallet_card_id.

    For point-based credits (point_value + credit_currency_id set on the library
    credit), the dollar value is computed as ``point_value * cpp / 100`` using the
    wallet CPP override or the currency's default CPP.
    """
    wc_by_card_id: dict[int, "WalletCard"] = {wc.card_id: wc for wc in wallet_cards}
    rows_by_wc_id: dict[int, list[WalletCardCredit]] = wallet_credit_rows or {}

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

        merged_lines: list[CreditLine] = []
        _cpp = cpp_overrides or {}
        _cur_defaults = currency_defaults or {}
        _kinds = currency_kinds or {}
        for row in rows_by_wc_id.get(wc.id, []):
            lib_credit = row.library_credit
            if lib_credit is None:
                continue
            # wallet_card_credits.value is stored in the credit's native
            # currency (dollars for Cash, points for points currencies).
            # Resolve to dollars here using the wallet's CPP.
            dollar_value = row.value
            cur_id = lib_credit.credit_currency_id
            if cur_id is not None and _kinds.get(cur_id) != "cash":
                cpp = _cpp.get(cur_id) or _cur_defaults.get(cur_id, 1.0)
                dollar_value = row.value * cpp / 100.0
            merged_lines.append(
                CreditLine(
                    library_credit_id=row.library_credit_id,
                    name=lib_credit.credit_name,
                    value=dollar_value,
                    excludes_first_year=lib_credit.excludes_first_year,
                    is_one_time=lib_credit.is_one_time,
                )
            )

        out.append(
            dataclasses.replace(
                cd,
                sub_points=wc.sub_points if wc.sub_points is not None else cd.sub_points,
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
                annual_bonus_percent=(
                    wc.annual_bonus_percent if wc.annual_bonus_percent is not None else cd.annual_bonus_percent
                ),
                annual_bonus_first_year_only=(
                    wc.annual_bonus_first_year_only if wc.annual_bonus_first_year_only is not None else cd.annual_bonus_first_year_only
                ),
                annual_fee=annual_fee,
                first_year_fee=first_year_fee,
                credit_lines=merged_lines,
                secondary_currency_rate=(
                    wc.secondary_currency_rate
                    if wc.secondary_currency_rate is not None
                    else cd.secondary_currency_rate
                ),
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


async def load_wallet_card_category_priorities(
    session: AsyncSession,
    wallet_id: int,
) -> dict[int, frozenset[str]]:
    """
    Load manual spend-category priority pins for cards in a wallet.
    Returns ``{card_id: frozenset(lowercased_category_name, ...)}``.

    The lowercased/stripped form matches ``_category_priority_cards`` in
    ``app.calculator.allocation`` so category matching is case-insensitive and
    works for both the normal key and the ``__foreign__`` split variant.
    """
    from .models import WalletCard as WalletCardModel

    result = await session.execute(
        select(WalletCardCategoryPriority)
        .options(selectinload(WalletCardCategoryPriority.spend_category))
        .where(WalletCardCategoryPriority.wallet_id == wallet_id)
    )
    rows = result.scalars().all()
    if not rows:
        return {}
    wc_ids = {r.wallet_card_id for r in rows}
    wc_result = await session.execute(
        select(WalletCardModel).where(WalletCardModel.id.in_(wc_ids))
    )
    wc_map = {wc.id: wc.card_id for wc in wc_result.scalars().all()}

    per_card: dict[int, set[str]] = {}
    for r in rows:
        card_id = wc_map.get(r.wallet_card_id)
        if card_id is None:
            continue
        cat_name = r.spend_category.category if r.spend_category else ""
        key = (cat_name or "").strip().lower()
        if not key:
            continue
        per_card.setdefault(card_id, set()).add(key)
    return {cid: frozenset(keys) for cid, keys in per_card.items()}


def apply_wallet_card_category_priorities(
    card_data_list: list[CardData],
    priorities_by_card: dict[int, frozenset[str]],
) -> list[CardData]:
    """
    Return CardData copies with ``priority_categories`` populated from the
    wallet's manual pin overrides.
    """
    if not priorities_by_card:
        return card_data_list
    out: list[CardData] = []
    for cd in card_data_list:
        pins = priorities_by_card.get(cd.id)
        if not pins:
            out.append(cd)
            continue
        out.append(dataclasses.replace(cd, priority_categories=pins))
    return out


async def load_wallet_portal_shares(
    session: AsyncSession,
    wallet_id: int,
) -> dict[int, float]:
    """Load per-portal shares for one wallet. Returns {travel_portal_id: share}.
    Portals without a row default to share=0 (the calculator's behavior is to
    not credit portal multipliers in that case)."""
    result = await session.execute(
        select(WalletPortalShare).where(WalletPortalShare.wallet_id == wallet_id)
    )
    return {row.travel_portal_id: float(row.share) for row in result.scalars()}


async def load_card_ids_by_portal(
    session: AsyncSession,
) -> dict[int, set[int]]:
    """Return {travel_portal_id: {card_id, ...}} from the travel_portal_cards
    association table."""
    from .models import travel_portal_cards  # local import to avoid cycles

    result = await session.execute(
        select(
            travel_portal_cards.c.travel_portal_id,
            travel_portal_cards.c.card_id,
        )
    )
    out: dict[int, set[int]] = {}
    for portal_id, card_id in result.all():
        out.setdefault(int(portal_id), set()).add(int(card_id))
    return out


def apply_wallet_portal_shares(
    card_data_list: list[CardData],
    shares_by_portal: dict[int, float],
    card_ids_by_portal: dict[int, set[int]],
) -> list[CardData]:
    """
    Return CardData copies with `portal_share` and `portal_memberships` set
    from the wallet's per-portal shares.

    `portal_memberships` is a `{portal_id: share}` dict listing every portal
    this card belongs to (with a positive share). The LP uses this to build
    pooled portal-cap constraints so cards sharing a portal share one cap
    instead of stacking caps independently.

    `portal_share` is the maximum share across the card's portals — used by
    the legacy greedy path and as a quick "is the card portal-eligible at all"
    flag.
    """
    if not shares_by_portal or not card_data_list:
        return card_data_list
    # Invert: card_id -> {portal_id: share} for portals with a positive share.
    memberships_by_card: dict[int, dict[int, float]] = {}
    for portal_id, share in shares_by_portal.items():
        if share <= 0.0:
            continue
        for cid in card_ids_by_portal.get(portal_id, ()):
            memberships_by_card.setdefault(cid, {})[portal_id] = share
    if not memberships_by_card:
        return card_data_list
    out: list[CardData] = []
    for cd in card_data_list:
        memberships = memberships_by_card.get(cd.id)
        if not memberships:
            out.append(cd)
            continue
        out.append(
            dataclasses.replace(
                cd,
                portal_share=max(memberships.values()),
                portal_memberships=dict(memberships),
            )
        )
    return out
