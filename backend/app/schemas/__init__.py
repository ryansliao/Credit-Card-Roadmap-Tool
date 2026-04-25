"""Pydantic v2 schemas for request/response validation.

Schemas are organised by domain (mirroring ``app.dal``). This package
re-exports every schema at the top level so existing ``from app.schemas
import X`` call sites continue to work.
"""

from .admin import (
    AdminAddCardMultiplierPayload,
    AdminAddRotatingHistoryPayload,
    AdminCreateCardMultiplierGroupPayload,
    AdminCreateCardPayload,
    AdminCreateCurrencyPayload,
    AdminCreateIssuerPayload,
    AdminCreateSpendCategoryPayload,
    AdminCreateTravelPortalPayload,
    AdminUpdateCardMultiplierGroupPayload,
    AdminUpdateTravelPortalPayload,
)
from .builders import wallet_read, wallet_to_schema, wc_read
from .card import (
    CardMultiplierGroupRead,
    CardMultiplierGroupSchema,
    CardMultiplierSchema,
    CardRead,
    GroupCategoryItem,
    RotatingCategoryRead,
    RotationCategoryWeight,
    UpdateCardLibraryPayload,
)
from .credit import (
    CardCreditRead,
    CreateCreditPayload,
    UpdateCreditPayload,
)
from .currency import (
    CurrencyRead,
    WalletCurrencyCppSet,
)
from .reference import (
    CoBrandRead,
    IssuerApplicationRuleRead,
    IssuerRead,
    NetworkTierRead,
)
from .results import (
    CardResultSchema,
    CategoryEarnItem,
    WalletResultResponseSchema,
    WalletResultSchema,
)
from .roadmap import (
    RoadmapCardStatus,
    RoadmapResponse,
    RoadmapRuleStatus,
)
from .spend import (
    SpendCategoryRead,
    UserSpendCategoryMappingRead,
    UserSpendCategoryRead,
    WalletSpendItemCreate,
    WalletSpendItemRead,
    WalletSpendItemUpdate,
)
from .travel_portal import (
    TravelPortalRead,
    WalletPortalSharePayload,
    WalletPortalShareRead,
)
from .wallet import (
    CreditTotalByCurrency,
    InitialWalletCardCredit,
    WalletBase,
    WalletCardBase,
    WalletCardCreate,
    WalletCardRead,
    WalletCardUpdate,
    WalletCreate,
    WalletRead,
    WalletSummary,
    WalletUpdate,
)
from .wallet_overrides import (
    WalletCardCategoryPriorityRead,
    WalletCardCategoryPrioritySet,
    WalletCardCreditRead,
    WalletCardCreditUpsert,
)
from .card_instance import (
    CardInstanceBase,
    CardInstanceRead,
    FutureCardCreate,
    FutureCardUpdate,
    OwnedCardCreate,
    OwnedCardUpdate,
)
from .scenario import (
    ScenarioBase,
    ScenarioCreate,
    ScenarioRead,
    ScenarioSummary,
    ScenarioUpdate,
)
from .scenario_currency import (
    ScenarioCurrencyBalanceRead,
    ScenarioCurrencyBalanceSet,
    ScenarioCurrencyCppRead,
    ScenarioCurrencyCppSet,
    ScenarioPortalShareRead,
    ScenarioPortalShareSet,
)
from .scenario_overlay import (
    ScenarioCardOverlayRead,
    ScenarioCardOverlayUpsert,
)
from .scenario_overrides import (
    ScenarioCardCategoryPriorityRead,
    ScenarioCardCategoryPrioritySet,
    ScenarioCardCreditRead,
    ScenarioCardCreditUpsert,
    ScenarioCardGroupSelectionRead,
    ScenarioCardGroupSelectionSet,
    ScenarioCardMultiplierRead,
    ScenarioCardMultiplierUpsert,
)

__all__ = [
    # Admin
    "AdminAddCardMultiplierPayload",
    "AdminAddRotatingHistoryPayload",
    "AdminCreateCardMultiplierGroupPayload",
    "AdminCreateCardPayload",
    "AdminCreateCurrencyPayload",
    "AdminCreateIssuerPayload",
    "AdminCreateSpendCategoryPayload",
    "AdminCreateTravelPortalPayload",
    "AdminUpdateCardMultiplierGroupPayload",
    "AdminUpdateTravelPortalPayload",
    # Builders
    "wallet_read",
    "wallet_to_schema",
    "wc_read",
    # Card
    "CardMultiplierGroupRead",
    "CardMultiplierGroupSchema",
    "CardMultiplierSchema",
    "CardRead",
    "GroupCategoryItem",
    "RotatingCategoryRead",
    "RotationCategoryWeight",
    "UpdateCardLibraryPayload",
    # Credit
    "CardCreditRead",
    "CreateCreditPayload",
    "UpdateCreditPayload",
    # Currency
    "CurrencyRead",
    "WalletCurrencyCppSet",
    # Reference
    "CoBrandRead",
    "IssuerApplicationRuleRead",
    "IssuerRead",
    "NetworkTierRead",
    # Results
    "CardResultSchema",
    "CategoryEarnItem",
    "WalletResultResponseSchema",
    "WalletResultSchema",
    # Roadmap
    "RoadmapCardStatus",
    "RoadmapResponse",
    "RoadmapRuleStatus",
    # Spend
    "SpendCategoryRead",
    "UserSpendCategoryMappingRead",
    "UserSpendCategoryRead",
    "WalletSpendItemCreate",
    "WalletSpendItemRead",
    "WalletSpendItemUpdate",
    # Travel portal
    "TravelPortalRead",
    "WalletPortalSharePayload",
    "WalletPortalShareRead",
    # Wallet
    "CreditTotalByCurrency",
    "InitialWalletCardCredit",
    "WalletBase",
    "WalletCardBase",
    "WalletCardCreate",
    "WalletCardRead",
    "WalletCardUpdate",
    "WalletCreate",
    "WalletRead",
    "WalletSummary",
    "WalletUpdate",
    # Wallet overrides
    "WalletCardCategoryPriorityRead",
    "WalletCardCategoryPrioritySet",
    "WalletCardCreditRead",
    "WalletCardCreditUpsert",
    # Card instance
    "CardInstanceBase",
    "CardInstanceRead",
    "FutureCardCreate",
    "FutureCardUpdate",
    "OwnedCardCreate",
    "OwnedCardUpdate",
    # Scenario
    "ScenarioBase",
    "ScenarioCreate",
    "ScenarioRead",
    "ScenarioSummary",
    "ScenarioUpdate",
    # Scenario currency / portal
    "ScenarioCurrencyBalanceRead",
    "ScenarioCurrencyBalanceSet",
    "ScenarioCurrencyCppRead",
    "ScenarioCurrencyCppSet",
    "ScenarioPortalShareRead",
    "ScenarioPortalShareSet",
    # Scenario overlay
    "ScenarioCardOverlayRead",
    "ScenarioCardOverlayUpsert",
    # Scenario per-card overrides
    "ScenarioCardCategoryPriorityRead",
    "ScenarioCardCategoryPrioritySet",
    "ScenarioCardCreditRead",
    "ScenarioCardCreditUpsert",
    "ScenarioCardGroupSelectionRead",
    "ScenarioCardGroupSelectionSet",
    "ScenarioCardMultiplierRead",
    "ScenarioCardMultiplierUpsert",
]
