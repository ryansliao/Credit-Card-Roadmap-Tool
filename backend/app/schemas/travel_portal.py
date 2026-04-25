"""Travel portal read schema (reference data)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class TravelPortalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    card_ids: list[int] = []

    @model_validator(mode="wrap")
    @classmethod
    def populate_card_ids(cls, data: Any, handler: Any) -> Any:
        if not isinstance(data, dict):
            cards = getattr(data, "cards", None) or []
            return handler(
                {
                    "id": data.id,
                    "name": data.name,
                    "card_ids": [c.id for c in cards],
                }
            )
        return handler(data)
