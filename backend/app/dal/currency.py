from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .card import Card


class Currency(Base):
    """
    A reward currency (e.g. Chase UR, Cash).

    cash_transfer_rate: rate when redeeming as cash/statement credit (1.0 = pure cash, 0.01 = 1¢/pt).
    partner_transfer_rate: rate for airline/hotel partner transfers; null = not transferable.
    converts_to_currency_id: upgrade pointer — when any wallet card earns the target currency
        directly, this currency automatically upgrades to it (e.g. UR Cash → UR, Citi TY Limited → Citi TY).
    """

    __tablename__ = "currencies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    photo_slug: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    # "points" (incl. miles) vs "cash" — affects display and CPP override behavior
    reward_kind: Mapped[str] = mapped_column(String(20), default="points", nullable=False)
    cents_per_point: Mapped[float] = mapped_column(Float, default=1.0)
    # Rate for partner transfers (e.g. 1.0 = 1:1, 0.7 = 1:0.7); null = not partner-transferable
    partner_transfer_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Rate for cash/statement credit redemption (e.g. 1.0 for pure cash, 0.01 for 1¢/pt); null = not set
    cash_transfer_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Optional upgrade pointer: if set, this currency converts to the target when
    # any wallet card earns the target currency directly.
    converts_to_currency_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("currencies.id", ondelete="NO ACTION"), nullable=True
    )
    # When converting to target: 1 unit of this currency = converts_at_rate units of target (e.g. 0.7 for 1:0.7)
    converts_at_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # CPP to use when no transfer enabler card is present in the wallet for this currency;
    # null = no reduction (currency is always valued at cents_per_point).
    # Used for ecosystems where transfers are completely blocked (e.g. Chase UR without Sapphire).
    no_transfer_cpp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Multiplier applied to the wallet's CPP when no transfer enabler is present;
    # null = no rate-based reduction. Used for ecosystems where transfers are available
    # but at a reduced rate (e.g. Citi TY 0.7 without Strata Premier).
    # Takes precedence over no_transfer_cpp when set.
    no_transfer_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    cards: Mapped[list["Card"]] = relationship(
        back_populates="currency_obj",
        foreign_keys="Card.currency_id",
    )
    converts_to_currency: Mapped[Optional["Currency"]] = relationship(
        "Currency",
        foreign_keys=[converts_to_currency_id],
        remote_side=[id],
    )

    def __repr__(self) -> str:
        return f"<Currency id={self.id} name={self.name!r}>"
