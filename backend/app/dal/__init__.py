"""Data Access Layer - ORM models organized by domain.

All models are re-exported here for backward compatibility with existing imports.
"""

from .user import User
from .reference import (
    Issuer,
    CoBrand,
    Network,
    NetworkTier,
    SpendCategory,
    IssuerApplicationRule,
)
from .currency import Currency
from .card import (
    Card,
    CardMultiplierGroup,
    CardCategoryMultiplier,
    RotatingCategory,
    travel_portal_cards,
)
from .credit import Credit, CardCredit
from .travel_portal import TravelPortal
from .wallet import Wallet, WalletCard
from .wallet_currency import WalletCurrencyCpp
from .wallet_card_override import (
    WalletCardCredit,
    WalletCardGroupSelection,
    WalletCardCategoryPriority,
    WalletCardMultiplier,
)
from .wallet_spend import WalletSpendItem
from .wallet_portal import WalletPortalShare
from .user_spend import UserSpendCategory, UserSpendCategoryMapping

__all__ = [
    # User
    "User",
    # Reference data
    "Issuer",
    "CoBrand",
    "Network",
    "NetworkTier",
    "SpendCategory",
    "IssuerApplicationRule",
    # Currency
    "Currency",
    # Card
    "Card",
    "CardMultiplierGroup",
    "CardCategoryMultiplier",
    "RotatingCategory",
    "travel_portal_cards",
    # Credit
    "Credit",
    "CardCredit",
    # Travel portal
    "TravelPortal",
    # Wallet
    "Wallet",
    "WalletCard",
    # Wallet currency
    "WalletCurrencyCpp",
    # Wallet card overrides
    "WalletCardCredit",
    "WalletCardGroupSelection",
    "WalletCardCategoryPriority",
    "WalletCardMultiplier",
    # Wallet spend
    "WalletSpendItem",
    # Wallet portal
    "WalletPortalShare",
    # User spend categories
    "UserSpendCategory",
    "UserSpendCategoryMapping",
]
