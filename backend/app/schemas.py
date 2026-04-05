"""Pydantic v2 schemas for request/response validation."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .constants import ALLOCATION_SUM_TOLERANCE


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
    # When listing with ?user_id=, effective CPP for that user (override or base)
    user_cents_per_point: Optional[float] = None



class WalletCurrencyCppSet(BaseModel):
    """Set wallet-scoped cents-per-point override for a currency."""

    cents_per_point: float = Field(..., gt=0)


# ---------------------------------------------------------------------------
# Card schemas
# ---------------------------------------------------------------------------


class CardCreditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    credit_name: str
    credit_value: float
    is_one_time: bool = False


class UpdateCardLibraryPayload(BaseModel):
    """Partial update for card library fields (PATCH /cards/{id})."""

    sub: Optional[int] = Field(default=None, ge=0)
    sub_min_spend: Optional[int] = Field(default=None, ge=0)
    sub_months: Optional[int] = Field(default=None, ge=0)
    annual_fee: Optional[float] = Field(default=None, ge=0)
    first_year_fee: Optional[float] = Field(default=None, ge=0)


class UpdateCardCreditPayload(BaseModel):
    """Update one statement credit on a card (at least one field required)."""

    credit_value: Optional[float] = Field(default=None, ge=0)
    credit_name: Optional[str] = Field(None, max_length=120)
    is_one_time: Optional[bool] = None

    @model_validator(mode="after")
    def at_least_one_field(self):
        if (
            self.credit_value is None
            and self.credit_name is None
            and self.is_one_time is None
        ):
            raise ValueError(
                "At least one of credit_value, credit_name, or is_one_time must be set"
            )
        return self


class CardMultiplierSchema(BaseModel):
    category: str
    multiplier: float
    cap_per_billing_cycle: Optional[float] = None
    cap_period: Optional[str] = None  # monthly, quarterly, annually
    is_portal: bool = False


class CardMultiplierGroupSchema(BaseModel):
    """Group of categories sharing one multiplier, optional cap, and optional top-N behavior."""

    multiplier: float
    cap_per_billing_cycle: Optional[float] = None
    cap_period: Optional[str] = None  # monthly, quarterly, annually
    top_category_only: bool = False  # legacy; use top_n_categories=1 instead
    top_n_categories: Optional[int] = None  # 1=top 1, 2=top 2, etc.; None=all get the rate
    categories: list[str] = []


class CardMultiplierGroupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    multiplier: float
    cap_per_billing_cycle: Optional[float] = None
    cap_period: Optional[str] = None
    top_category_only: bool = False  # legacy
    top_n_categories: Optional[int] = None  # 1=top 1, 2=top 2; None=all
    categories: list[str] = []

    @model_validator(mode="wrap")
    @classmethod
    def categories_from_orm(cls, data: Any, handler: Any) -> Any:
        if hasattr(data, "categories") and not isinstance(data, dict):
            # ORM object: categories is list of CardCategoryMultiplier
            # c.category is the property that reads c.spend_category.category
            cats = [c.category for c in data.categories]
            top_n = getattr(data, "top_n_categories", None)
            if top_n is None and getattr(data, "top_category_only", False):
                top_n = 1
            return handler(
                {
                    "multiplier": data.multiplier,
                    "cap_per_billing_cycle": getattr(
                        data, "cap_per_billing_cycle", None
                    ),
                    "cap_period": getattr(data, "cap_period", None),
                    "top_category_only": top_n == 1 if top_n is not None else False,
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
    sub: Optional[int] = None
    sub_min_spend: Optional[int] = None
    sub_months: Optional[int] = None
    sub_spend_earn: Optional[int] = None
    annual_bonus: Optional[int] = None
    sub_recurrence_months: Optional[int] = None
    sub_family: Optional[str] = None

    issuer: IssuerRead
    co_brand: Optional[CoBrandRead] = None
    currency_obj: CurrencyRead
    network_tier: Optional[NetworkTierRead] = None

    multipliers: list[CardMultiplierSchema] = []
    multiplier_groups: list[CardMultiplierGroupRead] = []
    credits: list[CardCreditRead] = []

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
                    "cap_period": getattr(m, "cap_period", None),
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
                        "cap_period": None,
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
# Wallet spend category schemas (wallet-scoped, replaces user-scoped)
# ---------------------------------------------------------------------------


class WalletSpendCategoryMappingCreate(BaseModel):
    spend_category_id: int
    allocation: float = Field(..., ge=0.0)


class WalletSpendCategoryMappingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    spend_category_id: int
    spend_category_name: str = ""
    allocation: float

    @model_validator(mode="wrap")
    @classmethod
    def populate_category_name(cls, data: Any, handler: Any) -> Any:
        if not isinstance(data, dict) and "spend_category" in getattr(data, "__dict__", {}):
            sc = data.__dict__["spend_category"]
            return handler(
                {
                    "id": data.id,
                    "spend_category_id": data.spend_category_id,
                    "spend_category_name": sc.category if sc else "",
                    "allocation": data.allocation,
                }
            )
        return handler(data)


class WalletSpendCategoryCreate(BaseModel):
    name: str
    amount: float = Field(default=0.0, ge=0.0)
    mappings: list[WalletSpendCategoryMappingCreate] = []

    @model_validator(mode="after")
    def validate_allocations_sum(self) -> "WalletSpendCategoryCreate":
        if self.mappings:
            total = sum(m.allocation for m in self.mappings)
            if abs(total - self.amount) > ALLOCATION_SUM_TOLERANCE:
                raise ValueError(
                    f"Mapping allocations must sum to annual amount ${self.amount:.2f} (got ${total:.2f})"
                )
        return self


class WalletSpendCategoryUpdate(BaseModel):
    name: Optional[str] = None
    amount: Optional[float] = Field(default=None, ge=0.0)
    mappings: Optional[list[WalletSpendCategoryMappingCreate]] = None


class WalletSpendCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    wallet_id: int
    name: str
    amount: float
    mappings: list[WalletSpendCategoryMappingRead] = []


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
    is_one_time: bool = False

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
                    "is_one_time": data.is_one_time,
                }
            )
        return handler(data)


class WalletCardCreditUpsert(BaseModel):
    value: float = Field(..., ge=0)
    is_one_time: Optional[bool] = None  # if None, inherit from library


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


class AdminCreateCurrencyPayload(BaseModel):
    name: str = Field(..., max_length=80)
    reward_kind: str = Field(default="points", pattern="^(points|cash)$")
    cents_per_point: float = Field(default=1.0, gt=0)
    partner_transfer_rate: Optional[float] = Field(default=None, gt=0)
    cash_transfer_rate: Optional[float] = Field(default=None, gt=0)
    converts_to_currency_id: Optional[int] = None
    converts_at_rate: Optional[float] = Field(default=None, gt=0)


class AdminCreateCardPayload(BaseModel):
    name: str = Field(..., max_length=120)
    issuer_id: int
    co_brand_id: Optional[int] = None
    currency_id: int
    annual_fee: float = Field(default=0.0, ge=0)
    first_year_fee: Optional[float] = Field(default=None, ge=0)
    business: bool = False
    network_tier_id: Optional[int] = None
    sub: Optional[int] = Field(default=None, ge=0)
    sub_min_spend: Optional[int] = Field(default=None, ge=0)
    sub_months: Optional[int] = Field(default=None, ge=1)
    sub_spend_earn: Optional[int] = Field(default=None, ge=0)
    annual_bonus: Optional[int] = Field(default=None, ge=0)
    sub_recurrence_months: Optional[int] = Field(default=None, ge=1)
    sub_family: Optional[str] = Field(default=None, max_length=80)


class AdminAddCardMultiplierPayload(BaseModel):
    category_id: int
    multiplier: float = Field(..., gt=0)
    is_portal: bool = False
    cap_per_billing_cycle: Optional[float] = Field(default=None, gt=0)
    cap_period: Optional[str] = Field(default=None, pattern="^(monthly|quarterly|annually)$")
    multiplier_group_id: Optional[int] = None


class AdminAddCardCreditPayload(BaseModel):
    credit_name: str = Field(..., max_length=120)
    credit_value: float = Field(default=0.0, ge=0)
    is_one_time: bool = False


# ---------------------------------------------------------------------------
# Wallet schemas
# ---------------------------------------------------------------------------


class WalletCardBase(BaseModel):
    card_id: int
    added_date: date
    sub: Optional[int] = None
    sub_min_spend: Optional[int] = None
    sub_months: Optional[int] = None
    sub_spend_earn: Optional[int] = None
    annual_bonus: Optional[int] = Field(default=None, ge=0)
    years_counted: int = Field(default=2, ge=1, le=20)
    annual_fee: Optional[float] = Field(default=None, ge=0)
    first_year_fee: Optional[float] = Field(default=None, ge=0)
    sub_earned_date: Optional[date] = None
    sub_projected_earn_date: Optional[date] = None
    closed_date: Optional[date] = None
    acquisition_type: Literal["opened", "product_change"] = "opened"
    panel: Literal["on_deck", "in_wallet"] = "on_deck"


class WalletCardCreate(WalletCardBase):
    pass


class WalletCardUpdate(BaseModel):
    """Partial update for a wallet card. All fields optional."""
    added_date: Optional[date] = None
    sub: Optional[int] = None
    sub_min_spend: Optional[int] = None
    sub_months: Optional[int] = None
    sub_spend_earn: Optional[int] = None
    annual_bonus: Optional[int] = Field(default=None, ge=0)
    years_counted: Optional[int] = Field(default=None, ge=1, le=20)
    annual_fee: Optional[float] = Field(default=None, ge=0)
    first_year_fee: Optional[float] = Field(default=None, ge=0)
    sub_earned_date: Optional[date] = None
    closed_date: Optional[date] = None
    acquisition_type: Optional[Literal["opened", "product_change"]] = None
    panel: Optional[Literal["on_deck", "in_wallet"]] = None


class WalletCardRead(WalletCardBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    wallet_id: int
    card_name: Optional[str] = None  # populated by the API layer


class WalletBase(BaseModel):
    name: str
    description: Optional[str] = None
    as_of_date: Optional[date] = None


class WalletCreate(WalletBase):
    user_id: int


class WalletUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    as_of_date: Optional[date] = None


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
    total_points: float = 0.0
    annual_point_earn: float = 0.0
    credit_valuation: float = 0.0
    annual_fee: float = 0.0
    first_year_fee: Optional[float] = None
    sub: int = 0
    annual_bonus: int = 0
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
