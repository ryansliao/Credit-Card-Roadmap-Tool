"""Wallet + WalletCard schemas (CRUD + read models)."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


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
    product_changed_date: Optional[date] = None
    acquisition_type: Literal["opened", "product_change"] = "opened"
    # For product_change cards: library card_id of the card changed FROM.
    pc_from_card_id: Optional[int] = None
    panel: Literal["in_wallet", "future_cards", "considering"] = "considering"
    is_enabled: bool = True


class InitialWalletCardCredit(BaseModel):
    library_credit_id: int
    value: float = Field(..., ge=0)


class WalletCardCreate(WalletCardBase):
    credits: list[InitialWalletCardCredit] = Field(default_factory=list)
    # Library card_id of the card being changed FROM (product change only).
    # When set, the matching wallet card's product_changed_date is auto-populated.
    pc_from_card_id: Optional[int] = None


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
    product_changed_date: Optional[date] = None
    acquisition_type: Optional[Literal["opened", "product_change"]] = None
    panel: Optional[Literal["in_wallet", "future_cards", "considering"]] = None
    is_enabled: Optional[bool] = None


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


class WalletUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    as_of_date: Optional[date] = None
    foreign_spend_percent: Optional[float] = None


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
