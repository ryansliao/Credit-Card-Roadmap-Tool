from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    DateTime,
    Float,
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
    from .scenario import Scenario
    from .user import User
    from .wallet_spend import WalletSpendItem


class Wallet(Base):
    """The user's single wallet.

    Owns the user's actual portfolio: card_instances (with scenario_id IS
    NULL) and spend_items. Calc-config + per-scenario overrides live on
    Scenario; future cards live as scenario-scoped CardInstance rows.
    """

    __tablename__ = "wallets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Percentage of total spend that occurs as foreign transactions (0–100).
    foreign_spend_percent: Mapped[float] = mapped_column(
        Float, default=0, server_default="0"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="wallets")
    spend_items: Mapped[list["WalletSpendItem"]] = relationship(
        back_populates="wallet", cascade="all, delete-orphan"
    )
    scenarios: Mapped[list["Scenario"]] = relationship(
        back_populates="wallet", cascade="all, delete-orphan"
    )
    card_instances: Mapped[list["CardInstance"]] = relationship(
        back_populates="wallet", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Wallet id={self.id} name={self.name!r}>"
