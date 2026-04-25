"""Scenario per-card override schemas: multiplier, credit, category
priority, and group selection. All key on (scenario_id, card_instance_id)
— duplicates of the same library card carry independent overrides."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScenarioCardMultiplierUpsert(BaseModel):
    multiplier: float = Field(..., ge=0)


class ScenarioCardMultiplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    scenario_id: int
    card_instance_id: int
    category_id: int
    category_name: str = ""
    multiplier: float

    @model_validator(mode="wrap")
    @classmethod
    def resolve_category_name(cls, data: Any, handler: Any) -> Any:
        if hasattr(data, "spend_category") and not isinstance(data, dict):
            return handler(
                {
                    "id": data.id,
                    "scenario_id": data.scenario_id,
                    "card_instance_id": data.card_instance_id,
                    "category_id": data.category_id,
                    "category_name": (
                        data.spend_category.category if data.spend_category else ""
                    ),
                    "multiplier": data.multiplier,
                }
            )
        return handler(data)


class ScenarioCardCreditUpsert(BaseModel):
    value: float = Field(..., ge=0)


class ScenarioCardCreditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    scenario_id: int
    card_instance_id: int
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
                    "scenario_id": data.scenario_id,
                    "card_instance_id": data.card_instance_id,
                    "library_credit_id": data.library_credit_id,
                    "credit_name": lc.credit_name if lc else "",
                    "value": data.value,
                }
            )
        return handler(data)


class ScenarioCardCategoryPrioritySet(BaseModel):
    """Replace the category-priority set for a card instance. Empty list
    clears all pins for the card."""

    spend_category_ids: list[int] = Field(default_factory=list)


class ScenarioCardCategoryPriorityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    scenario_id: int
    card_instance_id: int
    spend_category_id: int
    category_name: str = ""

    @model_validator(mode="wrap")
    @classmethod
    def resolve_category_name(cls, data: Any, handler: Any) -> Any:
        if hasattr(data, "spend_category") and not isinstance(data, dict):
            return handler(
                {
                    "id": data.id,
                    "scenario_id": data.scenario_id,
                    "card_instance_id": data.card_instance_id,
                    "spend_category_id": data.spend_category_id,
                    "category_name": (
                        data.spend_category.category if data.spend_category else ""
                    ),
                }
            )
        return handler(data)


class ScenarioCardGroupSelectionSet(BaseModel):
    """Set the manual category picks for a (card_instance, multiplier_group)
    pair. Empty list reverts to auto-pick by spend."""

    multiplier_group_id: int
    spend_category_ids: list[int] = Field(default_factory=list)


class ScenarioCardGroupSelectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    scenario_id: int
    card_instance_id: int
    multiplier_group_id: int
    spend_category_id: int
    category_name: str = ""

    @model_validator(mode="wrap")
    @classmethod
    def resolve_category_name(cls, data: Any, handler: Any) -> Any:
        if hasattr(data, "spend_category") and not isinstance(data, dict):
            return handler(
                {
                    "id": data.id,
                    "scenario_id": data.scenario_id,
                    "card_instance_id": data.card_instance_id,
                    "multiplier_group_id": data.multiplier_group_id,
                    "spend_category_id": data.spend_category_id,
                    "category_name": (
                        data.spend_category.category if data.spend_category else ""
                    ),
                }
            )
        return handler(data)
