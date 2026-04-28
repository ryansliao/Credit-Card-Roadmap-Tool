"""Wallet schemas (singular wallet per user).

The legacy ``Wallet`` / ``WalletCard*`` schema family was removed in
Stage 5 of the scenarios refactor. The remaining types support
``GET/PATCH /wallet`` (the new canonical singular-wallet endpoints).
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .card_instance import CardInstanceRead
from .scenario import ScenarioSummary


class WalletBase(BaseModel):
    name: str
    description: Optional[str] = None


class WalletUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    foreign_spend_percent: Optional[float] = Field(default=None, ge=0, le=100)
    housing_type: Optional[Literal["rent", "mortgage"]] = None


class WalletWithScenariosRead(BaseModel):
    """The user's single wallet plus owned CardInstances and a summary of
    its scenarios. Returned by ``GET /wallet``."""

    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    name: str
    description: Optional[str] = None
    foreign_spend_percent: float = 0.0
    housing_type: Optional[Literal["rent", "mortgage"]] = None
    card_instances: list[CardInstanceRead] = []
    scenarios: list[ScenarioSummary] = []
