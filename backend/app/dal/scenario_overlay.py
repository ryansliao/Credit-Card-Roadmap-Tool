from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    Date,
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
    from .scenario import Scenario


class ScenarioCardOverlay(Base):
    """
    Per-scenario hypothetical override on an OWNED CardInstance. All fields
    are nullable; NULL means "inherit from the underlying CardInstance" (which
    in turn falls back to the library Card). Three-tier resolution precedence:

        overlay.<field> ?? card_instance.<field> ?? library_card.<field>

    Application rule (enforced in service layer): the referenced
    ``card_instance.scenario_id`` must be NULL. Overlays only target owned
    cards — future cards are scenario-scoped already and edits go on the
    instance directly.
    """

    __tablename__ = "scenario_card_overlays"
    __table_args__ = (UniqueConstraint("scenario_id", "card_instance_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(
        ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False
    )
    card_instance_id: Mapped[int] = mapped_column(
        # NO ACTION because scenario_id already cascades; SQL Server forbids
        # two cascade paths to the same table via CardInstance → Wallet/Scenario.
        ForeignKey("card_instances.id", ondelete="NO ACTION"), nullable=False
    )

    # Hypothetical date overrides
    closed_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    product_change_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    sub_earned_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    sub_projected_earn_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Hypothetical SUB / fee / bonus overrides
    sub_points: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sub_min_spend: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sub_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sub_spend_earn: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    annual_bonus: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    annual_bonus_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    annual_bonus_first_year_only: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    annual_fee: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    first_year_fee: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    secondary_currency_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Hypothetical enable/disable in this scenario
    is_enabled: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    scenario: Mapped["Scenario"] = relationship(back_populates="overlays")
    card_instance: Mapped["CardInstance"] = relationship(back_populates="overlays")

    def __repr__(self) -> str:
        return (
            f"<ScenarioCardOverlay scenario={self.scenario_id} "
            f"instance={self.card_instance_id}>"
        )
