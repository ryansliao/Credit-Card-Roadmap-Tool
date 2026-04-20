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
