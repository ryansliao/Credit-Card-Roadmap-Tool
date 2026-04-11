"""Credit card value calculation engine.

This subpackage replaced the legacy single-file ``calculator.py``. The
topical modules are:

- ``types`` — dataclasses (CardData, CardResult, WalletResult, …)
- ``multipliers`` — per-category multiplier lookup + percentage bonus factors
- ``currency`` — CPP, transfer enablement, effective currency selection
- ``allocation`` — simple-path winner-takes-category allocation
- ``credits`` — credit valuation, SUB opp cost, total-points
- ``secondary`` — Bilt-style secondary currency + simple-path EV formula
- ``sub_planner`` — EDF SUB scheduling with EV-aware category split
- ``segments`` — segment builder + per-card per-segment earn
- ``segment_lp`` — scipy LP solver + greedy fallback
- ``segmented_ev`` — time-weighted per-card net value orchestrator
- ``compute`` — top-level ``compute_wallet`` + foreign-spend split

External code should import the public surface via ``from app.calculator
import X``; the internal module layout is deliberately opaque.
"""
from .allocation import calc_annual_allocated_spend, calc_annual_point_earn
from .compute import FOREIGN_CAT_PREFIX, compute_wallet
from .sub_planner import plan_sub_targeting
from .types import (
    CardData,
    CardResult,
    CreditLine,
    CurrencyData,
    SubCardSchedule,
    SubSpendPlan,
    WalletResult,
)

__all__ = [
    "CardData",
    "CardResult",
    "CreditLine",
    "CurrencyData",
    "FOREIGN_CAT_PREFIX",
    "SubCardSchedule",
    "SubSpendPlan",
    "WalletResult",
    "calc_annual_allocated_spend",
    "calc_annual_point_earn",
    "compute_wallet",
    "plan_sub_targeting",
]
