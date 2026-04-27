from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .card_instance import CardInstance
    from .credit import Credit


class WalletCardCredit(Base):
    """
    Per-owned-card-instance, per-library-credit valuation override at the
    wallet level. The middle tier between library defaults and per-scenario
    overrides:

        library CardCredit  →  WalletCardCredit  →  ScenarioCardCredit

    Owned cards (``CardInstance.scenario_id IS NULL``) write here from the
    Profile/WalletTab modal. Future cards skip this tier — their credits
    live directly in ScenarioCardCredit because they're scenario-scoped.

    Absence of a row for a (card_instance, library_credit) pair means
    "inherit the library default"; presence with ``value`` means the user
    set their own valuation.
    """

    __tablename__ = "wallet_card_credits"
    __table_args__ = (
        UniqueConstraint("card_instance_id", "library_credit_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    card_instance_id: Mapped[int] = mapped_column(
        ForeignKey("card_instances.id", ondelete="CASCADE"), nullable=False
    )
    library_credit_id: Mapped[int] = mapped_column(
        ForeignKey("credits.id", ondelete="NO ACTION"), nullable=False
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    card_instance: Mapped["CardInstance"] = relationship(
        back_populates="wallet_credit_overrides"
    )
    library_credit: Mapped["Credit"] = relationship()

    def __repr__(self) -> str:
        return (
            f"<WalletCardCredit instance={self.card_instance_id} "
            f"credit={self.library_credit_id} value={self.value}>"
        )
