from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .card import Card, CardCategoryMultiplier
    from .user_spend import UserSpendCategoryMapping


class Issuer(Base):
    """A credit card issuer (e.g. Chase, American Express, Citi)."""

    __tablename__ = "issuers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)

    cards: Mapped[list["Card"]] = relationship(back_populates="issuer")
    application_rules: Mapped[list["IssuerApplicationRule"]] = relationship(
        back_populates="issuer", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Issuer id={self.id} name={self.name!r}>"


class CoBrand(Base):
    """A co-brand partner attached to a card (e.g. Amazon, Delta, Bilt)."""

    __tablename__ = "co_brands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)

    cards: Mapped[list["Card"]] = relationship(back_populates="co_brand")

    def __repr__(self) -> str:
        return f"<CoBrand id={self.id} name={self.name!r}>"


class Network(Base):
    """Payment network (e.g. Visa, Mastercard). Fixed reference list for card network choice."""

    __tablename__ = "networks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)

    tiers: Mapped[list["NetworkTier"]] = relationship(back_populates="network")

    def __repr__(self) -> str:
        return f"<Network id={self.id} name={self.name!r}>"


class NetworkTier(Base):
    """Card tier within a network (e.g. Visa Signature, World Elite Mastercard). Fixed reference list."""

    __tablename__ = "network_tiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    network_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("networks.id", ondelete="SET NULL"), nullable=True
    )

    network: Mapped[Optional["Network"]] = relationship(back_populates="tiers")

    def __repr__(self) -> str:
        return f"<NetworkTier id={self.id} name={self.name!r}>"


class SpendCategory(Base):
    """
    Granular earn category for card multipliers (~35 categories).

    This is the "backend" tier of the two-tier category system. Card multipliers
    reference these categories. Users enter spend via UserSpendCategory (simplified
    15 categories), which maps to these via UserSpendCategoryMapping.

    The parent_id/children hierarchy supports category grouping for rotating cards.
    is_system=True marks "All Other" and "Foreign Transactions" (cannot be deleted).
    "All Other" is pinned to ID 1, "Travel" to ID 2.
    """

    __tablename__ = "spend_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("spend_categories.id", ondelete="NO ACTION"), nullable=True
    )
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    # True for housing categories (Rent, Mortgage) — used to compute secondary
    # currency conversion caps (e.g. Bilt Cash 75% of housing rule).
    is_housing: Mapped[bool] = mapped_column(Boolean, default=False)
    # True when a category can plausibly have foreign spend (travel, dining,
    # gas abroad). False for US-only recurring spend (Phone, Internet,
    # Streaming, Amazon, etc.). Gates _split_spend_for_foreign so the
    # wallet-level foreign-spend percentage only splits eligible categories.
    is_foreign_eligible: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )

    parent: Mapped[Optional["SpendCategory"]] = relationship(
        "SpendCategory",
        back_populates="children",
        foreign_keys=[parent_id],
        remote_side="SpendCategory.id",
    )
    children: Mapped[list["SpendCategory"]] = relationship(
        "SpendCategory",
        back_populates="parent",
        foreign_keys=[parent_id],
        order_by="SpendCategory.category",
    )
    card_multipliers: Mapped[list["CardCategoryMultiplier"]] = relationship(
        back_populates="spend_category"
    )
    user_category_mappings: Mapped[list["UserSpendCategoryMapping"]] = relationship(
        back_populates="earn_category"
    )


class IssuerApplicationRule(Base):
    """
    Velocity / eligibility rule for a card issuer (e.g. Chase 5/24, Amex 1/90).
    Used by the roadmap to flag potential application denials.

    max_count: maximum new cards allowed within period_days
    period_days: look-back window in days
    personal_only: if True, only count personal (non-business) cards toward the limit
    scope_all_issuers: if True, the count spans ALL issuers (e.g. Chase 5/24 counts every issuer's cards)
    """

    __tablename__ = "issuer_application_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issuer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("issuers.id", ondelete="CASCADE"), nullable=True
    )
    rule_name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    max_count: Mapped[int] = mapped_column(Integer, nullable=False)
    period_days: Mapped[int] = mapped_column(Integer, nullable=False)
    personal_only: Mapped[bool] = mapped_column(Boolean, default=False)
    scope_all_issuers: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    issuer: Mapped[Optional["Issuer"]] = relationship(back_populates="application_rules")

    def __repr__(self) -> str:
        return f"<IssuerApplicationRule id={self.id} rule={self.rule_name!r} issuer_id={self.issuer_id}>"
