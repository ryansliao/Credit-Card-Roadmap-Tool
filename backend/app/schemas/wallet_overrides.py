"""Wallet-scoped overrides: credits and category priorities."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WalletCardCreditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    wallet_card_id: int
    library_credit_id: int
    credit_name: str = ""
    value: float

    @model_validator(mode="wrap")
    @classmethod
    def populate_credit_name(cls, data: Any, handler: Any) -> Any:
        if not isinstance(data, dict) and "library_credit" in getattr(data, "__dict__", {}):
            lc = data.__dict__["library_credit"]
            return handler(
                {
                    "id": data.id,
                    "wallet_card_id": data.wallet_card_id,
                    "library_credit_id": data.library_credit_id,
                    "credit_name": lc.credit_name if lc else "",
                    "value": data.value,
                }
            )
        return handler(data)


class WalletCardCreditUpsert(BaseModel):
    value: float = Field(..., ge=0)


class WalletCardCategoryPriorityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    wallet_id: int
    wallet_card_id: int
    spend_category_id: int
    category_name: str = ""

    @model_validator(mode="wrap")
    @classmethod
    def resolve_category_name(cls, data: Any, handler: Any) -> Any:
        if hasattr(data, "spend_category") and not isinstance(data, dict):
            return handler(
                {
                    "id": data.id,
                    "wallet_id": data.wallet_id,
                    "wallet_card_id": data.wallet_card_id,
                    "spend_category_id": data.spend_category_id,
                    "category_name": data.spend_category.category if data.spend_category else "",
                }
            )
        return handler(data)


class WalletCardCategoryPrioritySet(BaseModel):
    spend_category_ids: list[int] = Field(default_factory=list)
