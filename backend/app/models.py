"""ORM models - re-exported from DAL for backward compatibility.

All models have been moved to the dal/ package, organized by domain.
This module re-exports everything for existing imports to continue working.
"""

from .dal import (
    # User
    User,
    # Reference data
    Issuer,
    CoBrand,
    Network,
    NetworkTier,
    SpendCategory,
    IssuerApplicationRule,
    # Currency
    Currency,
    # Card
    Card,
    CardMultiplierGroup,
    CardCategoryMultiplier,
    RotatingCategory,
    travel_portal_cards,
    # Credit
    Credit,
    CardCredit,
    # Travel portal
    TravelPortal,
    # Wallet
    Wallet,
    WalletCard,
    # Wallet currency
    WalletCurrencyCpp,
    # Wallet card overrides
    WalletCardCredit,
    WalletCardGroupSelection,
    WalletCardCategoryPriority,
    WalletCardMultiplier,
    # Wallet spend
    WalletSpendItem,
    # Wallet portal
    WalletPortalShare,
    # User spend categories
    UserSpendCategory,
    UserSpendCategoryMapping,
)

__all__ = [
    "User",
    "Issuer",
    "CoBrand",
    "Network",
    "NetworkTier",
    "SpendCategory",
    "IssuerApplicationRule",
    "Currency",
    "Card",
    "CardMultiplierGroup",
    "CardCategoryMultiplier",
    "RotatingCategory",
    "travel_portal_cards",
    "Credit",
    "CardCredit",
    "TravelPortal",
    "Wallet",
    "WalletCard",
    "WalletCurrencyCpp",
    "WalletCardCredit",
    "WalletCardGroupSelection",
    "WalletCardCategoryPriority",
    "WalletCardMultiplier",
    "WalletSpendItem",
    "WalletPortalShare",
    "UserSpendCategory",
    "UserSpendCategoryMapping",
]
