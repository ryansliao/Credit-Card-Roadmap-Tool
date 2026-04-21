"""Library-level credit schemas (the global credit catalog)."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CardCreditRead(BaseModel):
    """One row in the global standardized credit library."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    credit_name: str
    value: Optional[float] = None
    excludes_first_year: bool = False
    is_one_time: bool = False
    credit_currency_id: Optional[int] = None
    card_ids: list[int] = Field(default_factory=list)
    # Per-card values: {card_id: dollar_value}. Only includes cards with a non-null value.
    card_values: dict[int, float] = Field(default_factory=dict)

    @model_validator(mode="wrap")
    @classmethod
    def populate_card_fields(cls, data: Any, handler: Any) -> Any:
        if not isinstance(data, dict) and hasattr(data, "card_links"):
            links = data.card_links or []
            return handler(
                {
                    **{k: getattr(data, k) for k in (
                        "id", "credit_name", "value", "excludes_first_year",
                        "is_one_time", "credit_currency_id",
                    )},
                    "card_ids": sorted(link.card_id for link in links),
                    "card_values": {
                        link.card_id: link.value
                        for link in links
                        if link.value is not None
                    },
                }
            )
        return handler(data)


class CreateCreditPayload(BaseModel):
    credit_name: str = Field(..., max_length=120)
    value: Optional[float] = Field(default=None, ge=0)
    excludes_first_year: bool = False
    is_one_time: bool = False
    credit_currency_id: Optional[int] = None
    card_ids: list[int] = Field(default_factory=list)
    card_values: dict[int, float] = Field(default_factory=dict)


class UpdateCreditPayload(BaseModel):
    """Update a global library credit (at least one field required)."""

    value: Optional[float] = Field(default=None, ge=0)
    credit_name: Optional[str] = Field(None, max_length=120)
    excludes_first_year: Optional[bool] = None
    is_one_time: Optional[bool] = None
    credit_currency_id: Optional[int] = None
    card_ids: Optional[list[int]] = None
    card_values: Optional[dict[int, float]] = None

    @model_validator(mode="after")
    def at_least_one_field(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be set")
        return self
