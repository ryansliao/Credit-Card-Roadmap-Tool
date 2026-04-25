"""Currency read schema."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class CurrencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    photo_slug: Optional[str] = None
    reward_kind: str = "points"
    cents_per_point: float
    partner_transfer_rate: Optional[float] = None
    cash_transfer_rate: Optional[float] = None
    converts_to_currency_id: Optional[int] = None
    converts_at_rate: Optional[float] = None
    no_transfer_cpp: Optional[float] = None
    no_transfer_rate: Optional[float] = None
    # Effective CPP for the active scenario (override or base) when surfaced
    # via /scenarios/{id}/currencies. Equal to ``cents_per_point`` otherwise.
    user_cents_per_point: Optional[float] = None
