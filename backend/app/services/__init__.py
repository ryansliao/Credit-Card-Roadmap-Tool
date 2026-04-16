"""Service layer for data access.

Services are the only components that should access the database directly.
Routers should use services for all data operations.
"""

from .base import BaseService
from .wallet_service import WalletService, get_wallet_service
from .wallet_spend_service import WalletSpendService, get_wallet_spend_service
from .wallet_currency_service import WalletCurrencyService, get_wallet_currency_service
from .wallet_card_override_service import (
    WalletCardOverrideService,
    get_wallet_card_override_service,
)
from .wallet_portal_service import WalletPortalService, get_wallet_portal_service
from .card_service import CardService, get_card_service
from .credit_service import CreditService, get_credit_service
from .spend_category_service import SpendCategoryService, get_spend_category_service
from .currency_service import CurrencyService, get_currency_service
from .issuer_service import IssuerService, get_issuer_service
from .travel_portal_service import TravelPortalService, get_travel_portal_service
from .wallet_category_priority_service import (
    WalletCategoryPriorityService,
    get_wallet_category_priority_service,
)
from .calculator_data_service import (
    CalculatorDataService,
    get_calculator_data_service,
)

__all__ = [
    "BaseService",
    "WalletService",
    "get_wallet_service",
    "WalletSpendService",
    "get_wallet_spend_service",
    "WalletCurrencyService",
    "get_wallet_currency_service",
    "WalletCardOverrideService",
    "get_wallet_card_override_service",
    "WalletPortalService",
    "get_wallet_portal_service",
    "CardService",
    "get_card_service",
    "CreditService",
    "get_credit_service",
    "SpendCategoryService",
    "get_spend_category_service",
    "CurrencyService",
    "get_currency_service",
    "IssuerService",
    "get_issuer_service",
    "TravelPortalService",
    "get_travel_portal_service",
    "WalletCategoryPriorityService",
    "get_wallet_category_priority_service",
    "CalculatorDataService",
    "get_calculator_data_service",
]
