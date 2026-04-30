"""SpendCategory hierarchy + UserSpendCategory + WalletSpendItem schemas."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SpendCategoryFlat(BaseModel):
    """SpendCategory (earn category) without children - for use in mappings."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    parent_id: Optional[int] = None
    is_system: bool = False
    is_housing: bool = False
    is_foreign_eligible: bool = False


class SpendCategoryRead(BaseModel):
    """SpendCategory (earn category) with optional children for hierarchical display."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    parent_id: Optional[int] = None
    is_system: bool = False
    is_housing: bool = False
    is_foreign_eligible: bool = False
    children: list["SpendCategoryRead"] = []

    @model_validator(mode="wrap")
    @classmethod
    def populate_children(cls, data: Any, handler: Any) -> Any:
        if not isinstance(data, dict):
            children = getattr(data, "children", []) or []
            return handler(
                {
                    "id": data.id,
                    "category": data.category,
                    "parent_id": data.parent_id,
                    "is_housing": getattr(data, "is_housing", False),
                    "is_foreign_eligible": getattr(data, "is_foreign_eligible", False),
                    "is_system": data.is_system,
                    "children": children,
                }
            )
        return handler(data)


SpendCategoryRead.model_rebuild()


class UserSpendCategoryMappingRead(BaseModel):
    """Mapping from user category to earn category with weight."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    earn_category_id: int
    default_weight: float
    earn_category: SpendCategoryFlat


class UserSpendCategoryRead(BaseModel):
    """User-facing spend category (simplified 16 categories)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    display_order: int
    is_system: bool = False
    mappings: list[UserSpendCategoryMappingRead] = []

    @model_validator(mode="wrap")
    @classmethod
    def populate_mappings(cls, data: Any, handler: Any) -> Any:
        if not isinstance(data, dict):
            mappings = getattr(data, "mappings", []) or []
            return handler(
                {
                    "id": data.id,
                    "name": data.name,
                    "description": getattr(data, "description", None),
                    "display_order": data.display_order,
                    "is_system": getattr(data, "is_system", False),
                    "mappings": mappings,
                }
            )
        return handler(data)


class WalletSpendItemRead(BaseModel):
    """Wallet spend item response - includes user category info."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    wallet_id: int
    user_spend_category_id: Optional[int] = None
    amount: float
    user_spend_category: Optional[UserSpendCategoryRead] = None


class WalletSpendItemCreate(BaseModel):
    """Create a spend item using user category."""
    user_spend_category_id: int
    amount: float = Field(default=0.0, ge=0.0)


class WalletSpendItemUpdate(BaseModel):
    """Update spend amount."""
    amount: float = Field(..., ge=0.0)


class WalletCategoryWeightRowRead(BaseModel):
    """One row in the per-user-category weight editor response."""
    model_config = ConfigDict(from_attributes=True)

    earn_category_id: int
    earn_category_name: str
    default_weight: float
    override_weight: Optional[float] = None
    effective_weight: float


class WalletCategoryWeightsRead(BaseModel):
    """Per-user-category weight editor response."""
    user_category_id: int
    user_category_name: str
    mappings: list[WalletCategoryWeightRowRead]


class WalletCategoryWeightRowWrite(BaseModel):
    """One row in the PUT body."""
    earn_category_id: int
    weight: float = Field(..., ge=0.0)


class WalletCategoryWeightsWrite(BaseModel):
    """PUT body: a list of (earn_category_id, weight) pairs to persist.

    Server normalizes weights to sum to 1.0 before persisting. Each
    earn_category_id must be in the user category's default mapping set.
    """
    weights: list[WalletCategoryWeightRowWrite]
