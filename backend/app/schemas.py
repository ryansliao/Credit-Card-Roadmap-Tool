"""Pydantic v2 schemas for request/response validation."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# Issuer schemas
# ---------------------------------------------------------------------------


class IssuerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class CoBrandRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class NetworkTierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    network_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Currency schemas
# ---------------------------------------------------------------------------


class CurrencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    reward_kind: str = "points"
    cents_per_point: float
    partner_transfer_rate: Optional[float] = None
    cash_transfer_rate: Optional[float] = None
    converts_to_currency_id: Optional[int] = None
    converts_at_rate: Optional[float] = None
    no_transfer_cpp: Optional[float] = None
    no_transfer_rate: Optional[float] = None
    # When listing with ?user_id=, effective CPP for that user (override or base)
    user_cents_per_point: Optional[float] = None



class WalletCurrencyCppSet(BaseModel):
    """Set wallet-scoped cents-per-point override for a currency."""

    cents_per_point: float = Field(..., gt=0)


# ---------------------------------------------------------------------------
# Card schemas
# ---------------------------------------------------------------------------


class CardCreditRead(BaseModel):
    """One row in the global standardized credit library."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    credit_name: str
    value: Optional[float] = None
    excludes_first_year: bool = False
    is_one_time: bool = False
    credit_currency_id: Optional[int] = None
    card_ids: list[int] = Field(default_factory=list)
    # Per-card values: {card_id: dollar_value}. Only includes cards with a non-null value.
    card_values: dict[int, float] = Field(default_factory=dict)

    @model_validator(mode="wrap")
    @classmethod
    def populate_card_fields(cls, data: Any, handler: Any) -> Any:
        if not isinstance(data, dict) and hasattr(data, "card_links"):
            links = data.card_links or []
            return handler(
                {
                    **{k: getattr(data, k) for k in (
                        "id", "credit_name", "value", "excludes_first_year",
                        "is_one_time", "credit_currency_id",
                    )},
                    "card_ids": sorted(link.card_id for link in links),
                    "card_values": {
                        link.card_id: link.value
                        for link in links
                        if link.value is not None
                    },
                }
            )
        return handler(data)


class CreateCreditPayload(BaseModel):
    credit_name: str = Field(..., max_length=120)
    value: Optional[float] = Field(default=None, ge=0)
    excludes_first_year: bool = False
    is_one_time: bool = False
    credit_currency_id: Optional[int] = None
    card_ids: list[int] = Field(default_factory=list)
    card_values: dict[int, float] = Field(default_factory=dict)


class UpdateCreditPayload(BaseModel):
    """Update a global library credit (at least one field required)."""

    value: Optional[float] = Field(default=None, ge=0)
    credit_name: Optional[str] = Field(None, max_length=120)
    excludes_first_year: Optional[bool] = None
    is_one_time: Optional[bool] = None
    credit_currency_id: Optional[int] = None
    card_ids: Optional[list[int]] = None
    card_values: Optional[dict[int, float]] = None

    @model_validator(mode="after")
    def at_least_one_field(self):
        has_any = len(self.model_fields_set) > 0 or any(
            v is not None for v in (
                self.value, self.credit_name, self.excludes_first_year,
                self.is_one_time, self.credit_currency_id,
                self.card_ids, self.card_values,
            )
        )
        if not has_any:
            raise ValueError("At least one field must be set")
        return self


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


class RotationCategoryWeight(BaseModel):
    """Per-category activation probability inferred from rotating_categories."""

    spend_category_id: int
    name: str
    weight: float  # 0..1; fraction of historical quarters this category was active


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
            return validated.model_copy(update={"multipliers": mults})
        return handler(data)


# ---------------------------------------------------------------------------
# Spend category schemas
# ---------------------------------------------------------------------------


class SpendCategoryRead(BaseModel):
    """SpendCategory with optional children for hierarchical display."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    parent_id: Optional[int] = None
    is_system: bool = False
    is_housing: bool = False
    is_foreign_eligible: bool = False
    children: list["SpendCategoryRead"] = []

    @model_validator(mode="wrap")
    @classmethod
    def populate_children(cls, data: Any, handler: Any) -> Any:
        if not isinstance(data, dict):
            children = getattr(data, "children", []) or []
            return handler(
                {
                    "id": data.id,
                    "category": data.category,
                    "parent_id": data.parent_id,
                    "is_housing": getattr(data, "is_housing", False),
                    "is_foreign_eligible": getattr(data, "is_foreign_eligible", False),
                    "is_system": data.is_system,
                    "children": children,
                }
            )
        return handler(data)


SpendCategoryRead.model_rebuild()


class WalletSpendItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    wallet_id: int
    spend_category_id: int
    amount: float
    spend_category: SpendCategoryRead


class WalletSpendItemCreate(BaseModel):
    spend_category_id: int
    amount: float = Field(default=0.0, ge=0.0)


class WalletSpendItemUpdate(BaseModel):
    amount: float = Field(..., ge=0.0)


# ---------------------------------------------------------------------------
# Wallet card credit schemas
# ---------------------------------------------------------------------------


class WalletCardCreditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    wallet_card_id: int
    library_credit_id: int
    credit_name: str = ""
    value: float

    @model_validator(mode="wrap")
    @classmethod
    def populate_credit_name(cls, data: Any, handler: Any) -> Any:
        if not isinstance(data, dict) and "library_credit" in getattr(data, "__dict__", {}):
            lc = data.__dict__["library_credit"]
            return handler(
                {
                    "id": data.id,
                    "wallet_card_id": data.wallet_card_id,
                    "library_credit_id": data.library_credit_id,
                    "credit_name": lc.credit_name if lc else "",
                    "value": data.value,
                }
            )
        return handler(data)


class WalletCardCreditUpsert(BaseModel):
    value: float = Field(..., ge=0)


# ---------------------------------------------------------------------------
# Wallet card multiplier schemas
# ---------------------------------------------------------------------------


class WalletCardMultiplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    wallet_id: int
    card_id: int
    category_id: int
    category_name: str = ""
    multiplier: float

    @model_validator(mode="wrap")
    @classmethod
    def populate_category_name(cls, data: Any, handler: Any) -> Any:
        if not isinstance(data, dict) and "spend_category" in getattr(data, "__dict__", {}):
            sc = data.__dict__["spend_category"]
            return handler(
                {
                    "id": data.id,
                    "wallet_id": data.wallet_id,
                    "card_id": data.card_id,
                    "category_id": data.category_id,
                    "category_name": sc.category if sc else "",
                    "multiplier": data.multiplier,
                }
            )
        return handler(data)


class WalletCardMultiplierUpsert(BaseModel):
    multiplier: float = Field(..., gt=0)


# ---------------------------------------------------------------------------
# Admin reference data schemas
# ---------------------------------------------------------------------------


class AdminCreateIssuerPayload(BaseModel):
    name: str = Field(..., max_length=80)


class AdminCreateSpendCategoryPayload(BaseModel):
    category: str = Field(..., max_length=80)
    is_housing: bool = False
    is_foreign_eligible: bool = False


class AdminCreateCurrencyPayload(BaseModel):
    name: str = Field(..., max_length=80)
    reward_kind: str = Field(default="points", pattern="^(points|cash)$")
    cents_per_point: float = Field(default=1.0, gt=0)
    partner_transfer_rate: Optional[float] = Field(default=None, gt=0)
    cash_transfer_rate: Optional[float] = Field(default=None, gt=0)
    converts_to_currency_id: Optional[int] = None
    converts_at_rate: Optional[float] = Field(default=None, gt=0)
    no_transfer_cpp: Optional[float] = Field(default=None, gt=0)
    no_transfer_rate: Optional[float] = Field(default=None, gt=0, le=1)


class AdminCreateCardPayload(BaseModel):
    name: str = Field(..., max_length=120)
    issuer_id: int
    co_brand_id: Optional[int] = None
    currency_id: int
    annual_fee: float = Field(default=0.0, ge=0)
    first_year_fee: Optional[float] = Field(default=None, ge=0)
    business: bool = False
    network_tier_id: Optional[int] = None
    transfer_enabler: bool = False
    sub_points: Optional[int] = Field(default=None, ge=0)
    sub_min_spend: Optional[int] = Field(default=None, ge=0)
    sub_months: Optional[int] = Field(default=None, ge=1)
    sub_spend_earn: Optional[int] = Field(default=None, ge=0)
    sub_cash: Optional[float] = Field(default=None, ge=0)
    sub_secondary_points: Optional[int] = Field(default=None, ge=0)
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
    housing_tiered_enabled: bool = False
    foreign_transaction_fee: bool = False
    housing_fee_waived: bool = False
    sub_recurrence_months: Optional[int] = Field(default=None, ge=1)
    sub_family: Optional[str] = Field(default=None, max_length=80)


class AdminAddCardMultiplierPayload(BaseModel):
    category_id: int
    multiplier: float = Field(..., gt=0)
    is_portal: bool = False
    is_additive: bool = False
    cap_per_billing_cycle: Optional[float] = Field(default=None, gt=0)
    cap_period_months: Optional[int] = Field(default=None, ge=1)
    multiplier_group_id: Optional[int] = None


class AdminCreateCardMultiplierGroupPayload(BaseModel):
    multiplier: float = Field(..., gt=0)
    cap_per_billing_cycle: Optional[float] = Field(default=None, gt=0)
    cap_period_months: Optional[int] = Field(default=None, ge=1)
    top_n_categories: Optional[int] = Field(default=None, ge=1)
    is_rotating: bool = False
    is_additive: bool = False
    category_ids: list[int] = Field(default_factory=list)


class AdminUpdateCardMultiplierGroupPayload(BaseModel):
    multiplier: Optional[float] = Field(default=None, gt=0)
    cap_per_billing_cycle: Optional[float] = None
    cap_period_months: Optional[int] = Field(default=None, ge=1)
    top_n_categories: Optional[int] = None
    is_rotating: Optional[bool] = None
    is_additive: Optional[bool] = None
    category_ids: Optional[list[int]] = None


class AdminAddRotatingHistoryPayload(BaseModel):
    year: int = Field(..., ge=2000, le=2100)
    quarter: int = Field(..., ge=1, le=4)
    spend_category_id: int


class WalletPortalSharePayload(BaseModel):
    travel_portal_id: int
    share: float = Field(..., ge=0.0, le=1.0)


class WalletPortalShareRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    wallet_id: int
    travel_portal_id: int
    share: float
    travel_portal_name: str = ""

    @model_validator(mode="wrap")
    @classmethod
    def populate_portal_name(cls, data: Any, handler: Any) -> Any:
        if not isinstance(data, dict):
            portal = getattr(data, "travel_portal", None)
            return handler(
                {
                    "id": data.id,
                    "wallet_id": data.wallet_id,
                    "travel_portal_id": data.travel_portal_id,
                    "share": data.share,
                    "travel_portal_name": portal.name if portal is not None else "",
                }
            )
        return handler(data)


class TravelPortalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    card_ids: list[int] = []

    @model_validator(mode="wrap")
    @classmethod
    def populate_card_ids(cls, data: Any, handler: Any) -> Any:
        if not isinstance(data, dict):
            cards = getattr(data, "cards", None) or []
            return handler(
                {
                    "id": data.id,
                    "name": data.name,
                    "card_ids": [c.id for c in cards],
                }
            )
        return handler(data)


class AdminCreateTravelPortalPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    card_ids: list[int] = Field(default_factory=list)


class AdminUpdateTravelPortalPayload(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    card_ids: Optional[list[int]] = None


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


# ---------------------------------------------------------------------------
# Wallet card group selection schemas
# ---------------------------------------------------------------------------


class WalletCardGroupSelectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    wallet_card_id: int
    multiplier_group_id: int
    spend_category_id: int
    category_name: str = ""

    @model_validator(mode="wrap")
    @classmethod
    def resolve_category_name(cls, data: Any, handler: Any) -> Any:
        if hasattr(data, "spend_category") and not isinstance(data, dict):
            return handler(
                {
                    "id": data.id,
                    "wallet_card_id": data.wallet_card_id,
                    "multiplier_group_id": data.multiplier_group_id,
                    "spend_category_id": data.spend_category_id,
                    "category_name": data.spend_category.category if data.spend_category else "",
                }
            )
        return handler(data)


class WalletCardGroupSelectionSet(BaseModel):
    spend_category_ids: list[int] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Wallet card category priority schemas
# ---------------------------------------------------------------------------


class WalletCardCategoryPriorityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    wallet_id: int
    wallet_card_id: int
    spend_category_id: int
    category_name: str = ""

    @model_validator(mode="wrap")
    @classmethod
    def resolve_category_name(cls, data: Any, handler: Any) -> Any:
        if hasattr(data, "spend_category") and not isinstance(data, dict):
            return handler(
                {
                    "id": data.id,
                    "wallet_id": data.wallet_id,
                    "wallet_card_id": data.wallet_card_id,
                    "spend_category_id": data.spend_category_id,
                    "category_name": data.spend_category.category if data.spend_category else "",
                }
            )
        return handler(data)


class WalletCardCategoryPrioritySet(BaseModel):
    spend_category_ids: list[int] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Wallet schemas
# ---------------------------------------------------------------------------


class WalletCardBase(BaseModel):
    card_id: int
    added_date: date
    sub_points: Optional[int] = None
    sub_min_spend: Optional[int] = None
    sub_months: Optional[int] = None
    sub_spend_earn: Optional[int] = None
    annual_bonus: Optional[int] = Field(default=None, ge=0)
    annual_bonus_percent: Optional[float] = Field(default=None, ge=0)
    annual_bonus_first_year_only: Optional[bool] = None
    years_counted: int = Field(default=2, ge=1, le=20)
    annual_fee: Optional[float] = Field(default=None, ge=0)
    first_year_fee: Optional[float] = Field(default=None, ge=0)
    secondary_currency_rate: Optional[float] = Field(default=None, ge=0, le=1)
    sub_earned_date: Optional[date] = None
    sub_projected_earn_date: Optional[date] = None
    closed_date: Optional[date] = None
    acquisition_type: Literal["opened", "product_change"] = "opened"
    panel: Literal["in_wallet", "future_cards", "considering"] = "considering"


class InitialWalletCardCredit(BaseModel):
    library_credit_id: int
    value: float = Field(..., ge=0)


class WalletCardCreate(WalletCardBase):
    credits: list[InitialWalletCardCredit] = Field(default_factory=list)


class WalletCardUpdate(BaseModel):
    """Partial update for a wallet card. All fields optional."""
    added_date: Optional[date] = None
    sub_points: Optional[int] = None
    sub_min_spend: Optional[int] = None
    sub_months: Optional[int] = None
    sub_spend_earn: Optional[int] = None
    annual_bonus: Optional[int] = Field(default=None, ge=0)
    annual_bonus_percent: Optional[float] = Field(default=None, ge=0)
    annual_bonus_first_year_only: Optional[bool] = None
    years_counted: Optional[int] = Field(default=None, ge=1, le=20)
    annual_fee: Optional[float] = Field(default=None, ge=0)
    first_year_fee: Optional[float] = Field(default=None, ge=0)
    secondary_currency_rate: Optional[float] = Field(default=None, ge=0, le=1)
    sub_earned_date: Optional[date] = None
    closed_date: Optional[date] = None
    acquisition_type: Optional[Literal["opened", "product_change"]] = None
    panel: Optional[Literal["in_wallet", "future_cards", "considering"]] = None


class WalletCardRead(WalletCardBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    wallet_id: int
    card_name: Optional[str] = None  # populated by the API layer
    transfer_enabler: bool = False  # from library Card, populated by the API layer
    photo_slug: Optional[str] = None  # from library Card
    issuer_name: Optional[str] = None  # from library Card → Issuer
    network_tier_name: Optional[str] = None  # from library Card → NetworkTier
    credit_total: float = 0  # sum of wallet card credit override values


class WalletBase(BaseModel):
    name: str
    description: Optional[str] = None
    as_of_date: Optional[date] = None


class WalletCreate(WalletBase):
    pass


class WalletUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    as_of_date: Optional[date] = None
    foreign_spend_percent: Optional[float] = None


class WalletSettingsCurrencyIds(BaseModel):
    """Currencies relevant to wallet settings: earned by cards in the wallet or user-tracked."""

    currency_ids: list[int]


class WalletRead(WalletBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    wallet_cards: list[WalletCardRead] = []
    calc_start_date: Optional[date] = None
    calc_end_date: Optional[date] = None
    calc_duration_years: int = 2
    calc_duration_months: int = 0
    calc_window_mode: str = "duration"
    foreign_spend_percent: float = 0


class WalletResultResponseSchema(BaseModel):
    """Response for GET /wallets/{id}/results."""

    wallet_id: int
    wallet_name: str
    start_date: date
    end_date: Optional[date] = None
    duration_years: int = 0
    duration_months: int = 0
    total_months: int = 0
    as_of_date: Optional[date] = None  # same as start_date; kept for older clients
    projection_years: int
    projection_months: int
    years_counted: int  # integer years used for SUB amortization
    wallet: WalletResultSchema


# ---------------------------------------------------------------------------
# Calculation result schemas
# ---------------------------------------------------------------------------


class CategoryEarnItem(BaseModel):
    category: str
    points: float


class CardResultSchema(BaseModel):
    card_id: int
    card_name: str
    selected: bool
    effective_annual_fee: float = 0.0
    card_effective_annual_fee: float = 0.0
    card_active_years: float = 0.0
    total_points: float = 0.0
    annual_point_earn: float = 0.0
    credit_valuation: float = 0.0
    annual_fee: float = 0.0
    first_year_fee: Optional[float] = None
    sub_points: int = 0
    annual_bonus: int = 0
    annual_bonus_percent: float = 0.0
    annual_bonus_first_year_only: bool = False
    sub_extra_spend: float = 0.0
    sub_spend_earn: int = 0
    # Opportunity cost in dollars (net: gross minus value earned on target card)
    sub_opp_cost_dollars: float = 0.0
    # Gross opportunity cost in dollars (what the wallet would have earned)
    sub_opp_cost_gross_dollars: float = 0.0
    avg_spend_multiplier: float = 0.0
    cents_per_point: float = 0.0
    # Effective currency name (may differ when cashback converts to points)
    effective_currency_name: str = ""
    effective_currency_id: int = 0
    effective_reward_kind: str = "points"
    category_earn: list[CategoryEarnItem] = []

    # Secondary currency earn
    secondary_currency_earn: float = 0.0
    secondary_currency_name: str = ""
    secondary_currency_id: int = 0
    accelerator_activations: int = 0
    accelerator_bonus_points: float = 0.0
    accelerator_cost_points: float = 0.0
    secondary_currency_net_earn: float = 0.0
    secondary_currency_value_dollars: float = 0.0
    photo_slug: Optional[str] = None


class WalletResultSchema(BaseModel):
    years_counted: int
    total_effective_annual_fee: float
    total_points_earned: float
    total_annual_pts: float
    total_cash_reward_dollars: float = 0.0
    total_reward_value_usd: float = 0.0
    # currency name -> total points over the projection window (spend + bonuses, by effective currency).
    currency_pts: dict[str, float] = {}
    currency_pts_by_id: dict[int, float] = {}
    # secondary currency totals (e.g. Bilt Cash)
    secondary_currency_pts: dict[str, float] = {}
    secondary_currency_pts_by_id: dict[int, float] = {}
    card_results: list[CardResultSchema] = []



class WalletCurrencyBalanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    wallet_id: int
    currency_id: int
    currency_name: str = ""
    initial_balance: float = 0.0
    projection_earn: float = 0.0
    balance: float = 0.0
    user_tracked: bool = False
    updated_date: Optional[date] = None

    @model_validator(mode="wrap")
    @classmethod
    def populate_currency_name(cls, data: Any, handler: Any) -> Any:
        if not isinstance(data, dict) and "currency" in getattr(data, "__dict__", {}):
            c = data.__dict__["currency"]
            return handler(
                {
                    "id": data.id,
                    "wallet_id": data.wallet_id,
                    "currency_id": data.currency_id,
                    "currency_name": c.name if c else "",
                    "initial_balance": data.initial_balance,
                    "projection_earn": data.projection_earn,
                    "balance": data.balance,
                    "user_tracked": data.user_tracked,
                    "updated_date": data.updated_date,
                }
            )
        return handler(data)


class WalletCurrencyInitialSet(BaseModel):
    initial_balance: float = Field(..., ge=0)


class WalletCurrencyTrackCreate(BaseModel):
    currency_id: int
    initial_balance: float = Field(default=0.0, ge=0)


# ---------------------------------------------------------------------------
# Issuer application rule schemas
# ---------------------------------------------------------------------------


class IssuerApplicationRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issuer_id: Optional[int] = None
    issuer_name: Optional[str] = None
    rule_name: str
    description: Optional[str] = None
    max_count: int
    period_days: int
    personal_only: bool
    scope_all_issuers: bool

    @model_validator(mode="wrap")
    @classmethod
    def populate_issuer_name(cls, data: Any, handler: Any) -> Any:
        if not isinstance(data, dict) and "issuer" in getattr(data, "__dict__", {}):
            iss = data.__dict__["issuer"]
            return handler(
                {
                    "id": data.id,
                    "issuer_id": data.issuer_id,
                    "issuer_name": iss.name if iss else None,
                    "rule_name": data.rule_name,
                    "description": data.description,
                    "max_count": data.max_count,
                    "period_days": data.period_days,
                    "personal_only": data.personal_only,
                    "scope_all_issuers": data.scope_all_issuers,
                }
            )
        return handler(data)


# ---------------------------------------------------------------------------
# Roadmap schemas
# ---------------------------------------------------------------------------


class RoadmapCardStatus(BaseModel):
    wallet_card_id: int
    card_id: int
    card_name: str
    issuer_name: str
    is_business: bool
    added_date: date
    closed_date: Optional[date] = None
    is_active: bool
    sub_earned_date: Optional[date] = None
    sub_projected_earn_date: Optional[date] = None
    # "no_sub" | "pending" | "earned" | "expired"
    sub_status: str
    sub_window_end: Optional[date] = None
    next_sub_eligible_date: Optional[date] = None
    # Days remaining in SUB window (positive = still open, None = no window)
    sub_days_remaining: Optional[int] = None


class RoadmapRuleStatus(BaseModel):
    rule_id: int
    rule_name: str
    issuer_name: Optional[str]
    description: Optional[str]
    max_count: int
    period_days: int
    current_count: int
    is_violated: bool
    personal_only: bool
    scope_all_issuers: bool
    # Cards counted toward this rule (names)
    counted_cards: list[str] = []


class RoadmapResponse(BaseModel):
    wallet_id: int
    wallet_name: str
    as_of_date: date
    # 5/24 and general stats
    five_twenty_four_count: int
    five_twenty_four_eligible: bool
    personal_cards_24mo: list[str] = []
    # Per-rule violation checks
    rule_statuses: list[RoadmapRuleStatus] = []
    # Per-card status
    cards: list[RoadmapCardStatus] = []
