"""Wallet currency balance / track schemas."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, model_validator


class WalletCurrencyBalanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    wallet_id: int
    currency_id: int
    currency_name: str = ""
    balance: float = 0.0
    user_tracked: bool = False
    updated_date: Optional[date] = None

    @model_validator(mode="wrap")
    @classmethod
    def populate_currency_name(cls, data: Any, handler: Any) -> Any:
        if not isinstance(data, dict) and "currency" in getattr(data, "__dict__", {}):
            c = data.__dict__["currency"]
            return handler(
                {
                    "id": data.id,
                    "wallet_id": data.wallet_id,
                    "currency_id": data.currency_id,
                    "currency_name": c.name if c else "",
                    "balance": data.balance,
                    "user_tracked": data.user_tracked,
                    "updated_date": data.updated_date,
                }
            )
        return handler(data)


class WalletCurrencyTrackCreate(BaseModel):
    currency_id: int
