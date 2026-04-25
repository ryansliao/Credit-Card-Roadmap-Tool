"""Calculation result schemas returned by /wallets/{id}/results."""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel


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
    annual_point_earn_window: float = 0.0
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
    # Dollars-per-wallet-year that SUB-related terms added to effective_annual_fee.
    # Frontend adds this to effective_annual_fee when the "Include SUBs" toggle
    # is off, making the toggle a pure display switch (no recalculation needed).
    sub_eaf_contribution: float = 0.0
    # Card-year basis variant, paired with card_effective_annual_fee.
    card_sub_eaf_contribution: float = 0.0
    avg_spend_multiplier: float = 0.0
    cents_per_point: float = 0.0
    # Effective currency name (may differ when cashback converts to points)
    effective_currency_name: str = ""
    effective_currency_id: int = 0
    effective_reward_kind: str = "points"
    effective_currency_photo_slug: Optional[str] = None
    category_earn: list[CategoryEarnItem] = []
    # Effective multiplier per spend category (top-N + manual group selections applied)
    category_multipliers: dict[str, float] = {}

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
    point_income: float
    # Sum of CardResultSchema.sub_eaf_contribution across selected cards.
    total_sub_eaf_contribution: float = 0.0
    total_cash_reward_dollars: float = 0.0
    total_reward_value_usd: float = 0.0
    # currency name -> total points over the projection window (spend + bonuses, by effective currency).
    currency_pts: dict[str, float] = {}
    currency_pts_by_id: dict[int, float] = {}
    # Wallet calc window in years.
    wallet_window_years: float = 0.0
    # Per-currency active window in years (earliest open → latest close among
    # selected cards earning the currency, clamped to the wallet window).
    currency_window_years: dict[int, float] = {}
    # secondary currency totals (e.g. Bilt Cash)
    secondary_currency_pts: dict[str, float] = {}
    secondary_currency_pts_by_id: dict[int, float] = {}
    card_results: list[CardResultSchema] = []


class WalletResultResponseSchema(BaseModel):
    """Response for GET /wallets/{id}/results and /scenarios/{id}/results.

    Under the new model, ``wallet_id`` is the wallet (one per user), and
    ``scenario_id`` / ``scenario_name`` identify the scenario whose state
    was calculated. Legacy clients that read ``wallet_name`` get the
    scenario's name (matching the entity being calculated)."""

    wallet_id: int
    wallet_name: str
    scenario_id: Optional[int] = None
    scenario_name: Optional[str] = None
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
