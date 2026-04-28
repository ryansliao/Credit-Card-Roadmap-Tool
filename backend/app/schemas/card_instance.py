"""CardInstance CRUD + read models.

Card instances replace WalletCard. Owned cards (scenario_id IS NULL) are
created via Profile/WalletTab with only the library card_id + opening_date
— acquisition_type is no longer part of the API. Future cards
(scenario_id set) are created via Roadmap Tool and may carry override
fields and a pc_from_instance_id link.
"""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class CardInstanceBase(BaseModel):
    """Common fields. Owned cards typically only set card_id + opening_date;
    future cards may set every field."""

    card_id: int
    opening_date: date
    product_change_date: Optional[date] = None
    closed_date: Optional[date] = None

    sub_points: Optional[int] = None
    sub_min_spend: Optional[int] = None
    sub_months: Optional[int] = None
    sub_spend_earn: Optional[int] = None
    years_counted: int = Field(default=2, ge=1, le=20)

    annual_bonus: Optional[int] = Field(default=None, ge=0)
    annual_bonus_percent: Optional[float] = Field(default=None, ge=0)
    annual_bonus_first_year_only: Optional[bool] = None

    annual_fee: Optional[float] = Field(default=None, ge=0)
    first_year_fee: Optional[float] = Field(default=None, ge=0)
    secondary_currency_rate: Optional[float] = Field(default=None, ge=0, le=1)

    pc_from_instance_id: Optional[int] = None

    panel: Literal["in_wallet", "future_cards", "considering"] = "considering"
    is_enabled: bool = True


class WalletCardCreditValue(BaseModel):
    """Per-instance per-credit valuation override at the wallet level."""

    library_credit_id: int
    value: float


class OwnedCardCreate(BaseModel):
    """Payload for adding an owned card to the user's wallet from
    Profile/WalletTab. Mirrors ``FutureCardCreate`` minus the scenario-only
    fields (``pc_from_instance_id``, ``panel``, ``is_enabled``).

    ``credit_overrides`` carries wallet-level credit valuations
    (per-card-instance) — only entries whose value differs from the library
    default need to be sent. Absence means "inherit the library default".
    """

    card_id: int
    opening_date: date
    product_change_date: Optional[date] = None
    closed_date: Optional[date] = None

    sub_points: Optional[int] = None
    sub_min_spend: Optional[int] = None
    sub_months: Optional[int] = None
    sub_spend_earn: Optional[int] = None
    years_counted: int = Field(default=2, ge=1, le=20)

    annual_bonus: Optional[int] = Field(default=None, ge=0)
    annual_bonus_percent: Optional[float] = Field(default=None, ge=0)
    annual_bonus_first_year_only: Optional[bool] = None

    annual_fee: Optional[float] = Field(default=None, ge=0)
    first_year_fee: Optional[float] = Field(default=None, ge=0)
    secondary_currency_rate: Optional[float] = Field(default=None, ge=0, le=1)

    credit_overrides: Optional[list[WalletCardCreditValue]] = None


class OwnedCardUpdate(BaseModel):
    """Partial update for an owned CardInstance from Profile/WalletTab.

    ``credit_overrides`` (when present) replaces the entire wallet credit
    override set for the instance — pass only entries whose value differs
    from the library default; missing credits revert to library defaults.
    Pass ``None`` (or omit) to leave existing wallet credit overrides
    unchanged.
    """

    opening_date: Optional[date] = None
    closed_date: Optional[date] = None
    product_change_date: Optional[date] = None

    sub_points: Optional[int] = None
    sub_min_spend: Optional[int] = None
    sub_months: Optional[int] = None
    sub_spend_earn: Optional[int] = None
    years_counted: Optional[int] = Field(default=None, ge=1, le=20)
    annual_bonus: Optional[int] = Field(default=None, ge=0)
    annual_bonus_percent: Optional[float] = Field(default=None, ge=0)
    annual_bonus_first_year_only: Optional[bool] = None
    annual_fee: Optional[float] = Field(default=None, ge=0)
    first_year_fee: Optional[float] = Field(default=None, ge=0)
    secondary_currency_rate: Optional[float] = Field(default=None, ge=0, le=1)

    credit_overrides: Optional[list[WalletCardCreditValue]] = None


class FutureCardCreate(CardInstanceBase):
    """Payload for adding a future card to a scenario from Roadmap Tool."""


class FutureCardUpdate(BaseModel):
    """Partial update for a scenario-scoped (future) CardInstance."""

    opening_date: Optional[date] = None
    product_change_date: Optional[date] = None
    closed_date: Optional[date] = None

    sub_points: Optional[int] = None
    sub_min_spend: Optional[int] = None
    sub_months: Optional[int] = None
    sub_spend_earn: Optional[int] = None
    years_counted: Optional[int] = Field(default=None, ge=1, le=20)
    annual_bonus: Optional[int] = Field(default=None, ge=0)
    annual_bonus_percent: Optional[float] = Field(default=None, ge=0)
    annual_bonus_first_year_only: Optional[bool] = None
    annual_fee: Optional[float] = Field(default=None, ge=0)
    first_year_fee: Optional[float] = Field(default=None, ge=0)
    secondary_currency_rate: Optional[float] = Field(default=None, ge=0, le=1)

    pc_from_instance_id: Optional[int] = None
    panel: Optional[Literal["in_wallet", "future_cards", "considering"]] = None
    is_enabled: Optional[bool] = None


class CreditTotalByCurrency(BaseModel):
    """Per-currency aggregate of a card-instance's scenario credit values."""

    model_config = ConfigDict(from_attributes=True)
    kind: Literal["cash", "points"]
    currency_id: Optional[int]
    currency_name: Optional[str]
    value: float


class CardInstanceRead(CardInstanceBase):
    """Read model with enriched fields from the joined library Card."""

    model_config = ConfigDict(from_attributes=True)
    id: int
    wallet_id: int
    scenario_id: Optional[int] = None
    card_name: str
    transfer_enabler: bool
    photo_slug: Optional[str]
    issuer_name: Optional[str]
    network_tier_name: Optional[str]
    credit_totals: list[CreditTotalByCurrency] = []
    # Wallet-level credit override raw rows. Only populated for owned cards
    # (scenario_id IS NULL). Empty list = inherit library defaults for all
    # of this card's library credits.
    credit_overrides: list[WalletCardCreditValue] = []
