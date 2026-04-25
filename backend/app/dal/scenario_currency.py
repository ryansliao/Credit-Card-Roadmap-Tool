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
    from .currency import Currency
    from .scenario import Scenario
    from .travel_portal import TravelPortal


class ScenarioCurrencyCpp(Base):
    """
    Per-scenario cents-per-point override for a currency. Replaces
    WalletCurrencyCpp.
    """

    __tablename__ = "scenario_currency_cpp"
    __table_args__ = (UniqueConstraint("scenario_id", "currency_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(
        ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False
    )
    currency_id: Mapped[int] = mapped_column(
        ForeignKey("currencies.id", ondelete="CASCADE"), nullable=False
    )
    cents_per_point: Mapped[float] = mapped_column(Float, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    scenario: Mapped["Scenario"] = relationship(back_populates="cpp_overrides")
    currency: Mapped["Currency"] = relationship()

    def __repr__(self) -> str:
        return (
            f"<ScenarioCurrencyCpp scenario={self.scenario_id} "
            f"currency={self.currency_id} cpp={self.cents_per_point}>"
        )


class ScenarioCurrencyBalance(Base):
    """
    Per-scenario tracked point balance for a currency. New table — no legacy
    data to migrate (the prior wallet-level balance table was dropped in
    migration 003).
    """

    __tablename__ = "scenario_currency_balances"
    __table_args__ = (UniqueConstraint("scenario_id", "currency_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(
        ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False
    )
    currency_id: Mapped[int] = mapped_column(
        ForeignKey("currencies.id", ondelete="CASCADE"), nullable=False
    )
    balance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    scenario: Mapped["Scenario"] = relationship(back_populates="currency_balances")
    currency: Mapped["Currency"] = relationship()

    def __repr__(self) -> str:
        return (
            f"<ScenarioCurrencyBalance scenario={self.scenario_id} "
            f"currency={self.currency_id} balance={self.balance}>"
        )


class ScenarioPortalShare(Base):
    """
    Per-scenario per-travel-portal share. Replaces WalletPortalShare.
    """

    __tablename__ = "scenario_portal_shares"
    __table_args__ = (UniqueConstraint("scenario_id", "travel_portal_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(
        ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False
    )
    travel_portal_id: Mapped[int] = mapped_column(
        ForeignKey("travel_portals.id", ondelete="CASCADE"), nullable=False
    )
    share: Mapped[float] = mapped_column(Float, nullable=False)

    scenario: Mapped["Scenario"] = relationship(back_populates="portal_shares")
    travel_portal: Mapped["TravelPortal"] = relationship()

    def __repr__(self) -> str:
        return (
            f"<ScenarioPortalShare scenario={self.scenario_id} "
            f"portal={self.travel_portal_id} share={self.share}>"
        )
