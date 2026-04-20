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
    from .wallet import Wallet


class WalletCurrencyCpp(Base):
    """
    Wallet-scoped cents-per-point override for a currency.
    Each wallet can independently value currencies.
    """

    __tablename__ = "wallet_currency_cpp"
    __table_args__ = (UniqueConstraint("wallet_id", "currency_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_id: Mapped[int] = mapped_column(
        ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False
    )
    currency_id: Mapped[int] = mapped_column(
        ForeignKey("currencies.id", ondelete="CASCADE"), nullable=False
    )
    cents_per_point: Mapped[float] = mapped_column(Float, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    wallet: Mapped["Wallet"] = relationship(back_populates="cpp_overrides")
    currency: Mapped["Currency"] = relationship(back_populates="wallet_cpp_overrides")

    def __repr__(self) -> str:
        return f"<WalletCurrencyCpp wallet={self.wallet_id} currency={self.currency_id} cpp={self.cents_per_point}>"
