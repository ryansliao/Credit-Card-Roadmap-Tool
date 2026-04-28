"""Roadmap status schemas (5/24, SUB status, issuer rule violations)."""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel


class RoadmapCardStatus(BaseModel):
    wallet_card_id: int
    card_id: int
    card_name: str
    issuer_name: str
    is_business: bool
    added_date: date
    closed_date: Optional[date] = None
    is_active: bool
    sub_projected_earn_date: Optional[date] = None
    # "no_sub" | "pending" | "earned" | "expired"
    sub_status: str
    sub_window_end: Optional[date] = None
    next_sub_eligible_date: Optional[date] = None
    # Days remaining in SUB window (positive = still open, None = no window)
    sub_days_remaining: Optional[int] = None


class RuleAtRiskInterval(BaseModel):
    # Half-open interval [start, end): the rule's count is >= max_count
    # from `start` (inclusive) until `end` (exclusive — count drops below
    # max on this date). Already clipped to start from `as_of_date`.
    start: date
    end: date


class RoadmapRuleStatus(BaseModel):
    rule_id: int
    rule_name: str
    issuer_name: Optional[str]
    description: Optional[str]
    max_count: int
    period_days: int
    current_count: int
    is_violated: bool
    personal_only: bool
    scope_all_issuers: bool
    # Cards counted toward this rule (names)
    counted_cards: list[str] = []
    # Date intervals across the projection where count >= max_count. A
    # single rule can be at risk multiple times as cards are added and
    # roll off the rolling window.
    at_risk_intervals: list[RuleAtRiskInterval] = []


class RoadmapResponse(BaseModel):
    wallet_id: int
    wallet_name: str
    as_of_date: date
    # 5/24 and general stats
    five_twenty_four_count: int
    five_twenty_four_eligible: bool
    personal_cards_24mo: list[str] = []
    # Per-rule violation checks
    rule_statuses: list[RoadmapRuleStatus] = []
    # Per-card status
    cards: list[RoadmapCardStatus] = []
