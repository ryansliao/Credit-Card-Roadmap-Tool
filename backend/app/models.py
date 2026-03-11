from datetime import date
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    """Minimal user model so wallets can be tied to a user (single-tenant: one default user)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="Default User")

    wallets: Mapped[list["Wallet"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} name={self.name!r}>"


class Issuer(Base):
    """A credit card issuer (e.g. Chase, American Express, Citi)."""

    __tablename__ = "issuers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    co_brand_partner: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    network: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)

    currencies: Mapped[list["Currency"]] = relationship(
        back_populates="issuer", cascade="all, delete-orphan"
    )
    cards: Mapped[list["Card"]] = relationship(back_populates="issuer")

    def __repr__(self) -> str:
        return f"<Issuer id={self.id} name={self.name!r}>"


class Currency(Base):
    """
    A reward currency. May be tied to an issuer (issuer_id set) or standalone (e.g. Cash).
    Cash is treated as its own currency (is_cashback=True).
    """

    __tablename__ = "currencies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issuer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("issuers.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    cents_per_point: Mapped[float] = mapped_column(Float, default=1.0)
    # True for cash (its own currency); False for point currencies
    is_cashback: Mapped[bool] = mapped_column(Boolean, default=False)
    # True when points can be transferred to airline/hotel partners
    is_transferable: Mapped[bool] = mapped_column(Boolean, default=True)
    # When is_cashback: if True, this cash can convert to the issuer's point currency
    # when an anchor card (anchors_cashback_conversion) is in the wallet.
    converts_to_points: Mapped[bool] = mapped_column(Boolean, default=False)
    # When converts_to_points: the point currency this cash converts to (same issuer).
    converts_to_currency_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=True
    )

    issuer: Mapped[Optional["Issuer"]] = relationship(back_populates="currencies")
    cards: Mapped[list["Card"]] = relationship(
        back_populates="currency_obj",
        foreign_keys="Card.currency_id",
    )
    converts_to_currency: Mapped[Optional["Currency"]] = relationship(
        "Currency",
        foreign_keys=[converts_to_currency_id],
        remote_side=[id],
    )

    def __repr__(self) -> str:
        return f"<Currency id={self.id} name={self.name!r}>"


class Ecosystem(Base):
    """
    A points ecosystem (e.g. Chase UR, Amex MR, Marriott Bonvoy).
    Independent of issuer. When a key card is in the wallet, beneficiary cards
    whose currency is cashback_currency or in ecosystem_currencies earn the points_currency.
    """

    __tablename__ = "ecosystems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    points_currency_id: Mapped[int] = mapped_column(
        ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=False
    )
    cashback_currency_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("currencies.id", ondelete="SET NULL"), nullable=True
    )

    points_currency: Mapped["Currency"] = relationship(
        "Currency", foreign_keys=[points_currency_id]
    )
    cashback_currency: Mapped[Optional["Currency"]] = relationship(
        "Currency", foreign_keys=[cashback_currency_id]
    )
    # Additional currencies (beyond cashback) that convert to points when a key card is in wallet
    ecosystem_currencies: Mapped[list["EcosystemCurrency"]] = relationship(
        back_populates="ecosystem", cascade="all, delete-orphan"
    )
    card_memberships: Mapped[list["CardEcosystem"]] = relationship(
        back_populates="ecosystem", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Ecosystem id={self.id} name={self.name!r}>"


class EcosystemCurrency(Base):
    """Currencies that convert to this ecosystem's points when a key card is in wallet (e.g. Cash)."""

    __tablename__ = "ecosystem_currencies"
    __table_args__ = (UniqueConstraint("ecosystem_id", "currency_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ecosystem_id: Mapped[int] = mapped_column(
        ForeignKey("ecosystems.id", ondelete="CASCADE"), nullable=False
    )
    currency_id: Mapped[int] = mapped_column(
        ForeignKey("currencies.id", ondelete="CASCADE"), nullable=False
    )

    ecosystem: Mapped["Ecosystem"] = relationship(back_populates="ecosystem_currencies")
    currency: Mapped["Currency"] = relationship("Currency")

    def __repr__(self) -> str:
        return f"<EcosystemCurrency ecosystem_id={self.ecosystem_id} currency_id={self.currency_id}>"


class CardEcosystem(Base):
    """Junction: card membership in an ecosystem, with key_card = unlocks conversion for that ecosystem."""

    __tablename__ = "card_ecosystems"
    __table_args__ = (UniqueConstraint("card_id", "ecosystem_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    card_id: Mapped[int] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"), nullable=False
    )
    ecosystem_id: Mapped[int] = mapped_column(
        ForeignKey("ecosystems.id", ondelete="CASCADE"), nullable=False
    )
    # True = this card being in the wallet unlocks conversion for the ecosystem
    key_card: Mapped[bool] = mapped_column(Boolean, default=False)

    card: Mapped["Card"] = relationship(back_populates="ecosystem_memberships")
    ecosystem: Mapped["Ecosystem"] = relationship(back_populates="card_memberships")

    def __repr__(self) -> str:
        return f"<CardEcosystem card_id={self.card_id} ecosystem_id={self.ecosystem_id} key_card={self.key_card}>"


class Card(Base):
    """Static data for a single credit card."""

    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)

    issuer_id: Mapped[int] = mapped_column(
        ForeignKey("issuers.id", ondelete="RESTRICT"), nullable=False
    )
    # Default currency for this card (may be cash)
    currency_id: Mapped[int] = mapped_column(
        ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=False
    )

    annual_fee: Mapped[float] = mapped_column(Float, default=0)

    # Sign-up bonus
    sub_points: Mapped[int] = mapped_column(Integer, default=0)
    sub_min_spend: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sub_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Points earned just from hitting the SUB spend (e.g. BBP 2x on that spend)
    sub_spend_points: Mapped[int] = mapped_column(Integer, default=0)

    # Recurring annual bonus points (e.g. Chase Ink Preferred 10k points/year)
    annual_bonus_points: Mapped[int] = mapped_column(Integer, default=0)

    issuer: Mapped["Issuer"] = relationship(
        back_populates="cards", foreign_keys=[issuer_id]
    )
    currency_obj: Mapped["Currency"] = relationship(
        back_populates="cards", foreign_keys=[currency_id]
    )
    ecosystem_memberships: Mapped[list["CardEcosystem"]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )

    multipliers: Mapped[list["CardCategoryMultiplier"]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )
    credits: Mapped[list["CardCredit"]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )
    scenario_cards: Mapped[list["ScenarioCard"]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )
    wallet_cards: Mapped[list["WalletCard"]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Card id={self.id} name={self.name!r}>"


class CardCategoryMultiplier(Base):
    """Points multiplier for a card in a specific spend category."""

    __tablename__ = "card_category_multipliers"
    __table_args__ = (UniqueConstraint("card_id", "category"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    multiplier: Mapped[float] = mapped_column(Float, default=1.0)

    card: Mapped["Card"] = relationship(back_populates="multipliers")


class CardCredit(Base):
    """Monetary credit / perk value offered by a card."""

    __tablename__ = "card_credits"
    __table_args__ = (UniqueConstraint("card_id", "credit_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"))
    credit_name: Mapped[str] = mapped_column(String(120), nullable=False)
    credit_value: Mapped[float] = mapped_column(Float, default=0)

    card: Mapped["Card"] = relationship(back_populates="credits")


class SpendCategory(Base):
    """User's annual spend per category."""

    __tablename__ = "spend_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    annual_spend: Mapped[float] = mapped_column(Float, default=0)


class Scenario(Base):
    """
    A named wallet scenario for roadmap modeling.
    Each scenario captures a set of cards that are active during a date range.
    """

    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    as_of_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    scenario_cards: Mapped[list["ScenarioCard"]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Scenario id={self.id} name={self.name!r}>"


class ScenarioCard(Base):
    """
    Maps a card to a scenario with an optional active date window.
    If end_date is None the card is still held.
    years_counted overrides the global setting for this card in this scenario.
    """

    __tablename__ = "scenario_cards"
    __table_args__ = (UniqueConstraint("scenario_id", "card_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(
        ForeignKey("scenarios.id", ondelete="CASCADE")
    )
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"))
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    years_counted: Mapped[int] = mapped_column(Integer, default=2)

    scenario: Mapped["Scenario"] = relationship(back_populates="scenario_cards")
    card: Mapped["Card"] = relationship(back_populates="scenario_cards")

    def __repr__(self) -> str:
        return (
            f"<ScenarioCard scenario={self.scenario_id} card={self.card_id} "
            f"start={self.start_date} end={self.end_date}>"
        )


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

    user: Mapped["User"] = relationship(back_populates="wallets")
    wallet_cards: Mapped[list["WalletCard"]] = relationship(
        back_populates="wallet", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Wallet id={self.id} name={self.name!r}>"


class WalletCard(Base):
    """
    A card in a wallet with added_date and optional SUB overrides.
    If sub_points/sub_min_spend/sub_months/sub_spend_points are null, use Card's values.
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
    sub_spend_points: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    years_counted: Mapped[int] = mapped_column(Integer, default=2)

    wallet: Mapped["Wallet"] = relationship(back_populates="wallet_cards")
    card: Mapped["Card"] = relationship(back_populates="wallet_cards")

    def __repr__(self) -> str:
        return f"<WalletCard wallet={self.wallet_id} card={self.card_id} added={self.added_date}>"
