from datetime import date
from typing import Optional

from sqlalchemy import (
    JSON,
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

    cards: Mapped[list["Card"]] = relationship(back_populates="issuer")
    application_rules: Mapped[list["IssuerApplicationRule"]] = relationship(
        back_populates="issuer", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Issuer id={self.id} name={self.name!r}>"


class CoBrand(Base):
    """A co-brand partner attached to a card (e.g. Amazon, Delta, Bilt)."""

    __tablename__ = "co_brands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)

    cards: Mapped[list["Card"]] = relationship(back_populates="co_brand")

    def __repr__(self) -> str:
        return f"<CoBrand id={self.id} name={self.name!r}>"


class Network(Base):
    """Payment network (e.g. Visa, Mastercard). Fixed reference list for card network choice."""

    __tablename__ = "networks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)

    tiers: Mapped[list["NetworkTier"]] = relationship(back_populates="network")

    def __repr__(self) -> str:
        return f"<Network id={self.id} name={self.name!r}>"


class NetworkTier(Base):
    """Card tier within a network (e.g. Visa Signature, World Elite Mastercard). Fixed reference list."""

    __tablename__ = "network_tiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    network_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("networks.id", ondelete="SET NULL"), nullable=True
    )

    network: Mapped[Optional["Network"]] = relationship(back_populates="tiers")

    def __repr__(self) -> str:
        return f"<NetworkTier id={self.id} name={self.name!r}>"


class Currency(Base):
    """
    A reward currency (e.g. Chase UR, Cash).

    cash_transfer_rate: rate when redeeming as cash/statement credit (1.0 = pure cash, 0.01 = 1¢/pt).
    partner_transfer_rate: rate for airline/hotel partner transfers; null = not transferable.
    converts_to_currency_id: upgrade pointer — when any wallet card earns the target currency
        directly, this currency automatically upgrades to it (e.g. UR Cash → UR, Citi TY Limited → Citi TY).
    """

    __tablename__ = "currencies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    # "points" (incl. miles) vs "cash" — affects display and CPP override behavior
    reward_kind: Mapped[str] = mapped_column(String(20), default="points", nullable=False)
    cents_per_point: Mapped[float] = mapped_column(Float, default=1.0)
    # Rate for partner transfers (e.g. 1.0 = 1:1, 0.7 = 1:0.7); null = not partner-transferable
    partner_transfer_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Rate for cash/statement credit redemption (e.g. 1.0 for pure cash, 0.01 for 1¢/pt); null = not set
    cash_transfer_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Optional upgrade pointer: if set, this currency converts to the target when
    # any wallet card earns the target currency directly.
    converts_to_currency_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=True
    )
    # When converting to target: 1 unit of this currency = converts_at_rate units of target (e.g. 0.7 for 1:0.7)
    converts_at_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    cards: Mapped[list["Card"]] = relationship(
        back_populates="currency_obj",
        foreign_keys="Card.currency_id",
    )
    converts_to_currency: Mapped[Optional["Currency"]] = relationship(
        "Currency",
        foreign_keys=[converts_to_currency_id],
        remote_side=[id],
    )
    wallet_cpp_overrides: Mapped[list["WalletCurrencyCpp"]] = relationship(
        back_populates="currency", cascade="all, delete-orphan"
    )
    wallet_balances: Mapped[list["WalletCurrencyBalance"]] = relationship(
        "WalletCurrencyBalance", back_populates="currency", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Currency id={self.id} name={self.name!r}>"




class Card(Base):
    """Static data for a single credit card."""

    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)

    issuer_id: Mapped[int] = mapped_column(
        ForeignKey("issuers.id", ondelete="RESTRICT"), nullable=False
    )
    co_brand_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("co_brands.id", ondelete="SET NULL"), nullable=True
    )
    # Default currency for this card (may be cash)
    currency_id: Mapped[int] = mapped_column(
        ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=False
    )

    annual_fee: Mapped[float] = mapped_column(Float, default=0)
    # First year annual fee (optional; if set, often lower than annual_fee, e.g. waived or reduced)
    first_year_fee: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    business: Mapped[bool] = mapped_column(Boolean, default=False)
    network_tier_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("network_tiers.id", ondelete="SET NULL"), nullable=True
    )

    # Sign-up bonus (all optional)
    sub: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sub_min_spend: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sub_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Amount earned just from hitting the SUB spend (e.g. BBP 2x on that spend; can be points or cash)
    sub_spend_earn: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Recurring annual bonus (e.g. Chase Ink Preferred 10k points/year; can be points or cash)
    annual_bonus: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)

    # Roadmap: how many months before the SUB can be earned again (e.g. 48 for Sapphire family)
    sub_recurrence_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Roadmap: SUB eligibility family (cards in same family share a cooldown, e.g. "sapphire")
    sub_family: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)

    issuer: Mapped["Issuer"] = relationship(
        back_populates="cards", foreign_keys=[issuer_id]
    )
    co_brand: Mapped[Optional["CoBrand"]] = relationship(
        back_populates="cards", foreign_keys=[co_brand_id]
    )
    currency_obj: Mapped["Currency"] = relationship(
        back_populates="cards", foreign_keys=[currency_id]
    )
    network_tier: Mapped[Optional["NetworkTier"]] = relationship(
        "NetworkTier", foreign_keys=[network_tier_id]
    )

    multipliers: Mapped[list["CardCategoryMultiplier"]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )
    multiplier_groups: Mapped[list["CardMultiplierGroup"]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )
    credits: Mapped[list["CardCredit"]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )
    wallet_cards: Mapped[list["WalletCard"]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )
    wallet_multipliers: Mapped[list["WalletCardMultiplier"]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Card id={self.id} name={self.name!r}>"


# Cap period for spend caps: monthly, quarterly, or annually
CAP_PERIOD_MONTHLY = "monthly"
CAP_PERIOD_QUARTERLY = "quarterly"
CAP_PERIOD_ANNUALLY = "annually"


class CardMultiplierGroup(Base):
    """
    A group of categories that share one multiplier, optional cap, and optional
    'top N' behavior (e.g. 5% on top 2 eligible categories by spend, up to $500/month).
    """

    __tablename__ = "card_multiplier_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"))
    multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    cap_per_billing_cycle: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cap_period: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # monthly, quarterly, annually
    top_category_only: Mapped[bool] = mapped_column(Boolean, default=False)  # legacy; prefer top_n_categories
    top_n_categories: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1=top 1, 2=top 2, etc.; None=all

    card: Mapped["Card"] = relationship(back_populates="multiplier_groups")
    categories: Mapped[list["CardCategoryMultiplier"]] = relationship(
        back_populates="multiplier_group", cascade="all, delete-orphan"
    )


class CardCategoryMultiplier(Base):
    """
    Points multiplier for a card in a specific spend category.
    Either standalone (multiplier_group_id NULL) or part of a CardMultiplierGroup.
    When in a group, the group's multiplier, cap_per_billing_cycle, and top_n_categories apply.
    is_portal: when True, the multiplier only applies when booking through the card's travel portal.
    """

    __tablename__ = "card_category_multipliers"
    __table_args__ = (UniqueConstraint("card_id", "category_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"))
    category_id: Mapped[int] = mapped_column(
        ForeignKey("spend_categories.id", ondelete="RESTRICT"), nullable=False
    )
    is_portal: Mapped[bool] = mapped_column(Boolean, default=False)
    multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    cap_per_billing_cycle: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cap_period: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # monthly, quarterly, annually
    multiplier_group_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("card_multiplier_groups.id", ondelete="CASCADE"), nullable=True
    )

    card: Mapped["Card"] = relationship(back_populates="multipliers")
    spend_category: Mapped["SpendCategory"] = relationship(back_populates="card_multipliers")
    multiplier_group: Mapped[Optional["CardMultiplierGroup"]] = relationship(
        back_populates="categories"
    )

    @property
    def category(self) -> str:
        """Convenience accessor: returns the spend category name via the relationship."""
        return self.spend_category.category if self.spend_category else ""


class CardCredit(Base):
    """Statement credit or perk. `credit_value` is dollars; recurring unless `is_one_time`."""

    __tablename__ = "card_credits"
    __table_args__ = (UniqueConstraint("card_id", "credit_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"))
    credit_name: Mapped[str] = mapped_column(String(120), nullable=False)
    credit_value: Mapped[float] = mapped_column(Float, default=0)
    is_one_time: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    card: Mapped["Card"] = relationship(back_populates="credits")
    wallet_credit_overrides: Mapped[list["WalletCardCredit"]] = relationship(
        back_populates="library_credit", cascade="all, delete-orphan"
    )


class SpendCategory(Base):
    """
    Unified spend category: card multiplier categories AND user-facing spend buckets.
    The parent_id/children hierarchy is used for the spend picker UI.
    is_system=True marks "All Other" (cannot be deleted or renamed by users).
    "All Other" is pinned to ID 1, "Travel" to ID 2.
    """

    __tablename__ = "spend_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("spend_categories.id", ondelete="RESTRICT"), nullable=True
    )
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)

    parent: Mapped[Optional["SpendCategory"]] = relationship(
        "SpendCategory",
        back_populates="children",
        foreign_keys=[parent_id],
        remote_side="SpendCategory.id",
    )
    children: Mapped[list["SpendCategory"]] = relationship(
        "SpendCategory",
        back_populates="parent",
        foreign_keys=[parent_id],
        order_by="SpendCategory.category",
    )
    card_multipliers: Mapped[list["CardCategoryMultiplier"]] = relationship(
        back_populates="spend_category"
    )
    wallet_spend_mappings: Mapped[list["WalletSpendCategoryMapping"]] = relationship(
        back_populates="spend_category"
    )
    wallet_card_multipliers: Mapped[list["WalletCardMultiplier"]] = relationship(
        back_populates="spend_category"
    )
    wallet_spend_items: Mapped[list["WalletSpendItem"]] = relationship(
        back_populates="spend_category", cascade="all, delete-orphan"
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

    # Persisted calculation configuration (saved on each successful calculate)
    calc_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    calc_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    calc_duration_years: Mapped[int] = mapped_column(Integer, default=2, server_default="2")
    calc_duration_months: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    calc_window_mode: Mapped[str] = mapped_column(String(20), default="duration", server_default="duration")

    user: Mapped["User"] = relationship(back_populates="wallets")
    wallet_cards: Mapped[list["WalletCard"]] = relationship(
        back_populates="wallet", cascade="all, delete-orphan"
    )
    currency_balances: Mapped[list["WalletCurrencyBalance"]] = relationship(
        "WalletCurrencyBalance", back_populates="wallet", cascade="all, delete-orphan"
    )
    spend_categories: Mapped[list["WalletSpendCategory"]] = relationship(
        back_populates="wallet", cascade="all, delete-orphan"
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
    Per-credit valuations are stored in WalletCardCredit rows (wallet_card_credits table).
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
    sub: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sub_min_spend: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sub_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sub_spend_earn: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    years_counted: Mapped[int] = mapped_column(Integer, default=2)

    # Optional annual_bonus override (null = use Card's annual_bonus)
    annual_bonus: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Optional fee overrides (null = use Card's annual_fee / first_year_fee)
    annual_fee: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    first_year_fee: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Roadmap tracking
    sub_earned_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    sub_projected_earn_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    closed_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Acquisition tracking: "opened" = new application, "product_change" = PC from same issuer
    acquisition_type: Mapped[str] = mapped_column(String(20), nullable=False, default="opened")

    wallet: Mapped["Wallet"] = relationship(back_populates="wallet_cards")
    card: Mapped["Card"] = relationship(back_populates="wallet_cards")
    credit_overrides_rows: Mapped[list["WalletCardCredit"]] = relationship(
        back_populates="wallet_card", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<WalletCard wallet={self.wallet_id} card={self.card_id} added={self.added_date}>"




class WalletCurrencyBalance(Base):
    """
    Per-wallet currency points: user-set initial balance plus projection-period earn
    updated when the wallet is calculated. user_tracked = user added this row explicitly.
    """

    __tablename__ = "wallet_currency_balances"
    __table_args__ = (UniqueConstraint("wallet_id", "currency_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_id: Mapped[int] = mapped_column(
        ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False
    )
    currency_id: Mapped[int] = mapped_column(
        ForeignKey("currencies.id", ondelete="CASCADE"), nullable=False
    )
    initial_balance: Mapped[float] = mapped_column(Float, default=0.0)
    projection_earn: Mapped[float] = mapped_column(Float, default=0.0)
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    user_tracked: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    wallet: Mapped["Wallet"] = relationship(back_populates="currency_balances")
    currency: Mapped["Currency"] = relationship(back_populates="wallet_balances")

    def __repr__(self) -> str:
        return (
            f"<WalletCurrencyBalance w={self.wallet_id} c={self.currency_id} "
            f"init={self.initial_balance} proj={self.projection_earn}>"
        )


class IssuerApplicationRule(Base):
    """
    Velocity / eligibility rule for a card issuer (e.g. Chase 5/24, Amex 1/90).
    Used by the roadmap to flag potential application denials.

    max_count: maximum new cards allowed within period_days
    period_days: look-back window in days
    personal_only: if True, only count personal (non-business) cards toward the limit
    scope_all_issuers: if True, the count spans ALL issuers (e.g. Chase 5/24 counts every issuer's cards)
    """

    __tablename__ = "issuer_application_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issuer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("issuers.id", ondelete="CASCADE"), nullable=True
    )
    rule_name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    max_count: Mapped[int] = mapped_column(Integer, nullable=False)
    period_days: Mapped[int] = mapped_column(Integer, nullable=False)
    personal_only: Mapped[bool] = mapped_column(Boolean, default=False)
    scope_all_issuers: Mapped[bool] = mapped_column(Boolean, default=False)

    issuer: Mapped[Optional["Issuer"]] = relationship(back_populates="application_rules")

    def __repr__(self) -> str:
        return f"<IssuerApplicationRule id={self.id} rule={self.rule_name!r} issuer_id={self.issuer_id}>"


# ---------------------------------------------------------------------------
# Wallet-level instance tables (wallet-scoped overrides replacing user-scoped tables)
# ---------------------------------------------------------------------------


class WalletCardCredit(Base):
    """
    Wallet-level override of a statement credit value/type for a specific wallet card.
    Replaces the former credit_overrides JSON blob on WalletCard.
    When no row exists for a (wallet_card_id, library_credit_id) pair, the library value is used.
    """

    __tablename__ = "wallet_card_credits"
    __table_args__ = (UniqueConstraint("wallet_card_id", "library_credit_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_card_id: Mapped[int] = mapped_column(
        ForeignKey("wallet_cards.id", ondelete="CASCADE"), nullable=False
    )
    library_credit_id: Mapped[int] = mapped_column(
        ForeignKey("card_credits.id", ondelete="CASCADE"), nullable=False
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)
    is_one_time: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    wallet_card: Mapped["WalletCard"] = relationship(back_populates="credit_overrides_rows")
    library_credit: Mapped["CardCredit"] = relationship(back_populates="wallet_credit_overrides")

    def __repr__(self) -> str:
        return f"<WalletCardCredit wc={self.wallet_card_id} credit={self.library_credit_id} value={self.value}>"


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

    wallet: Mapped["Wallet"] = relationship(back_populates="cpp_overrides")
    currency: Mapped["Currency"] = relationship(back_populates="wallet_cpp_overrides")

    def __repr__(self) -> str:
        return f"<WalletCurrencyCpp wallet={self.wallet_id} currency={self.currency_id} cpp={self.cents_per_point}>"


class WalletSpendCategory(Base):
    """
    Wallet-scoped spend bucket (e.g. 'Travel', 'Dining Out').
    Each wallet has its own spend profile.
    """

    __tablename__ = "wallet_spend_categories"
    __table_args__ = (UniqueConstraint("wallet_id", "name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_id: Mapped[int] = mapped_column(
        ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    amount: Mapped[float] = mapped_column(Float, default=0.0)

    wallet: Mapped["Wallet"] = relationship(back_populates="spend_categories")
    mappings: Mapped[list["WalletSpendCategoryMapping"]] = relationship(
        back_populates="wallet_spend_category", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<WalletSpendCategory wallet={self.wallet_id} name={self.name!r} amount={self.amount}>"


class WalletSpendCategoryMapping(Base):
    """
    Allocates part of a WalletSpendCategory bucket (annual $) to a global SpendCategory.
    Allocates part of a WalletSpendCategory bucket (annual $) to a global SpendCategory.
    """

    __tablename__ = "wallet_spend_category_mappings"
    __table_args__ = (UniqueConstraint("wallet_spend_category_id", "spend_category_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_spend_category_id: Mapped[int] = mapped_column(
        ForeignKey("wallet_spend_categories.id", ondelete="CASCADE"), nullable=False
    )
    spend_category_id: Mapped[int] = mapped_column(
        ForeignKey("spend_categories.id", ondelete="RESTRICT"), nullable=False
    )
    allocation: Mapped[float] = mapped_column(Float, default=0.0)

    wallet_spend_category: Mapped["WalletSpendCategory"] = relationship(back_populates="mappings")
    spend_category: Mapped["SpendCategory"] = relationship(back_populates="wallet_spend_mappings")

    def __repr__(self) -> str:
        return (
            f"<WalletSpendCategoryMapping wsc={self.wallet_spend_category_id} "
            f"sc={self.spend_category_id} alloc={self.allocation}>"
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

    wallet: Mapped["Wallet"] = relationship(back_populates="card_multipliers")
    card: Mapped["Card"] = relationship(back_populates="wallet_multipliers")
    spend_category: Mapped["SpendCategory"] = relationship(back_populates="wallet_card_multipliers")

    @property
    def category(self) -> str:
        return self.spend_category.category if self.spend_category else ""

    def __repr__(self) -> str:
        return f"<WalletCardMultiplier wallet={self.wallet_id} card={self.card_id} category={self.category_id} mult={self.multiplier}>"


class WalletSpendItem(Base):
    """
    Per-wallet spend item: how much a user spends annually in a given SpendCategory.
    Replaces WalletSpendCategory + WalletSpendCategoryMapping.
    The SpendCategory itself is both the card multiplier category and the user-facing name.
    """

    __tablename__ = "wallet_spend_items"
    __table_args__ = (UniqueConstraint("wallet_id", "spend_category_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_id: Mapped[int] = mapped_column(
        ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False
    )
    spend_category_id: Mapped[int] = mapped_column(
        ForeignKey("spend_categories.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Float, default=0.0)

    wallet: Mapped["Wallet"] = relationship(back_populates="spend_items")
    spend_category: Mapped["SpendCategory"] = relationship(
        back_populates="wallet_spend_items"
    )

    def __repr__(self) -> str:
        return f"<WalletSpendItem wallet={self.wallet_id} sc={self.spend_category_id} amount={self.amount}>"
