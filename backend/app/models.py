from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base



class User(Base):
    """User model — authenticated via Google Sign-In or local credentials."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[Optional[str]] = mapped_column(String(40), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="Default User")
    google_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    picture: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    wallets: Mapped[list["Wallet"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} name={self.name!r} email={self.email!r}>"


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
        ForeignKey("currencies.id", ondelete="NO ACTION"), nullable=True
    )
    # When converting to target: 1 unit of this currency = converts_at_rate units of target (e.g. 0.7 for 1:0.7)
    converts_at_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # CPP to use when no transfer enabler card is present in the wallet for this currency;
    # null = no reduction (currency is always valued at cents_per_point).
    # Used for ecosystems where transfers are completely blocked (e.g. Chase UR without Sapphire).
    no_transfer_cpp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Multiplier applied to the wallet's CPP when no transfer enabler is present;
    # null = no rate-based reduction. Used for ecosystems where transfers are available
    # but at a reduced rate (e.g. Citi TY 0.7 without Strata Premier).
    # Takes precedence over no_transfer_cpp when set.
    no_transfer_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

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
        ForeignKey("issuers.id", ondelete="NO ACTION"), nullable=False
    )
    co_brand_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("co_brands.id", ondelete="SET NULL"), nullable=True
    )
    # Default currency for this card (may be cash)
    currency_id: Mapped[int] = mapped_column(
        ForeignKey("currencies.id", ondelete="NO ACTION"), nullable=False
    )

    annual_fee: Mapped[float] = mapped_column(Float, default=0)
    # First year annual fee (optional; if set, often lower than annual_fee, e.g. waived or reduced)
    first_year_fee: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    business: Mapped[bool] = mapped_column(Boolean, default=False)
    network_tier_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("network_tiers.id", ondelete="SET NULL"), nullable=True
    )

    # Sign-up bonus (all optional)
    sub_points: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sub_min_spend: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sub_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Amount earned just from hitting the SUB spend (e.g. BBP 2x on that spend; can be points or cash)
    sub_spend_earn: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Dollar-denominated SUB bonus (e.g. $200 cash back). Added at face value, not converted via CPP.
    sub_cash: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # SUB paid in the card's secondary currency (e.g. 10000 Bilt Cash = $100 face).
    # Subject to the same conversion cap as secondary currency earned from spend:
    # if ``secondary_currency_cap_rate > 0`` and the wallet has no housing spend,
    # this SUB contributes $0 to EAF.
    sub_secondary_points: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Recurring annual bonus (e.g. Chase Ink Preferred 10k points/year; can be points or cash)
    annual_bonus: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    # Percentage-based annual bonus: earns this % of the card's own category earn as bonus points.
    # e.g. 10.0 for CSP's 10% anniversary bonus, 100.0 for Discover IT's first-year cashback match.
    annual_bonus_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # When True, percentage bonus applies only in the first year (e.g. Discover IT match).
    # When False/null, percentage bonus recurs every year (e.g. CSP 10%).
    annual_bonus_first_year_only: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, default=False)

    # True if this card enables partner transfers for its currency ecosystem
    # (e.g. Sapphire Reserve for Chase UR, Strata Premier for Citi TY)
    transfer_enabler: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Secondary currency: optional second currency earned at a flat rate on all spend
    # (e.g. Bilt Cash at 4% on all everyday spending, alongside Bilt Points via multipliers)
    secondary_currency_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("currencies.id", ondelete="SET NULL"), nullable=True
    )
    secondary_currency_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Conversion cap: secondary currency can only convert to points when non-housing
    # spend on this card stays below cap_rate × housing spend. 0 = no cap. (e.g. 0.75 for Bilt)
    secondary_currency_cap_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Point accelerator: spend secondary currency to earn bonus primary points
    # (e.g. Bilt: $200 Bilt Cash for +1x on next $5,000, up to 5x/year)
    accelerator_cost: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    accelerator_spend_limit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    accelerator_bonus_multiplier: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    accelerator_max_activations: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Bilt 2.0: when true, the card's housing (Rent/Mortgage) earn rate is
    # computed from the ratio of non-housing to housing spend allocated to
    # the card (<25% → flat 250 pts/mo floor, 25/50/75/100% → 0.5/0.75/1.0/1.25x).
    # Mutually exclusive with the Bilt Cash secondary-currency mode — the
    # calculator evaluates both per card and picks the higher-value option.
    housing_tiered_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )

    # Filename stem for the card photo in frontend/public/photos/ (e.g. "chase_sapphire_reserve").
    photo_slug: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    # True when the card charges a foreign transaction fee (typically ~3%).
    # False = no FTF (preferred for international spend).
    foreign_transaction_fee: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # True when the card can pay rent/mortgage without the ~2.5-3% processing
    # fee that payment platforms typically charge for credit card housing
    # payments.  Only Bilt cards waive this fee via their built-in platform.
    housing_fee_waived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # Roadmap: how many months before the SUB can be earned again (e.g. 48 for Sapphire family)
    sub_recurrence_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Roadmap: SUB eligibility family (cards in same family share a cooldown, e.g. "sapphire")
    sub_family: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    issuer: Mapped["Issuer"] = relationship(
        back_populates="cards", foreign_keys=[issuer_id]
    )
    co_brand: Mapped[Optional["CoBrand"]] = relationship(
        back_populates="cards", foreign_keys=[co_brand_id]
    )
    currency_obj: Mapped["Currency"] = relationship(
        back_populates="cards", foreign_keys=[currency_id]
    )
    secondary_currency_obj: Mapped[Optional["Currency"]] = relationship(
        "Currency", foreign_keys=[secondary_currency_id]
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
    rotating_categories: Mapped[list["RotatingCategory"]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )
    wallet_cards: Mapped[list["WalletCard"]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )
    wallet_multipliers: Mapped[list["WalletCardMultiplier"]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )

    travel_portals: Mapped[list["TravelPortal"]] = relationship(
        secondary="travel_portal_cards", back_populates="cards"
    )

    def __repr__(self) -> str:
        return f"<Card id={self.id} name={self.name!r}>"


# Many-to-many: a TravelPortal contains the set of cards whose portal-only
# multipliers (CardCategoryMultiplier.is_portal=True) become eligible when
# the wallet has a portal share for that portal. A card may belong to more
# than one portal in principle.
travel_portal_cards = Table(
    "travel_portal_cards",
    Base.metadata,
    Column(
        "travel_portal_id",
        ForeignKey("travel_portals.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "card_id",
        ForeignKey("cards.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class TravelPortal(Base):
    """
    A travel booking portal (e.g. Chase Travel, Amex Travel, Capital One Travel).

    A portal owns the list of cards whose portal-only multipliers should be
    treated as earnable. The user's wallet sets a per-portal share to control
    what fraction of category spend is treated as booked through that portal.
    """

    __tablename__ = "travel_portals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)

    cards: Mapped[list["Card"]] = relationship(
        secondary="travel_portal_cards", back_populates="travel_portals"
    )

    def __repr__(self) -> str:
        return f"<TravelPortal id={self.id} name={self.name!r}>"


class CardMultiplierGroup(Base):
    """
    A group of categories that share one multiplier, optional cap, and optional
    'top N' behavior (e.g. 5% on top 2 eligible categories by spend, up to $500/month).

    cap_period_months: length of one cap period in calendar months. Common values:
    1 = monthly, 3 = quarterly, 6 = semi-annual, 12 = annual. NULL = no cap.

    is_rotating: when True, the group's category list is the *universe* of
    historically-rotated bonus categories, and per-category activation
    probabilities are inferred from `rotating_categories` rows on the
    parent card. The calculator treats each category's per-period cap as
    `cap_per_billing_cycle × p_C` instead of pooling the full cap across
    every category in the group.
    """

    __tablename__ = "card_multiplier_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"))
    multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    cap_per_billing_cycle: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cap_period_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    top_n_categories: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1=top 1, 2=top 2, etc.; None=all
    is_rotating: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_additive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

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
    is_additive: when True, the multiplier value is a *premium* that stacks onto
    the card's base + other applicable premiums (rather than replacing them).
    Used by cards like Chase Freedom Flex that earn 1x base + 2x dining premium
    + 4x rotating premium on overlapping categories (= 7x on dining-during-Q2).

    Uniqueness is enforced by two partial indexes (see migration 024):
        - at most one standalone row per (card, category)
        - at most one row per (card, category, multiplier_group)
    """

    __tablename__ = "card_category_multipliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"))
    category_id: Mapped[int] = mapped_column(
        ForeignKey("spend_categories.id", ondelete="NO ACTION"), nullable=False
    )
    is_portal: Mapped[bool] = mapped_column(Boolean, default=False)
    is_additive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    cap_per_billing_cycle: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cap_period_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    multiplier_group_id: Mapped[Optional[int]] = mapped_column(
        # NO ACTION: card_category_multipliers is cleaned up via card_id CASCADE when
        # a card is deleted, so this secondary path from card_multiplier_groups must
        # be NO ACTION to avoid a SQL Server multiple-cascade-paths error.
        ForeignKey("card_multiplier_groups.id", ondelete="NO ACTION"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    card: Mapped["Card"] = relationship(back_populates="multipliers")
    spend_category: Mapped["SpendCategory"] = relationship(back_populates="card_multipliers")
    multiplier_group: Mapped[Optional["CardMultiplierGroup"]] = relationship(
        back_populates="categories"
    )

    @property
    def category(self) -> str:
        """Convenience accessor: returns the spend category name via the relationship."""
        return self.spend_category.category if self.spend_category else ""


class RotatingCategory(Base):
    """
    One historical (year, quarter) bonus-category activation for a rotating card.

    Multiple rows per (card, year, quarter) are allowed when the issuer ran more
    than one bonus category in the same quarter (e.g. Chase Freedom Flex's
    "Gas + Select Streaming" quarters). The calculator collapses these rows
    into per-category activation probabilities `p_C = active_quarters / total_quarters`.
    """

    __tablename__ = "rotating_categories"
    __table_args__ = (
        UniqueConstraint("card_id", "year", "quarter", "spend_category_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    card_id: Mapped[int] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    quarter: Mapped[int] = mapped_column(Integer, nullable=False)
    spend_category_id: Mapped[int] = mapped_column(
        ForeignKey("spend_categories.id", ondelete="NO ACTION"), nullable=False
    )

    card: Mapped["Card"] = relationship(back_populates="rotating_categories")
    spend_category: Mapped["SpendCategory"] = relationship()

    @property
    def category_name(self) -> str:
        return self.spend_category.category if self.spend_category else ""

    def __repr__(self) -> str:
        return (
            f"<RotatingCategory card={self.card_id} {self.year}Q{self.quarter} "
            f"cat={self.spend_category_id}>"
        )


class Credit(Base):
    """
    Standardized statement credit / perk in the global library
    (e.g. Priority Pass, Global Entry, Free Checked Bags, Uber Cash).

    `credit_value` is the default dollar valuation; users can override it on a
    per-wallet-card basis via WalletCardCredit. Credits are recurring by default.
    When `excludes_first_year` is True, the credit is not counted in the first
    year of card ownership (e.g. anniversary free night awards).
    """

    __tablename__ = "credits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    credit_name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    excludes_first_year: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_one_time: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Currency this credit is denominated in. Cash (id=1) = dollar amount used directly.
    # Points currencies = value is in points, resolved via CPP.
    credit_currency_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("currencies.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    wallet_credit_overrides: Mapped[list["WalletCardCredit"]] = relationship(
        back_populates="library_credit", cascade="all, delete-orphan"
    )

    # Cards in the global library that natively offer this credit. Used by the UI to
    # auto-suggest credits when a card is added to a wallet.
    card_links: Mapped[list["CardCredit"]] = relationship(
        back_populates="credit",
        cascade="all, delete-orphan",
    )

    @property
    def card_ids(self) -> list[int]:
        return sorted(link.card_id for link in self.card_links)


class CardCredit(Base):
    """Join row linking a global library credit to a card that natively offers it.

    ``value`` is the issuer-stated dollar amount this specific card provides for
    the credit (e.g. Amex Gold Dining = $120, Marriott Brilliant Dining = $300).
    NULL means use the credit's default ``credits.value``.
    """

    __tablename__ = "card_credits"

    credit_id: Mapped[int] = mapped_column(
        ForeignKey("credits.id", ondelete="CASCADE"), primary_key=True
    )
    card_id: Mapped[int] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"), primary_key=True
    )
    value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    credit: Mapped["Credit"] = relationship(back_populates="card_links")


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
        ForeignKey("spend_categories.id", ondelete="NO ACTION"), nullable=True
    )
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    # True for housing categories (Rent, Mortgage) — used to compute secondary
    # currency conversion caps (e.g. Bilt Cash 75% of housing rule).
    is_housing: Mapped[bool] = mapped_column(Boolean, default=False)
    # True when a category can plausibly have foreign spend (travel, dining,
    # gas abroad). False for US-only recurring spend (Phone, Internet,
    # Streaming, Amazon, etc.). Gates _split_spend_for_foreign so the
    # wallet-level foreign-spend percentage only splits eligible categories.
    is_foreign_eligible: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )

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

    # Acquisition tracking: "opened" = new application, "product_change" = PC from same issuer
    acquisition_type: Mapped[str] = mapped_column(String(20), nullable=False, default="opened")

    # Panel placement:
    #   "in_wallet"    = currently held; included in calculations
    #   "future_cards" = not yet held but committed (added_date in the future); included in calculations
    #   "considering"  = candidate, not committed; excluded from calculations
    # Closed state is derived from `closed_date` and is not stored in this column.
    panel: Mapped[str] = mapped_column(String(16), nullable=False, default="considering")

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

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    issuer: Mapped[Optional["Issuer"]] = relationship(back_populates="application_rules")

    def __repr__(self) -> str:
        return f"<IssuerApplicationRule id={self.id} rule={self.rule_name!r} issuer_id={self.issuer_id}>"


# ---------------------------------------------------------------------------
# Wallet-level instance tables (wallet-scoped overrides replacing user-scoped tables)
# ---------------------------------------------------------------------------


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


class WalletPortalShare(Base):
    """
    Per-wallet per-travel-portal share. Determines what fraction of the
    wallet's spend in portal-eligible categories (e.g., Travel, Hotels) is
    treated as booked through that portal — and thus eligible for the
    portal-only multipliers on the cards belonging to that TravelPortal.

    A wallet has at most one row per portal. share is in [0, 1]. The default
    behavior when no row exists is share=0, which means portal-only
    multipliers contribute nothing until the user explicitly opts in.

    Cards belong to a portal via the travel_portal_cards association table —
    issuer is no longer the linking concept.
    """

    __tablename__ = "wallet_portal_shares"
    __table_args__ = (UniqueConstraint("wallet_id", "travel_portal_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_id: Mapped[int] = mapped_column(
        ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False
    )
    travel_portal_id: Mapped[int] = mapped_column(
        ForeignKey("travel_portals.id", ondelete="CASCADE"), nullable=False
    )
    share: Mapped[float] = mapped_column(Float, nullable=False)

    wallet: Mapped["Wallet"] = relationship()
    travel_portal: Mapped["TravelPortal"] = relationship()

    def __repr__(self) -> str:
        return f"<WalletPortalShare w={self.wallet_id} portal={self.travel_portal_id} share={self.share}>"


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


class WalletSpendItem(Base):
    """
    Per-wallet spend item: how much a user spends annually in a given SpendCategory.
    The SpendCategory itself is both the card multiplier category and the user-facing name.
    """

    __tablename__ = "wallet_spend_items"
    __table_args__ = (UniqueConstraint("wallet_id", "spend_category_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_id: Mapped[int] = mapped_column(
        ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False
    )
    spend_category_id: Mapped[int] = mapped_column(
        ForeignKey("spend_categories.id", ondelete="NO ACTION"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    wallet: Mapped["Wallet"] = relationship(back_populates="spend_items")
    spend_category: Mapped["SpendCategory"] = relationship(
        back_populates="wallet_spend_items"
    )

    def __repr__(self) -> str:
        return f"<WalletSpendItem wallet={self.wallet_id} sc={self.spend_category_id} amount={self.amount}>"
