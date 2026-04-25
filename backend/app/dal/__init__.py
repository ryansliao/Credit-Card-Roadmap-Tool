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
from .wallet import Wallet
from .wallet_spend import WalletSpendItem
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
    "WalletSpendItem",
    "UserSpendCategory",
    "UserSpendCategoryMapping",
]
