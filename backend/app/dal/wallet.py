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
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .card import Card
    from .user import User
    from .wallet_card_override import (
        WalletCardCredit,
        WalletCardGroupSelection,
        WalletCardCategoryPriority,
        WalletCardMultiplier,
    )
    from .wallet_currency import WalletCurrencyBalance, WalletCurrencyCpp
    from .wallet_spend import WalletSpendItem


class Wallet(Base):
    """
    A user's wallet: a named set of cards with added dates and optional SUB overrides.
    Replaces Scenario as the primary wallet entity for the Wallet Tool.
    """

    __tablename__ = "wallets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    as_of_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Persisted calculation configuration (saved on each successful calculate)
    calc_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    calc_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    calc_duration_years: Mapped[int] = mapped_column(Integer, default=2, server_default="2")
    calc_duration_months: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    calc_window_mode: Mapped[str] = mapped_column(String(20), default="duration", server_default="duration")

    # Percentage of total spend that occurs as foreign transactions (0–100).
    foreign_spend_percent: Mapped[float] = mapped_column(Float, default=0, server_default="0")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user: Mapped["User"] = relationship(back_populates="wallets")
    wallet_cards: Mapped[list["WalletCard"]] = relationship(
        back_populates="wallet", cascade="all, delete-orphan"
    )
    currency_balances: Mapped[list["WalletCurrencyBalance"]] = relationship(
        "WalletCurrencyBalance", back_populates="wallet", cascade="all, delete-orphan"
    )
    spend_items: Mapped[list["WalletSpendItem"]] = relationship(
        back_populates="wallet", cascade="all, delete-orphan"
    )
    cpp_overrides: Mapped[list["WalletCurrencyCpp"]] = relationship(
        back_populates="wallet", cascade="all, delete-orphan"
    )
    card_multipliers: Mapped[list["WalletCardMultiplier"]] = relationship(
        back_populates="wallet", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Wallet id={self.id} name={self.name!r}>"


class WalletCard(Base):
    """
    A card in a wallet with added_date and optional overrides vs the library Card.
    Null sub_* / annual_fee / first_year_fee means use Card defaults.
    Selected statement credits and their valuations live in WalletCardCredit rows
    (wallet_card_credits table); each row attaches one global library credit to
    this wallet card with a user-set value.
    """

    __tablename__ = "wallet_cards"
    __table_args__ = (UniqueConstraint("wallet_id", "card_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_id: Mapped[int] = mapped_column(
        ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False
    )
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"), nullable=False)
    added_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Optional SUB overrides (null = use Card's value)
    sub_points: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sub_min_spend: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sub_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sub_spend_earn: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    years_counted: Mapped[int] = mapped_column(Integer, default=2)

    # Optional annual_bonus override (null = use Card's annual_bonus)
    annual_bonus: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    annual_bonus_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    annual_bonus_first_year_only: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # Optional fee overrides (null = use Card's annual_fee / first_year_fee)
    annual_fee: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    first_year_fee: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Optional secondary currency rate override (null = use Card's secondary_currency_rate)
    secondary_currency_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Roadmap tracking
    sub_earned_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    sub_projected_earn_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    closed_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    # Set when this card is the "from" card in a product change; grayed out in UI.
    product_changed_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Acquisition tracking: "opened" = new application, "product_change" = PC from same issuer
    acquisition_type: Mapped[str] = mapped_column(String(20), nullable=False, default="opened")
    # For product_change cards: the library card_id of the card that was changed FROM.
    pc_from_card_id: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Panel placement:
    #   "in_wallet"    = currently held; included in calculations
    #   "future_cards" = not yet held but committed (added_date in the future); included in calculations
    #   "considering"  = candidate, not committed; excluded from calculations
    # Closed state is derived from `closed_date` and is not stored in this column.
    panel: Mapped[str] = mapped_column(String(16), nullable=False, default="considering")

    # Whether this card is included in wallet calculations. False = excluded
    # (equivalent to the legacy "considering" panel). Used by the Roadmap Tool
    # redesign's on/off toggle.
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    wallet: Mapped["Wallet"] = relationship(back_populates="wallet_cards")
    card: Mapped["Card"] = relationship(back_populates="wallet_cards")
    credit_overrides_rows: Mapped[list["WalletCardCredit"]] = relationship(
        back_populates="wallet_card", cascade="all, delete-orphan"
    )
    group_selections: Mapped[list["WalletCardGroupSelection"]] = relationship(
        back_populates="wallet_card", cascade="all, delete-orphan"
    )
    category_priorities: Mapped[list["WalletCardCategoryPriority"]] = relationship(
        back_populates="wallet_card", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<WalletCard wallet={self.wallet_id} card={self.card_id} added={self.added_date}>"
