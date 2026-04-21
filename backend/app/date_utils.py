"""Shared date utility functions.

Pure, DB-free helpers for date arithmetic and SUB-window math.
"""

from __future__ import annotations

import math
from calendar import monthrange
from datetime import date, timedelta
from typing import Optional


def add_months(d: date, months: int) -> date:
    """Add N months to a date, clamping to end of month as needed."""
    month = d.month + months
    year = d.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    day = min(d.day, monthrange(year, month)[1])
    return date(year, month, day)


def is_sub_earnable(
    sub_min_spend: Optional[int],
    sub_months: Optional[int],
    daily_spend_rate: float,
) -> bool:
    """Return True if the SUB min spend can be reached within the SUB window."""
    if not sub_min_spend:
        return True
    if daily_spend_rate <= 0:
        return False
    if not sub_months:
        return True
    reachable = daily_spend_rate * (sub_months * 30.44)
    return reachable >= sub_min_spend


def projected_sub_earn_date(
    added_date: date,
    sub_min_spend: Optional[int],
    sub_months: Optional[int],
    daily_spend_rate: float,
) -> Optional[date]:
    """Project the date when the SUB will be earned based on daily spend rate."""
    if not sub_min_spend or daily_spend_rate <= 0:
        return None
    days_to_earn = math.ceil(sub_min_spend / daily_spend_rate)
    # Guard against overflow (max ~3650000 days until year 9999)
    if days_to_earn > 3650000:
        return None
    projected = added_date + timedelta(days=days_to_earn)
    if sub_months:
        window_end = add_months(added_date, sub_months)
        if projected > window_end:
            return None
    return projected


def months_in_half_open_interval(start: date, end: date) -> int:
    """Number of full calendar months spanned by [start, end).

    Returns 0 for intervals shorter than one month. Callers that need a
    minimum of one year should funnel the result through
    ``years_counted_from_total_months``, which already floors at 1.
    """
    if end <= start:
        raise ValueError("end must be after start")
    total = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        total -= 1
    return max(0, total)


def years_counted_from_total_months(total_months: int) -> int:
    full = total_months // 12
    rem = total_months % 12
    return max(1, full + (1 if rem >= 6 else 0))
