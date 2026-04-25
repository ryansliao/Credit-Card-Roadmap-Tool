"""Scenario CRUD + read models."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ScenarioBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = None


class ScenarioCreate(ScenarioBase):
    """Create a new scenario under the user's wallet.

    When ``copy_from_scenario_id`` is provided, the new scenario inherits
    calc config + future cards + overlays + override tables from the source.
    """

    copy_from_scenario_id: Optional[int] = None


class ScenarioUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    duration_years: Optional[int] = Field(default=None, ge=0, le=20)
    duration_months: Optional[int] = Field(default=None, ge=0, le=240)
    window_mode: Optional[str] = None
    include_subs: Optional[bool] = None


class ScenarioSummary(BaseModel):
    """Lightweight scenario record for list views and pickers."""

    model_config = ConfigDict(from_attributes=True)
    id: int
    wallet_id: int
    name: str
    description: Optional[str] = None
    is_default: bool
    updated_at: datetime


class ScenarioRead(ScenarioBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    wallet_id: int
    is_default: bool
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    duration_years: int = 2
    duration_months: int = 0
    window_mode: str = "duration"
    include_subs: bool = True
    last_calc_timestamp: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
