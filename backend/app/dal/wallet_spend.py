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
    from .user_spend import UserSpendCategory
    from .wallet import Wallet


class WalletSpendItem(Base):
    """
    Per-wallet spend item: how much a user spends annually in a given
    user-facing category. The calculator expands each user category into
    granular earn categories via UserSpendCategoryMapping weights.
    """

    __tablename__ = "wallet_spend_items"
    __table_args__ = (UniqueConstraint("wallet_id", "user_spend_category_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_id: Mapped[int] = mapped_column(
        ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False
    )
    user_spend_category_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_spend_categories.id", ondelete="NO ACTION"), nullable=True
    )
    amount: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    wallet: Mapped["Wallet"] = relationship(back_populates="spend_items")
    user_spend_category: Mapped["UserSpendCategory | None"] = relationship(
        back_populates="wallet_spend_items"
    )

    def __repr__(self) -> str:
        return f"<WalletSpendItem wallet={self.wallet_id} usc={self.user_spend_category_id} amount={self.amount}>"
