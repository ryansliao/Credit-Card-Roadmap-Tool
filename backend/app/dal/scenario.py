from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    Date,
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
    from .card_instance import CardInstance
    from .scenario_currency import (
        ScenarioCurrencyBalance,
        ScenarioCurrencyCpp,
        ScenarioPortalShare,
    )
    from .scenario_overlay import ScenarioCardOverlay
    from .scenario_overrides import (
        ScenarioCardCategoryPriority,
        ScenarioCardCredit,
        ScenarioCardGroupSelection,
        ScenarioCardMultiplier,
    )
    from .wallet import Wallet


class Scenario(Base):
    """
    A what-if iteration of a user's wallet. Each scenario carries its own
    calc window, future-card additions, per-card overlays, and override
    tables. Owned cards live on Wallet (CardInstance with scenario_id IS
    NULL); future cards live here (CardInstance with scenario_id = this.id).
    """

    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_id: Mapped[int] = mapped_column(
        ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )

    # Calc window (moved from Wallet)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    duration_years: Mapped[int] = mapped_column(Integer, default=2, server_default="2")
    duration_months: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    window_mode: Mapped[str] = mapped_column(
        String(20), default="duration", server_default="duration"
    )
    include_subs: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )

    # Cached last results payload (JSON-serialised WalletResultResponseSchema)
    last_calc_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_calc_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    wallet: Mapped["Wallet"] = relationship(back_populates="scenarios")
    card_instances: Mapped[list["CardInstance"]] = relationship(
        back_populates="scenario",
        primaryjoin="Scenario.id == CardInstance.scenario_id",
        cascade="all, delete-orphan",
    )
    overlays: Mapped[list["ScenarioCardOverlay"]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan"
    )
    cpp_overrides: Mapped[list["ScenarioCurrencyCpp"]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan"
    )
    currency_balances: Mapped[list["ScenarioCurrencyBalance"]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan"
    )
    portal_shares: Mapped[list["ScenarioPortalShare"]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan"
    )
    card_multipliers: Mapped[list["ScenarioCardMultiplier"]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan"
    )
    card_credits: Mapped[list["ScenarioCardCredit"]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan"
    )
    category_priorities: Mapped[list["ScenarioCardCategoryPriority"]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan"
    )
    card_group_selections: Mapped[list["ScenarioCardGroupSelection"]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Scenario id={self.id} wallet={self.wallet_id} name={self.name!r}>"
