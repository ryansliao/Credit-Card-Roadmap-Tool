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
from .builders import wallet_to_schema, wc_read
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
    InitialWalletCardCredit,
    WalletBase,
    WalletCardBase,
    WalletCardCreate,
    WalletCardRead,
    WalletCardUpdate,
    WalletRead,
    WalletUpdate,
)
from .wallet_overrides import (
    WalletCardCategoryPriorityRead,
    WalletCardCategoryPrioritySet,
    WalletCardCreditRead,
    WalletCardCreditUpsert,
    WalletCardGroupSelectionRead,
    WalletCardGroupSelectionSet,
    WalletCardMultiplierRead,
    WalletCardMultiplierUpsert,
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
    "InitialWalletCardCredit",
    "WalletBase",
    "WalletCardBase",
    "WalletCardCreate",
    "WalletCardRead",
    "WalletCardUpdate",
    "WalletRead",
    "WalletUpdate",
    # Wallet overrides
    "WalletCardCategoryPriorityRead",
    "WalletCardCategoryPrioritySet",
    "WalletCardCreditRead",
    "WalletCardCreditUpsert",
    "WalletCardGroupSelectionRead",
    "WalletCardGroupSelectionSet",
    "WalletCardMultiplierRead",
    "WalletCardMultiplierUpsert",
]
