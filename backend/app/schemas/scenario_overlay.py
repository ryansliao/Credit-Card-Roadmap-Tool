"""Scenario card overlay schemas — per-scenario hypothetical overrides on
owned card instances. All fields nullable; NULL means "inherit from
underlying CardInstance"."""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ScenarioCardOverlayUpsert(BaseModel):
    """Upsert payload. Any field set to a non-None value will override the
    underlying CardInstance's value in this scenario only. Set a field to
    null in the request body to clear that field's overlay (and revert to
    the underlying value).

    Note: ``closed_date`` cannot express "force open" via null alone (null
    means inherit). Use ``closed_date_clear=True`` to explicitly force the
    card active in this scenario regardless of the underlying close date.
    """

    closed_date: Optional[date] = None
    closed_date_clear: Optional[bool] = None
    product_change_date: Optional[date] = None

    sub_points: Optional[int] = None
    sub_min_spend: Optional[int] = None
    sub_months: Optional[int] = None
    sub_spend_earn: Optional[int] = None
    annual_bonus: Optional[int] = Field(default=None, ge=0)
    annual_bonus_percent: Optional[float] = Field(default=None, ge=0)
    annual_bonus_first_year_only: Optional[bool] = None
    annual_fee: Optional[float] = Field(default=None, ge=0)
    first_year_fee: Optional[float] = Field(default=None, ge=0)
    secondary_currency_rate: Optional[float] = Field(default=None, ge=0, le=1)

    is_enabled: Optional[bool] = None


class ScenarioCardOverlayRead(ScenarioCardOverlayUpsert):
    model_config = ConfigDict(from_attributes=True)
    id: int
    scenario_id: int
    card_instance_id: int
