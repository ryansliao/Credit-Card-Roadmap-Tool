from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .card_instance import CardInstance
    from .credit import CardCredit
    from .currency import Currency
    from .reference import CoBrand, Issuer, NetworkTier, SpendCategory
    from .travel_portal import TravelPortal


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

    # Delta TakeOff 15: when true, the card earns a 15% discount on Delta
    # award redemptions. Modelled as a CPP boost: effective CPP = cpp / 0.85.
    takeoff15_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

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
    card_instances: Mapped[list["CardInstance"]] = relationship(
        back_populates="card",
        cascade="all, delete-orphan",
        foreign_keys="CardInstance.card_id",
    )
    card_credit_links: Mapped[list["CardCredit"]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )

    travel_portals: Mapped[list["TravelPortal"]] = relationship(
        secondary="travel_portal_cards", back_populates="cards"
    )

    def __repr__(self) -> str:
        return f"<Card id={self.id} name={self.name!r}>"


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
