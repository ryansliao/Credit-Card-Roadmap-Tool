"""
Shared constants used across backend modules.
"""

# Single-tenant: all user data belongs to this user.
DEFAULT_USER_ID: int = 1

# The "catch-all" spend category name used both as a SpendCategory row
# and as the reserved UserSpendCategory that cannot be renamed or deleted.
ALL_OTHER_CATEGORY: str = "All Other"

# Tolerance for allocation sum validation (allows for floating-point rounding).
ALLOCATION_SUM_TOLERANCE: float = 0.01

# Typical foreign transaction fee percentage charged by issuers (e.g. 3%).
FOREIGN_TRANSACTION_FEE_PERCENT: float = 3.0

# Network names considered preferred for foreign spend (no-FTF tier).
PREFERRED_FOREIGN_NETWORKS: frozenset[str] = frozenset({"Visa", "Mastercard"})
