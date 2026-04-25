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
    from .card import CardMultiplierGroup
    from .card_instance import CardInstance
    from .credit import Credit
    from .reference import SpendCategory
    from .scenario import Scenario


class ScenarioCardMultiplier(Base):
    """
    Per-scenario, per-instance override of a card's category multiplier.
    Replaces the wallet-wide WalletCardMultiplier — duplicates of the same
    library card can each carry their own multiplier override.
    """

    __tablename__ = "scenario_card_multipliers"
    __table_args__ = (
        UniqueConstraint("scenario_id", "card_instance_id", "category_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(
        ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False
    )
    card_instance_id: Mapped[int] = mapped_column(
        # NO ACTION: scenario_id already cascades, and CardInstance also
        # cascades from Wallet — avoid multi-path cascade error.
        ForeignKey("card_instances.id", ondelete="NO ACTION"), nullable=False
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("spend_categories.id", ondelete="NO ACTION"), nullable=False
    )
    multiplier: Mapped[float] = mapped_column(Float, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    scenario: Mapped["Scenario"] = relationship(back_populates="card_multipliers")
    card_instance: Mapped["CardInstance"] = relationship(back_populates="multipliers")
    spend_category: Mapped["SpendCategory"] = relationship()

    @property
    def category(self) -> str:
        return self.spend_category.category if self.spend_category else ""

    def __repr__(self) -> str:
        return (
            f"<ScenarioCardMultiplier scenario={self.scenario_id} "
            f"instance={self.card_instance_id} cat={self.category_id} "
            f"mult={self.multiplier}>"
        )


class ScenarioCardCredit(Base):
    """
    Per-scenario, per-instance attached credit with user-set value. Replaces
    WalletCardCredit. Lets two duplicates of the same library card hold
    different valuations, and lets the same instance valuate a credit
    differently per scenario.
    """

    __tablename__ = "scenario_card_credits"
    __table_args__ = (
        UniqueConstraint("scenario_id", "card_instance_id", "library_credit_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(
        ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False
    )
    card_instance_id: Mapped[int] = mapped_column(
        ForeignKey("card_instances.id", ondelete="NO ACTION"), nullable=False
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

    scenario: Mapped["Scenario"] = relationship(back_populates="card_credits")
    card_instance: Mapped["CardInstance"] = relationship(back_populates="credit_overrides_rows")
    library_credit: Mapped["Credit"] = relationship()

    def __repr__(self) -> str:
        return (
            f"<ScenarioCardCredit scenario={self.scenario_id} "
            f"instance={self.card_instance_id} credit={self.library_credit_id} "
            f"value={self.value}>"
        )


class ScenarioCardCategoryPriority(Base):
    """
    Per-scenario manual pin: forces all allocation of ``spend_category`` to
    the named ``card_instance`` regardless of the normal scoring. At most
    one card per category per scenario.
    """

    __tablename__ = "scenario_card_category_priorities"
    __table_args__ = (UniqueConstraint("scenario_id", "spend_category_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(
        ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False
    )
    card_instance_id: Mapped[int] = mapped_column(
        ForeignKey("card_instances.id", ondelete="NO ACTION"), nullable=False
    )
    spend_category_id: Mapped[int] = mapped_column(
        ForeignKey("spend_categories.id", ondelete="NO ACTION"), nullable=False
    )

    scenario: Mapped["Scenario"] = relationship(back_populates="category_priorities")
    card_instance: Mapped["CardInstance"] = relationship(back_populates="category_priorities")
    spend_category: Mapped["SpendCategory"] = relationship()

    @property
    def category_name(self) -> str:
        return self.spend_category.category if self.spend_category else ""

    def __repr__(self) -> str:
        return (
            f"<ScenarioCardCategoryPriority scenario={self.scenario_id} "
            f"instance={self.card_instance_id} cat={self.spend_category_id}>"
        )


class ScenarioCardGroupSelection(Base):
    """
    Per-scenario manual category pick for a top-N CardMultiplierGroup on a
    specific card instance. For a group with top_n_categories=N, exactly N
    rows should exist for a given (scenario, instance, group). When no rows
    exist, the calculator auto-picks by spend (current behaviour).
    """

    __tablename__ = "scenario_card_group_selections"
    __table_args__ = (
        UniqueConstraint(
            "scenario_id",
            "card_instance_id",
            "multiplier_group_id",
            "spend_category_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(
        ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False
    )
    card_instance_id: Mapped[int] = mapped_column(
        ForeignKey("card_instances.id", ondelete="NO ACTION"), nullable=False
    )
    multiplier_group_id: Mapped[int] = mapped_column(
        ForeignKey("card_multiplier_groups.id", ondelete="NO ACTION"), nullable=False
    )
    spend_category_id: Mapped[int] = mapped_column(
        ForeignKey("spend_categories.id", ondelete="NO ACTION"), nullable=False
    )

    scenario: Mapped["Scenario"] = relationship(back_populates="card_group_selections")
    card_instance: Mapped["CardInstance"] = relationship(back_populates="group_selections")
    multiplier_group: Mapped["CardMultiplierGroup"] = relationship()
    spend_category: Mapped["SpendCategory"] = relationship()

    @property
    def category_name(self) -> str:
        return self.spend_category.category if self.spend_category else ""

    def __repr__(self) -> str:
        return (
            f"<ScenarioCardGroupSelection scenario={self.scenario_id} "
            f"instance={self.card_instance_id} grp={self.multiplier_group_id} "
            f"cat={self.spend_category_id}>"
        )
