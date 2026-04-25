from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .card import Card
    from .currency import Currency


class Credit(Base):
    """
    Standardized statement credit / perk in the global library
    (e.g. Priority Pass, Global Entry, Free Checked Bags, Uber Cash).

    `credit_value` is the default dollar valuation; users can override it on a
    per-scenario per-card-instance basis via ScenarioCardCredit. Credits are
    recurring by default.
    When `excludes_first_year` is True, the credit is not counted in the first
    year of card ownership (e.g. anniversary free night awards).
    """

    __tablename__ = "credits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    credit_name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    excludes_first_year: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_one_time: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Currency this credit is denominated in. Cash (id=1) = dollar amount used directly.
    # Points currencies = value is in points, resolved via CPP.
    credit_currency_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("currencies.id", ondelete="SET NULL"), nullable=True
    )
    credit_currency: Mapped[Optional["Currency"]] = relationship(
        foreign_keys=[credit_currency_id]
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Cards in the global library that natively offer this credit. Used by the UI to
    # auto-suggest credits when a card is added to a wallet.
    card_links: Mapped[list["CardCredit"]] = relationship(
        back_populates="credit",
        cascade="all, delete-orphan",
    )

    @property
    def card_ids(self) -> list[int]:
        return sorted(link.card_id for link in self.card_links)


class CardCredit(Base):
    """Join row linking a global library credit to a card that natively offers it.

    ``value`` is the issuer-stated dollar amount this specific card provides for
    the credit (e.g. Amex Gold Dining = $120, Marriott Brilliant Dining = $300).
    NULL means use the credit's default ``credits.value``.
    """

    __tablename__ = "card_credits"

    credit_id: Mapped[int] = mapped_column(
        ForeignKey("credits.id", ondelete="CASCADE"), primary_key=True
    )
    card_id: Mapped[int] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"), primary_key=True
    )
    value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    credit: Mapped["Credit"] = relationship(back_populates="card_links")
    card: Mapped["Card"] = relationship(back_populates="card_credit_links")
