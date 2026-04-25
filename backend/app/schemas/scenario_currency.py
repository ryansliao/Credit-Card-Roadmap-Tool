"""Scenario currency + portal share schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ScenarioCurrencyCppSet(BaseModel):
    cents_per_point: float = Field(..., ge=0)


class ScenarioCurrencyCppRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    scenario_id: int
    currency_id: int
    cents_per_point: float


class ScenarioCurrencyBalanceSet(BaseModel):
    balance: float = Field(..., ge=0)


class ScenarioCurrencyBalanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    scenario_id: int
    currency_id: int
    balance: float


class ScenarioPortalShareSet(BaseModel):
    share: float = Field(..., ge=0, le=1)


class ScenarioPortalShareRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    scenario_id: int
    travel_portal_id: int
    share: float
