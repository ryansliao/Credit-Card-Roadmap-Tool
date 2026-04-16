from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

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
    from .card import Card, CardMultiplierGroup
    from .credit import Credit
    from .reference import SpendCategory
    from .wallet import Wallet, WalletCard


class WalletCardCredit(Base):
    """
    A standardized credit (from the global credits library) attached to a
    specific wallet card with a user-set dollar value. The presence of this row
    means "this wallet card has this credit"; the value defaults to the library
    default but can be overridden by the user.
    """

    __tablename__ = "wallet_card_credits"
    __table_args__ = (UniqueConstraint("wallet_card_id", "library_credit_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_card_id: Mapped[int] = mapped_column(
        ForeignKey("wallet_cards.id", ondelete="CASCADE"), nullable=False
    )
    library_credit_id: Mapped[int] = mapped_column(
        ForeignKey("credits.id", ondelete="CASCADE"), nullable=False
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    wallet_card: Mapped["WalletCard"] = relationship(back_populates="credit_overrides_rows")
    library_credit: Mapped["Credit"] = relationship(back_populates="wallet_credit_overrides")

    def __repr__(self) -> str:
        return f"<WalletCardCredit wc={self.wallet_card_id} credit={self.library_credit_id} value={self.value}>"


class WalletCardGroupSelection(Base):
    """
    Per-wallet-card manual category selection for a multiplier group with top_n_categories.
    Each row pins one category as "selected" for the group's bonus rate.
    For a group with top_n_categories=N, exactly N rows should exist.
    When no rows exist for a (wallet_card_id, multiplier_group_id) pair, the calculator
    auto-picks by spend (current behavior).
    """

    __tablename__ = "wallet_card_group_selections"
    __table_args__ = (
        UniqueConstraint("wallet_card_id", "multiplier_group_id", "spend_category_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_card_id: Mapped[int] = mapped_column(
        ForeignKey("wallet_cards.id", ondelete="CASCADE"), nullable=False
    )
    multiplier_group_id: Mapped[int] = mapped_column(
        # NO ACTION: wallet_card_group_selections is cleaned up via wallet_card_id
        # CASCADE, and cards → card_multiplier_groups → here would form a second
        # cascade path from cards. NO ACTION breaks that cycle.
        ForeignKey("card_multiplier_groups.id", ondelete="NO ACTION"), nullable=False
    )
    spend_category_id: Mapped[int] = mapped_column(
        ForeignKey("spend_categories.id", ondelete="NO ACTION"), nullable=False
    )

    wallet_card: Mapped["WalletCard"] = relationship(back_populates="group_selections")
    multiplier_group: Mapped["CardMultiplierGroup"] = relationship()
    spend_category: Mapped["SpendCategory"] = relationship()

    @property
    def category_name(self) -> str:
        return self.spend_category.category if self.spend_category else ""

    def __repr__(self) -> str:
        return f"<WalletCardGroupSelection wc={self.wallet_card_id} grp={self.multiplier_group_id} cat={self.spend_category_id}>"


class WalletCardCategoryPriority(Base):
    """
    Per-wallet manual override that pins a spend category to a specific wallet
    card. When set, the calculator forces all allocation of the pinned
    ``spend_category`` to the named ``wallet_card`` regardless of the
    normal multiplier × CPP scoring. Unique per ``(wallet_id, spend_category_id)``
    so a category can be claimed by at most one card in the wallet.

    ``wallet_id`` is denormalised (mirrors ``WalletCardMultiplier``) to let the
    unique constraint span cards within the same wallet.
    """

    __tablename__ = "wallet_card_category_priorities"
    __table_args__ = (UniqueConstraint("wallet_id", "spend_category_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_id: Mapped[int] = mapped_column(
        # NO ACTION (not CASCADE) to avoid a multiple-cascade-path error in SQL
        # Server: wallet_cards already cascades from wallets, so this table is
        # cleaned up transitively via wallet_card_id when a wallet is deleted.
        ForeignKey("wallets.id", ondelete="NO ACTION"), nullable=False
    )
    wallet_card_id: Mapped[int] = mapped_column(
        ForeignKey("wallet_cards.id", ondelete="CASCADE"), nullable=False
    )
    spend_category_id: Mapped[int] = mapped_column(
        ForeignKey("spend_categories.id", ondelete="NO ACTION"), nullable=False
    )

    wallet_card: Mapped["WalletCard"] = relationship(back_populates="category_priorities")
    spend_category: Mapped["SpendCategory"] = relationship()

    @property
    def category_name(self) -> str:
        return self.spend_category.category if self.spend_category else ""

    def __repr__(self) -> str:
        return (
            f"<WalletCardCategoryPriority w={self.wallet_id} wc={self.wallet_card_id} "
            f"cat={self.spend_category_id}>"
        )


class WalletCardMultiplier(Base):
    """
    Wallet-level override of a card's category multiplier.
    Overrides the library CardCategoryMultiplier for a specific card within a specific wallet.
    """

    __tablename__ = "wallet_card_multipliers"
    __table_args__ = (UniqueConstraint("wallet_id", "card_id", "category_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_id: Mapped[int] = mapped_column(
        ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False
    )
    card_id: Mapped[int] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("spend_categories.id", ondelete="CASCADE"), nullable=False
    )
    multiplier: Mapped[float] = mapped_column(Float, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    wallet: Mapped["Wallet"] = relationship(back_populates="card_multipliers")
    card: Mapped["Card"] = relationship(back_populates="wallet_multipliers")
    spend_category: Mapped["SpendCategory"] = relationship(back_populates="wallet_card_multipliers")

    @property
    def category(self) -> str:
        return self.spend_category.category if self.spend_category else ""

    def __repr__(self) -> str:
        return f"<WalletCardMultiplier wallet={self.wallet_id} card={self.card_id} category={self.category_id} mult={self.multiplier}>"
