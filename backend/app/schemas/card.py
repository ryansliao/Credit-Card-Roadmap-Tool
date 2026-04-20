"""Card library schemas: CardRead, multipliers, groups, rotating history."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .currency import CurrencyRead
from .reference import CoBrandRead, IssuerRead, NetworkTierRead


class UpdateCardLibraryPayload(BaseModel):
    """Partial update for card library fields (PATCH /cards/{id})."""

    sub_points: Optional[int] = Field(default=None, ge=0)
    sub_min_spend: Optional[int] = Field(default=None, ge=0)
    sub_months: Optional[int] = Field(default=None, ge=0)
    sub_cash: Optional[float] = Field(default=None, ge=0)
    sub_secondary_points: Optional[int] = Field(default=None, ge=0)
    annual_fee: Optional[float] = Field(default=None, ge=0)
    first_year_fee: Optional[float] = Field(default=None, ge=0)
    transfer_enabler: Optional[bool] = None
    annual_bonus: Optional[int] = Field(default=None, ge=0)
    annual_bonus_percent: Optional[float] = Field(default=None, ge=0)
    annual_bonus_first_year_only: Optional[bool] = None
    secondary_currency_id: Optional[int] = None
    secondary_currency_rate: Optional[float] = Field(default=None, ge=0, le=1)
    secondary_currency_cap_rate: Optional[float] = Field(default=None, ge=0, le=1)
    accelerator_cost: Optional[int] = Field(default=None, ge=0)
    accelerator_spend_limit: Optional[float] = Field(default=None, ge=0)
    accelerator_bonus_multiplier: Optional[float] = Field(default=None, ge=0)
    accelerator_max_activations: Optional[int] = Field(default=None, ge=0)
    housing_tiered_enabled: Optional[bool] = None
    foreign_transaction_fee: Optional[bool] = None
    housing_fee_waived: Optional[bool] = None
    photo_slug: Optional[str] = None


class CardMultiplierSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    category: str
    multiplier: float
    cap_per_billing_cycle: Optional[float] = None
    cap_period_months: Optional[int] = None  # 1=monthly, 3=quarterly, 6=semi-annual, 12=annual
    is_portal: bool = False
    is_additive: bool = False


class GroupCategoryItem(BaseModel):
    spend_category_id: int
    name: str


class CardMultiplierGroupSchema(BaseModel):
    """Group of categories sharing one multiplier, optional cap, and optional top-N behavior."""

    multiplier: float
    cap_per_billing_cycle: Optional[float] = None
    cap_period_months: Optional[int] = None  # 1=monthly, 3=quarterly, 6=semi-annual, 12=annual
    top_n_categories: Optional[int] = None  # 1=top 1, 2=top 2, etc.; None=all get the rate
    is_rotating: bool = False
    is_additive: bool = False
    categories: list[GroupCategoryItem] = []


class CardPortalPremiumRead(BaseModel):
    """Portal multiplier entry expanded through the spend-category hierarchy.

    A card with a portal row set on a parent (e.g. "Travel") produces one
    entry per descendant (Hotels, Airlines, Flights, …) plus the root row
    itself. Callers can key directly off `category` without having to walk
    the hierarchy themselves. `source_category` identifies which explicit
    portal row this entry was derived from; a child category with its own
    portal row takes precedence and halts expansion from any ancestor.
    """

    category: str
    multiplier: float
    is_additive: bool = False
    source_category: str


class RotationCategoryWeight(BaseModel):
    """Per-category activation probability inferred from rotating_categories."""

    spend_category_id: int
    name: str
    weight: float  # 0..1; fraction of historical quarters this category was active


def _build_portal_premiums(card: Any) -> list[dict[str, Any]]:
    """Expand portal multipliers through the spend-category hierarchy.

    Each explicit portal row on the card emits one entry for the row's own
    category plus one for every descendant in the spend-category tree.
    Expansion halts at a child that is itself an explicit portal row on the
    same card, so a more specific portal rate takes precedence over an
    ancestor's rate.

    The card's `multipliers[*].spend_category.children` relationship must be
    eager-loaded; unloaded children simply truncate the expansion from that
    node.
    """
    if not hasattr(card, "multipliers"):
        return []

    portal_rows: list[tuple[Any, float, bool]] = []
    for m in card.multipliers:
        if getattr(m, "multiplier_group_id", None) is not None:
            continue
        if not getattr(m, "is_portal", False):
            continue
        sc = getattr(m, "spend_category", None)
        if sc is None:
            continue
        portal_rows.append((sc, float(m.multiplier), bool(getattr(m, "is_additive", False))))

    if not portal_rows:
        return []

    explicit_ids = {sc.id for sc, _m, _a in portal_rows}

    out: list[dict[str, Any]] = []
    for root_sc, mult, is_add in portal_rows:
        root_label = root_sc.category
        stack = [root_sc]
        while stack:
            sc = stack.pop()
            out.append(
                {
                    "category": sc.category,
                    "multiplier": mult,
                    "is_additive": is_add,
                    "source_category": root_label,
                }
            )
            for child in getattr(sc, "children", None) or []:
                if child.id in explicit_ids and child.id != root_sc.id:
                    continue
                stack.append(child)
    return out


def _build_rotation_weights(group: Any) -> list[dict[str, Any]]:
    """
    Compute per-category activation probabilities for a rotating CardMultiplierGroup
    ORM object from its parent card's loaded `rotating_categories` rows.

    Returns [] when the group is not rotating or when the parent card's history
    is empty / unloaded. Categories present in the group but missing from history
    receive weight=0.
    """
    if not getattr(group, "is_rotating", False):
        return []
    card = getattr(group, "card", None)
    history = getattr(card, "rotating_categories", None) if card is not None else None
    if not history:
        # Still emit zero-weight rows so the UI can show the universe.
        return [
            {
                "spend_category_id": c.category_id,
                "name": c.category,
                "weight": 0.0,
            }
            for c in getattr(group, "categories", [])
        ]
    # Distinct (year, quarter) pairs across the entire card's history.
    quarters = {(h.year, h.quarter) for h in history}
    total_q = len(quarters) or 1
    # Per-category active quarter counts, scoped to this group's category set.
    group_cat_ids = {c.category_id for c in getattr(group, "categories", [])}
    counts: dict[int, int] = {}
    for h in history:
        if h.spend_category_id in group_cat_ids:
            counts[h.spend_category_id] = counts.get(h.spend_category_id, 0) + 1
    out: list[dict[str, Any]] = []
    for c in getattr(group, "categories", []):
        out.append(
            {
                "spend_category_id": c.category_id,
                "name": c.category,
                "weight": counts.get(c.category_id, 0) / total_q,
            }
        )
    out.sort(key=lambda r: r["weight"], reverse=True)
    return out


class CardMultiplierGroupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    multiplier: float
    cap_per_billing_cycle: Optional[float] = None
    cap_period_months: Optional[int] = None
    top_n_categories: Optional[int] = None  # 1=top 1, 2=top 2; None=all
    is_rotating: bool = False
    is_additive: bool = False
    categories: list[GroupCategoryItem] = []
    # Populated only for rotating groups; surfaces the inferred per-category
    # activation probabilities so the frontend can display them.
    rotation_weights: list[RotationCategoryWeight] = []

    @model_validator(mode="wrap")
    @classmethod
    def categories_from_orm(cls, data: Any, handler: Any) -> Any:
        if hasattr(data, "categories") and not isinstance(data, dict):
            # ORM object: categories is list of CardCategoryMultiplier
            cats = [
                {"spend_category_id": c.category_id, "name": c.category}
                for c in data.categories
            ]
            top_n = getattr(data, "top_n_categories", None)
            return handler(
                {
                    "id": data.id,
                    "multiplier": data.multiplier,
                    "cap_per_billing_cycle": getattr(
                        data, "cap_per_billing_cycle", None
                    ),
                    "cap_period_months": getattr(data, "cap_period_months", None),
                    "is_rotating": bool(getattr(data, "is_rotating", False)),
                    "is_additive": bool(getattr(data, "is_additive", False)),
                    "rotation_weights": _build_rotation_weights(data),
                    "top_n_categories": top_n,
                    "categories": cats,
                }
            )
        return handler(data)


class CardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    issuer_id: int
    co_brand_id: Optional[int] = None
    currency_id: int
    annual_fee: float
    first_year_fee: Optional[float] = None
    business: bool = False
    network_tier_id: Optional[int] = None
    sub_points: Optional[int] = None
    sub_min_spend: Optional[int] = None
    sub_months: Optional[int] = None
    sub_spend_earn: Optional[int] = None
    sub_cash: Optional[float] = None
    sub_secondary_points: Optional[int] = None
    annual_bonus: Optional[int] = None
    annual_bonus_percent: Optional[float] = None
    annual_bonus_first_year_only: Optional[bool] = None
    transfer_enabler: bool = False
    secondary_currency_id: Optional[int] = None
    secondary_currency_rate: Optional[float] = None
    secondary_currency_cap_rate: Optional[float] = None
    accelerator_cost: Optional[int] = None
    accelerator_spend_limit: Optional[float] = None
    accelerator_bonus_multiplier: Optional[float] = None
    accelerator_max_activations: Optional[int] = None
    housing_tiered_enabled: bool = False
    photo_slug: Optional[str] = None
    foreign_transaction_fee: bool = False
    housing_fee_waived: bool = False
    sub_recurrence_months: Optional[int] = None
    sub_family: Optional[str] = None

    issuer: IssuerRead
    co_brand: Optional[CoBrandRead] = None
    currency_obj: CurrencyRead
    secondary_currency_obj: Optional[CurrencyRead] = None
    network_tier: Optional[NetworkTierRead] = None

    multipliers: list[CardMultiplierSchema] = []
    multiplier_groups: list[CardMultiplierGroupRead] = []
    # Portal multipliers after hierarchy expansion. A portal row on a parent
    # category (e.g. Travel) produces one entry per descendant so consumers
    # can key by leaf-category name without walking the hierarchy.
    portal_premiums: list[CardPortalPremiumRead] = []

    @model_validator(mode="wrap")
    @classmethod
    def filter_multipliers_from_orm(cls, data: Any, handler: Any) -> Any:
        """When building from Card ORM, expose only standalone multipliers (not in a group).
        Ensure 'All Other' is always present (default 1x, uncapped) if missing.
        m.category is a property that reads m.spend_category.category via the FK relationship."""
        ALL_OTHER = "All Other"
        if hasattr(data, "multipliers") and not isinstance(data, dict):
            standalone = [
                {
                    "category": m.category,
                    "multiplier": m.multiplier,
                    "cap_per_billing_cycle": getattr(m, "cap_per_billing_cycle", None),
                    "cap_period_months": getattr(m, "cap_period_months", None),
                    "is_additive": bool(getattr(m, "is_additive", False)),
                    "is_portal": getattr(m, "is_portal", False),
                }
                for m in data.multipliers
                if getattr(m, "multiplier_group_id", None) is None
            ]
            has_all_other = any(
                (m.get("category") or "").strip().lower() == ALL_OTHER.lower()
                for m in standalone
            )
            if not has_all_other:
                standalone.insert(
                    0,
                    {
                        "category": ALL_OTHER,
                        "multiplier": 1.0,
                        "cap_per_billing_cycle": None,
                        "cap_period_months": None,
                        "is_additive": False,
                        "is_portal": False,
                    },
                )
            validated = handler(data)
            mults = [CardMultiplierSchema.model_validate(m) for m in standalone]
            portal_prems = [
                CardPortalPremiumRead.model_validate(p)
                for p in _build_portal_premiums(data)
            ]
            return validated.model_copy(
                update={"multipliers": mults, "portal_premiums": portal_prems}
            )
        return handler(data)


class RotatingCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    card_id: int
    year: int
    quarter: int
    spend_category_id: int
    category_name: str = ""

    @model_validator(mode="wrap")
    @classmethod
    def populate_category_name(cls, data: Any, handler: Any) -> Any:
        if not isinstance(data, dict):
            sc = getattr(data, "spend_category", None)
            return handler(
                {
                    "id": data.id,
                    "card_id": data.card_id,
                    "year": data.year,
                    "quarter": data.quarter,
                    "spend_category_id": data.spend_category_id,
                    "category_name": sc.category if sc is not None else "",
                }
            )
        return handler(data)
