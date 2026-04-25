"""Service layer for data access.

Services are the only components that should access the database directly.
Routers should use services for all data operations.
"""

from .base import BaseService
from .wallet_service import WalletService, get_wallet_service
from .wallet_spend_service import WalletSpendService, get_wallet_spend_service
from .card_service import CardService, get_card_service
from .credit_service import CreditService, get_credit_service
from .spend_category_service import SpendCategoryService, get_spend_category_service
from .user_spend_category_service import (
    UserSpendCategoryService,
    get_user_spend_category_service,
)
from .currency_service import CurrencyService, get_currency_service
from .issuer_service import IssuerService, get_issuer_service
from .travel_portal_service import TravelPortalService, get_travel_portal_service
from .calculator_data_service import (
    CalculatorDataService,
    get_calculator_data_service,
)
from .scenario_service import ScenarioService, get_scenario_service
from .card_instance_service import (
    CardInstanceService,
    get_card_instance_service,
)
from .scenario_overlay_service import (
    ScenarioCardOverlayService,
    get_scenario_card_overlay_service,
)
from .scenario_card_override_service import (
    ScenarioCardCreditService,
    ScenarioCardGroupSelectionService,
    ScenarioCardMultiplierService,
    ScenarioCategoryPriorityService,
    get_scenario_card_credit_service,
    get_scenario_card_group_selection_service,
    get_scenario_card_multiplier_service,
    get_scenario_category_priority_service,
)
from .scenario_currency_service import (
    ScenarioCurrencyService,
    get_scenario_currency_service,
)
from .scenario_portal_service import (
    ScenarioPortalService,
    get_scenario_portal_service,
)
from .scenario_resolver import (
    ComputeInputs,
    ResolvedInstance,
    ScenarioResolver,
    get_scenario_resolver,
)

__all__ = [
    "BaseService",
    "WalletService",
    "get_wallet_service",
    "WalletSpendService",
    "get_wallet_spend_service",
    "CardService",
    "get_card_service",
    "CreditService",
    "get_credit_service",
    "SpendCategoryService",
    "get_spend_category_service",
    "UserSpendCategoryService",
    "get_user_spend_category_service",
    "CurrencyService",
    "get_currency_service",
    "IssuerService",
    "get_issuer_service",
    "TravelPortalService",
    "get_travel_portal_service",
    "CalculatorDataService",
    "get_calculator_data_service",
    # Scenario services
    "ScenarioService",
    "get_scenario_service",
    "CardInstanceService",
    "get_card_instance_service",
    "ScenarioCardOverlayService",
    "get_scenario_card_overlay_service",
    "ScenarioCardCreditService",
    "get_scenario_card_credit_service",
    "ScenarioCardGroupSelectionService",
    "get_scenario_card_group_selection_service",
    "ScenarioCardMultiplierService",
    "get_scenario_card_multiplier_service",
    "ScenarioCategoryPriorityService",
    "get_scenario_category_priority_service",
    "ScenarioCurrencyService",
    "get_scenario_currency_service",
    "ScenarioPortalService",
    "get_scenario_portal_service",
    "ComputeInputs",
    "ResolvedInstance",
    "ScenarioResolver",
    "get_scenario_resolver",
]
