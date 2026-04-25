from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .card import Card
    from .scenario import Scenario
    from .scenario_overlay import ScenarioCardOverlay
    from .scenario_overrides import (
        ScenarioCardCategoryPriority,
        ScenarioCardCredit,
        ScenarioCardGroupSelection,
        ScenarioCardMultiplier,
    )
    from .wallet import Wallet


class CardInstance(Base):
    """
    A specific instance of a library Card held in a wallet. Owned cards have
    ``scenario_id IS NULL`` and represent the user's actual holdings (managed
    via Profile/WalletTab). Future cards have ``scenario_id`` set to the
    scenario where they're being modeled (managed via the Roadmap Tool).

    Duplicates of the same library card_id within the same wallet are
    permitted (some cards allow multi-application; product-change chains can
    produce them naturally) — there is intentionally NO unique constraint on
    ``(wallet_id, card_id)``.

    Acquisition is encoded by date columns rather than an enum:
    - ``opening_date`` — when this account was originally opened. Preserved
      across product changes (PC keeps the same account number, so the
      destination instance reuses the source's opening_date).
    - ``product_change_date`` — when this card became its current product via
      a PC. NULL = fresh open.
    - ``closed_date`` — when this card stopped being its current product
      (closure or PC'd-out).

    PC chains link via ``pc_from_instance_id`` (instance-to-instance) so a
    card can be PC'd into without conflicting with another instance of the
    same library card.
    """

    __tablename__ = "card_instances"
    __table_args__ = (
        Index("IX_card_instances_wallet_scenario", "wallet_id", "scenario_id"),
        Index(
            "IX_card_instances_wallet_scenario_enabled",
            "wallet_id",
            "scenario_id",
            "is_enabled",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_id: Mapped[int] = mapped_column(
        ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False
    )
    # NULL = owned card; non-NULL = future card scoped to that scenario.
    # NO ACTION because wallet_id already cascades from wallets and SQL
    # Server forbids two cascading paths to the same table.
    scenario_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("scenarios.id", ondelete="NO ACTION"), nullable=True
    )
    card_id: Mapped[int] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"), nullable=False
    )

    # Account dates (see class docstring)
    opening_date: Mapped[date] = mapped_column(Date, nullable=False)
    product_change_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    closed_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # SUB tracking
    sub_earned_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    sub_projected_earn_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # PC chain link (instance-to-instance). NO ACTION to avoid self-cycle
    # cascade and to avoid blocking deletion of the chain root.
    pc_from_instance_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("card_instances.id", ondelete="NO ACTION"), nullable=True
    )

    # Optional SUB overrides (null = use library Card's value)
    sub_points: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sub_min_spend: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sub_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sub_spend_earn: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    years_counted: Mapped[int] = mapped_column(Integer, default=2)

    # Optional annual_bonus override (null = use library Card)
    annual_bonus: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    annual_bonus_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    annual_bonus_first_year_only: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # Optional fee overrides
    annual_fee: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    first_year_fee: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Optional secondary currency rate override
    secondary_currency_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Panel placement (legacy field, retained for UI grouping):
    #   "in_wallet"    = currently held; included in calculations
    #   "future_cards" = not yet held but committed; included in calculations
    #   "considering"  = candidate, not committed; excluded from calculations
    panel: Mapped[str] = mapped_column(String(16), nullable=False, default="considering")

    # Whether this instance is included in calculations.
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    wallet: Mapped["Wallet"] = relationship(back_populates="card_instances")
    scenario: Mapped[Optional["Scenario"]] = relationship(
        back_populates="card_instances",
        primaryjoin="Scenario.id == CardInstance.scenario_id",
        foreign_keys=[scenario_id],
    )
    card: Mapped["Card"] = relationship(
        back_populates="card_instances",
        foreign_keys=[card_id],
    )
    pc_from_instance: Mapped[Optional["CardInstance"]] = relationship(
        remote_side="CardInstance.id",
        foreign_keys=[pc_from_instance_id],
    )
    overlays: Mapped[list["ScenarioCardOverlay"]] = relationship(
        back_populates="card_instance", cascade="all, delete-orphan"
    )
    credit_overrides_rows: Mapped[list["ScenarioCardCredit"]] = relationship(
        back_populates="card_instance", cascade="all, delete-orphan"
    )
    group_selections: Mapped[list["ScenarioCardGroupSelection"]] = relationship(
        back_populates="card_instance", cascade="all, delete-orphan"
    )
    category_priorities: Mapped[list["ScenarioCardCategoryPriority"]] = relationship(
        back_populates="card_instance", cascade="all, delete-orphan"
    )
    multipliers: Mapped[list["ScenarioCardMultiplier"]] = relationship(
        back_populates="card_instance", cascade="all, delete-orphan"
    )

    @property
    def is_owned(self) -> bool:
        return self.scenario_id is None

    def __repr__(self) -> str:
        scope = f"scenario={self.scenario_id}" if self.scenario_id else "owned"
        return (
            f"<CardInstance id={self.id} wallet={self.wallet_id} card={self.card_id} "
            f"{scope} opened={self.opening_date}>"
        )
