"""Shared date utility functions."""

from calendar import monthrange
from datetime import date


def add_months(d: date, months: int) -> date:
    """Add N months to a date, clamping to end of month as needed."""
    month = d.month + months
    year = d.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    day = min(d.day, monthrange(year, month)[1])
    return date(year, month, day)
