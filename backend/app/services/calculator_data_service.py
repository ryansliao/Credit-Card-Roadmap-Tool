"""Calculator data loading service.

Wraps all database loading functions needed for EV calculations.
Pure transform functions (apply_*) live in ``app.card_data_transforms``.
"""

from __future__ import annotations

from dataclasses import replace as _replace

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..calculator import CardData, CreditLine, CurrencyData
from ..constants import ALL_OTHER_CATEGORY
from ..database import get_db
from ..models import (
    Card,
    CardCategoryMultiplier,
    CardMultiplierGroup,
    Currency,
    NetworkTier,
    RotatingCategory,
    SpendCategory,
    UserSpendCategory,
    UserSpendCategoryMapping,
    WalletSpendItem,
    travel_portal_cards,
)


def _currency_data(
    orm_currency: Currency,
    cpp_overrides: dict[int, float] | None = None,
) -> CurrencyData:
    """Convert a Currency ORM object to a CurrencyData.

    Overrides apply to this row and any nested converts_to_currency.
    """
    oid = orm_currency.id
    cpp_override = cpp_overrides.get(oid) if cpp_overrides else None
    rk = getattr(orm_currency, "reward_kind", None) or "points"
    default_cpp = float(orm_currency.cents_per_point)
    if rk == "cash":
        cpp = default_cpp
    else:
        cpp = float(cpp_override) if cpp_override is not None else default_cpp

    converts_to: CurrencyData | None = None
    if orm_currency.converts_to_currency is not None:
        converts_to = _currency_data(orm_currency.converts_to_currency, cpp_overrides)

    converts_at_rate = getattr(orm_currency, "converts_at_rate", None)
    return CurrencyData(
        id=orm_currency.id,
        name=orm_currency.name,
        photo_slug=getattr(orm_currency, "photo_slug", None),
        reward_kind=rk,
        cents_per_point=cpp,
        comparison_cpp=cpp,
        cash_transfer_rate=(
            orm_currency.cash_transfer_rate
            if orm_currency.cash_transfer_rate is not None
            else 1.0
        ),
        partner_transfer_rate=orm_currency.partner_transfer_rate,
        converts_to_currency=converts_to,
        converts_at_rate=converts_at_rate if converts_at_rate is not None else 1.0,
        no_transfer_cpp=getattr(orm_currency, "no_transfer_cpp", None),
        no_transfer_rate=getattr(orm_currency, "no_transfer_rate", None),
    )


class CalculatorDataService:
    """Service for loading all data needed by the calculator.

    This service encapsulates all DB queries required for EV calculations,
    keeping wallet_results.py focused on orchestration logic.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # -------------------------------------------------------------------------
    # Card lookup
    # -------------------------------------------------------------------------

    async def load_cards_by_ids(self, card_ids: set[int]) -> dict[int, Card]:
        """Load Card objects by IDs: {card_id: Card}."""
        if not card_ids:
            return {}
        result = await self.db.execute(
            select(Card).where(Card.id.in_(card_ids))
        )
        return {c.id: c for c in result.scalars().all()}

    # -------------------------------------------------------------------------
    # Currency loading
    # -------------------------------------------------------------------------

    async def load_currency_defaults(self) -> dict[int, float]:
        """Load default CPP for all currencies: currency_id -> cents_per_point."""
        result = await self.db.execute(select(Currency))
        return {c.id: c.cents_per_point for c in result.scalars()}

    async def load_currency_kinds(self) -> dict[int, str]:
        """Load reward_kind for all currencies: currency_id -> 'cash' | 'points'."""
        result = await self.db.execute(select(Currency))
        return {c.id: c.reward_kind for c in result.scalars()}

    # -------------------------------------------------------------------------
    # Spend category loading
    # -------------------------------------------------------------------------

    async def load_housing_category_names(self) -> set[str]:
        """Return category names marked as housing (Rent, Mortgage)."""
        result = await self.db.execute(
            select(SpendCategory.category).where(
                SpendCategory.is_housing == True  # noqa: E712
            )
        )
        return {row[0] for row in result.all()}

    async def load_foreign_eligible_category_names(self) -> set[str]:
        """Return category names that can have foreign spend."""
        result = await self.db.execute(
            select(SpendCategory.category).where(
                SpendCategory.is_foreign_eligible == True  # noqa: E712
            )
        )
        return {row[0] for row in result.all()}

    # -------------------------------------------------------------------------
    # Wallet spend loading
    # -------------------------------------------------------------------------

    async def load_wallet_spend_items(self, wallet_id: int) -> dict[str, float]:
        """Load spend dict for a wallet: earn_category_name -> amount.

        User spend (stored per user_spend_category_id) is expanded to granular
        earn categories using the mapping weights. For example, if the user has
        $1000 in "Groceries" (user category) and the mappings are:
          Groceries -> Groceries (75%), Wholesale Clubs (20%), Online Groceries (5%)
        The result will be:
          {"Groceries": 750, "Wholesale Clubs": 200, "Online Groceries": 50}
        """
        # Load wallet spend items with user category
        result = await self.db.execute(
            select(WalletSpendItem)
            .options(
                selectinload(WalletSpendItem.user_spend_category),
            )
            .where(WalletSpendItem.wallet_id == wallet_id)
        )
        items = result.scalars().all()

        # Collect user category IDs that need mapping expansion
        user_cat_ids = {
            item.user_spend_category_id
            for item in items
            if item.user_spend_category_id is not None
        }

        # Load mappings for all user categories in one query
        mappings_by_user_cat: dict[int, list[tuple[str, float]]] = {}
        if user_cat_ids:
            mapping_result = await self.db.execute(
                select(UserSpendCategoryMapping)
                .options(selectinload(UserSpendCategoryMapping.earn_category))
                .where(UserSpendCategoryMapping.user_category_id.in_(user_cat_ids))
            )
            for mapping in mapping_result.scalars().all():
                earn_cat_name = mapping.earn_category.category
                mappings_by_user_cat.setdefault(mapping.user_category_id, []).append(
                    (earn_cat_name, mapping.default_weight)
                )

        spend: dict[str, float] = {}
        for item in items:
            if item.user_spend_category_id is not None:
                # New path: expand user category to earn categories via mappings
                mappings = mappings_by_user_cat.get(item.user_spend_category_id, [])
                if mappings:
                    # Normalize weights to sum to 1.0
                    total_weight = sum(w for _, w in mappings)
                    for earn_cat_name, weight in mappings:
                        normalized = weight / total_weight if total_weight > 0 else 0
                        spend[earn_cat_name] = (
                            spend.get(earn_cat_name, 0.0) + item.amount * normalized
                        )
                else:
                    # No mappings found - fall back to All Other
                    spend[ALL_OTHER_CATEGORY] = (
                        spend.get(ALL_OTHER_CATEGORY, 0.0) + item.amount
                    )
            else:
                # user_spend_category_id unset — fall back to All Other
                spend[ALL_OTHER_CATEGORY] = (
                    spend.get(ALL_OTHER_CATEGORY, 0.0) + item.amount
                )

        return spend

    # -------------------------------------------------------------------------
    # Portal loading
    # -------------------------------------------------------------------------

    async def load_card_ids_by_portal(self) -> dict[int, set[int]]:
        """Return {travel_portal_id: {card_id, ...}}."""
        result = await self.db.execute(
            select(
                travel_portal_cards.c.travel_portal_id,
                travel_portal_cards.c.card_id,
            )
        )
        out: dict[int, set[int]] = {}
        for portal_id, card_id in result.all():
            out.setdefault(int(portal_id), set()).add(int(card_id))
        return out

    # -------------------------------------------------------------------------
    # Card data loading (complex)
    # -------------------------------------------------------------------------

    async def load_card_data(
        self, cpp_overrides: dict[int, float] | None = None
    ) -> list[CardData]:
        """Load all cards with full relationship tree as CardData objects.

        This is the main entry point for calculator card data. It handles:
        - Eager loading of all card relationships
        - Multiplier aggregation (additive-aware)
        - Portal premium expansion through category hierarchy
        - Rotating category probability computation
        """
        result = await self.db.execute(
            select(Card).options(
                selectinload(Card.issuer),
                selectinload(Card.currency_obj).selectinload(
                    Currency.converts_to_currency
                ),
                selectinload(Card.secondary_currency_obj).selectinload(
                    Currency.converts_to_currency
                ),
                selectinload(Card.multipliers).selectinload(
                    CardCategoryMultiplier.spend_category
                ),
                selectinload(Card.multiplier_groups)
                .selectinload(CardMultiplierGroup.categories)
                .selectinload(CardCategoryMultiplier.spend_category),
                selectinload(Card.rotating_categories).selectinload(
                    RotatingCategory.spend_category
                ),
                selectinload(Card.network_tier).selectinload(NetworkTier.network),
            )
        )
        cards = result.scalars().all()

        # Build parent-id → descendants map for portal premium expansion
        sc_rows = await self.db.execute(select(SpendCategory))
        sc_by_id: dict[int, SpendCategory] = {
            sc.id: sc for sc in sc_rows.scalars()
        }
        children_by_parent: dict[int, list[SpendCategory]] = {}
        for sc in sc_by_id.values():
            if sc.parent_id is not None:
                children_by_parent.setdefault(sc.parent_id, []).append(sc)

        out: list[CardData] = []
        for card in cards:
            card_data = self._build_card_data(
                card, cpp_overrides, sc_by_id, children_by_parent
            )
            out.append(card_data)
        return out

    _TAKEOFF15_FACTOR = 1.0 / (1.0 - 0.15)  # ≈ 1.1765

    def _build_card_data(
        self,
        card: Card,
        cpp_overrides: dict[int, float] | None,
        sc_by_id: dict[int, SpendCategory],
        children_by_parent: dict[int, list[SpendCategory]],
    ) -> CardData:
        """Build a CardData from a Card ORM object."""
        currency = _currency_data(card.currency_obj, cpp_overrides)
        if getattr(card, "takeoff15_enabled", False):
            f = self._TAKEOFF15_FACTOR
            currency = _replace(
                currency,
                cents_per_point=currency.cents_per_point * f,
                comparison_cpp=currency.comparison_cpp * f,
            )

        # Get all-other base rate
        all_other_rate = 1.0
        for m in card.multipliers:
            if (
                (m.category or "").strip().lower() == "all other"
                and getattr(m, "multiplier_group_id", None) is None
            ):
                all_other_rate = float(m.multiplier)
                break

        # Classify standalone multipliers
        non_add_overrides: dict[str, float] = {}
        additive_premiums: dict[str, float] = {}
        portal_rows: list[tuple[int, str, float, bool]] = []

        for m in card.multipliers:
            if getattr(m, "multiplier_group_id", None) is not None:
                continue
            cat = m.category
            if not cat or (cat or "").strip().lower() == "all other":
                continue
            is_add = bool(getattr(m, "is_additive", False))
            if bool(getattr(m, "is_portal", False)):
                portal_rows.append((m.category_id, cat, float(m.multiplier), is_add))
                continue
            if is_add:
                additive_premiums[cat] = (
                    additive_premiums.get(cat, 0.0) + float(m.multiplier)
                )
            else:
                non_add_overrides[cat] = float(m.multiplier)

        # Expand portal rows through hierarchy
        portal_premiums_list = self._expand_portal_premiums(
            portal_rows, sc_by_id, children_by_parent
        )

        # Build multipliers dict
        multipliers: dict[str, float] = {"All Other": all_other_rate}
        for cat, val in non_add_overrides.items():
            multipliers[cat] = val
        for cat, premium in additive_premiums.items():
            if cat not in non_add_overrides:
                multipliers[cat] = all_other_rate + premium

        # Cascade standalone non-portal multipliers down the spend-category
        # tree. A card's rate on a parent (e.g. CSP's "Travel 2x") applies to
        # every descendant that doesn't have its own standalone non-portal
        # override, modelling issuer semantics without requiring each child
        # category to be listed redundantly in the DB. Descendants that are
        # explicit standalone non-portal overrides halt descent through that
        # subtree; group membership or portal-only entries do not.
        explicit_standalone_ids: set[int] = set()
        standalone_rate_by_id: dict[int, float] = {}
        for m in card.multipliers:
            if getattr(m, "multiplier_group_id", None) is not None:
                continue
            if getattr(m, "is_portal", False):
                continue
            if not m.category or (m.category or "").strip().lower() == "all other":
                continue
            rate = multipliers.get(m.category)
            if rate is None:
                continue
            explicit_standalone_ids.add(m.category_id)
            standalone_rate_by_id[m.category_id] = rate

        for cid, rate in standalone_rate_by_id.items():
            stack = list(children_by_parent.get(cid, []))
            while stack:
                desc = stack.pop()
                if desc.id in explicit_standalone_ids:
                    continue
                if desc.category not in multipliers:
                    multipliers[desc.category] = rate
                for child in children_by_parent.get(desc.id, []):
                    stack.append(child)

        portal_categories: set[str] = {
            m.category
            for m in card.multipliers
            if getattr(m, "is_portal", False) and m.category
        }

        # Rotation probabilities
        history_rows = getattr(card, "rotating_categories", []) or []
        rotation_quarters = {(h.year, h.quarter) for h in history_rows}
        total_history_q = len(rotation_quarters) or 1
        rotation_counts: dict[int, int] = {}
        for h in history_rows:
            rotation_counts[h.spend_category_id] = (
                rotation_counts.get(h.spend_category_id, 0) + 1
            )

        # Build multiplier groups
        multiplier_groups_list = self._build_multiplier_groups(
            card, rotation_counts, total_history_q
        )

        # Network name
        _net_tier = getattr(card, "network_tier", None)
        _network = getattr(_net_tier, "network", None) if _net_tier else None
        _network_name = _network.name if _network else None

        return CardData(
            id=card.id,
            name=card.name,
            issuer_name=card.issuer.name,
            currency=currency,
            annual_fee=card.annual_fee,
            first_year_fee=card.first_year_fee,
            sub_points=card.sub_points if card.sub_points is not None else 0,
            sub_min_spend=card.sub_min_spend,
            sub_months=card.sub_months,
            sub_spend_earn=(
                card.sub_spend_earn if card.sub_spend_earn is not None else 0
            ),
            sub_cash=card.sub_cash if card.sub_cash is not None else 0.0,
            sub_secondary_points=(
                card.sub_secondary_points
                if card.sub_secondary_points is not None
                else 0
            ),
            annual_bonus=card.annual_bonus if card.annual_bonus is not None else 0,
            annual_bonus_percent=(
                card.annual_bonus_percent
                if card.annual_bonus_percent is not None
                else 0.0
            ),
            annual_bonus_first_year_only=(
                bool(card.annual_bonus_first_year_only)
                if card.annual_bonus_first_year_only is not None
                else False
            ),
            multipliers=multipliers,
            multiplier_groups=multiplier_groups_list,
            credit_lines=[],  # Credits live on wallet cards now
            portal_categories=portal_categories,
            portal_premiums=portal_premiums_list,
            transfer_enabler=bool(getattr(card, "transfer_enabler", False)),
            secondary_currency=(
                _currency_data(card.secondary_currency_obj, cpp_overrides)
                if card.secondary_currency_obj
                else None
            ),
            secondary_currency_rate=(
                float(card.secondary_currency_rate)
                if card.secondary_currency_rate
                else 0.0
            ),
            secondary_currency_cap_rate=(
                float(card.secondary_currency_cap_rate)
                if card.secondary_currency_cap_rate
                else 0.0
            ),
            accelerator_cost=card.accelerator_cost or 0,
            accelerator_spend_limit=(
                float(card.accelerator_spend_limit)
                if card.accelerator_spend_limit
                else 0.0
            ),
            accelerator_bonus_multiplier=(
                float(card.accelerator_bonus_multiplier)
                if card.accelerator_bonus_multiplier
                else 0.0
            ),
            accelerator_max_activations=card.accelerator_max_activations or 0,
            housing_tiered_enabled=bool(
                getattr(card, "housing_tiered_enabled", False)
            ),
            has_foreign_transaction_fee=bool(
                getattr(card, "foreign_transaction_fee", False)
            ),
            housing_fee_waived=bool(getattr(card, "housing_fee_waived", False)),
            network_name=_network_name,
            foreign_multiplier_bonus=multipliers.get("Foreign Transactions", 0.0),
        )

    def _expand_portal_premiums(
        self,
        portal_rows: list[tuple[int, str, float, bool]],
        sc_by_id: dict[int, SpendCategory],
        children_by_parent: dict[int, list[SpendCategory]],
    ) -> list[tuple[str, float, bool]]:
        """Expand portal rows through the spend category hierarchy."""
        explicit_portal_ids: set[int] = {cid for cid, _c, _m, _a in portal_rows}
        portal_premiums_list: list[tuple[str, float, bool]] = []

        for cid, cat_label, mult, is_add in portal_rows:
            names = self._expand_portal_row(
                cid, explicit_portal_ids, sc_by_id, children_by_parent
            ) or [cat_label]
            for name in names:
                portal_premiums_list.append((name.strip().lower(), mult, is_add))

        return portal_premiums_list

    def _expand_portal_row(
        self,
        root_id: int,
        explicit_ids: set[int],
        sc_by_id: dict[int, SpendCategory],
        children_by_parent: dict[int, list[SpendCategory]],
    ) -> list[str]:
        """Expand a portal row through the spend category subtree."""
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
                    continue
                out.append(child.category)
                stack.append(child.id)
        return out

    def _build_multiplier_groups(
        self,
        card: Card,
        rotation_counts: dict[int, int],
        total_history_q: int,
    ) -> list[
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
    ]:
        """Build multiplier group tuples for a card."""
        multiplier_groups_list = []

        for grp in getattr(card, "multiplier_groups", []) or []:
            top_n = getattr(grp, "top_n_categories", None)
            cats = [
                c.category
                for c in getattr(grp, "categories", [])
                if getattr(c, "category", None)
            ]
            cap_amount = getattr(grp, "cap_per_billing_cycle", None)
            cap_months = getattr(grp, "cap_period_months", None)
            is_rotating = bool(getattr(grp, "is_rotating", False))
            is_additive = bool(getattr(grp, "is_additive", False))

            rotation_weights: dict[str, float] = {}
            if is_rotating and rotation_counts:
                group_cat_ids = {
                    c.category_id for c in getattr(grp, "categories", [])
                }
                for cm in getattr(grp, "categories", []):
                    cat_name = getattr(cm, "category", None)
                    if not cat_name:
                        continue
                    count = rotation_counts.get(cm.category_id, 0)
                    if cm.category_id in group_cat_ids:
                        rotation_weights[cat_name] = count / total_history_q
                # Note: rotation weights are NOT propagated up to ancestor
                # categories. The issuer pays the bonus only on the explicit
                # leaf category that's currently active (e.g. Hotels), not on
                # the parent (e.g. Travel). Propagating up would make generic
                # "Other Travel" spend earn the rotating Hotels bonus, which
                # is incorrect.

            multiplier_groups_list.append(
                (
                    grp.multiplier,
                    cats,
                    top_n,
                    grp.id,
                    cap_amount,
                    cap_months,
                    is_rotating,
                    rotation_weights,
                    is_additive,
                )
            )

        return multiplier_groups_list


def get_calculator_data_service(
    db: AsyncSession = Depends(get_db),
) -> CalculatorDataService:
    """FastAPI dependency for CalculatorDataService."""
    return CalculatorDataService(db)
