"""Currency read + wallet-scoped CPP override schemas."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


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
    # When listing with ?user_id=, effective CPP for that user (override or base)
    user_cents_per_point: Optional[float] = None


class WalletCurrencyCppSet(BaseModel):
    """Set wallet-scoped cents-per-point override for a currency."""

    cents_per_point: float = Field(..., gt=0)
