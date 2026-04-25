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
from .scenario import Scenario
from .card_instance import CardInstance
from .scenario_overlay import ScenarioCardOverlay
from .scenario_overrides import (
    ScenarioCardMultiplier,
    ScenarioCardCredit,
    ScenarioCardCategoryPriority,
    ScenarioCardGroupSelection,
)
from .scenario_currency import (
    ScenarioCurrencyCpp,
    ScenarioCurrencyBalance,
    ScenarioPortalShare,
)

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
    # Wallet (legacy + new)
    "Wallet",
    "WalletCard",
    # Scenario (new)
    "Scenario",
    "CardInstance",
    "ScenarioCardOverlay",
    "ScenarioCardMultiplier",
    "ScenarioCardCredit",
    "ScenarioCardCategoryPriority",
    "ScenarioCardGroupSelection",
    "ScenarioCurrencyCpp",
    "ScenarioCurrencyBalance",
    "ScenarioPortalShare",
    # Wallet currency (legacy)
    "WalletCurrencyCpp",
    # Wallet card overrides (legacy)
    "WalletCardCredit",
    "WalletCardGroupSelection",
    "WalletCardCategoryPriority",
    "WalletCardMultiplier",
    # Wallet spend
    "WalletSpendItem",
    # Wallet portal (legacy)
    "WalletPortalShare",
    # User spend categories
    "UserSpendCategory",
    "UserSpendCategoryMapping",
]
