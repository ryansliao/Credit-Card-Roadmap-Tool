"""Pure CardData transforms: apply wallet-level overrides to calculator inputs.

These functions sit between :class:`CalculatorDataService` (which loads
ORM data) and :mod:`app.calculator` (which consumes ``CardData``). None of
them touch the database — they take already-loaded ORM rows and produce
modified :class:`CardData` copies.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from .calculator import CardData, CreditLine
from .models import (
    WalletCardCredit,
    WalletCardMultiplier,
)

if TYPE_CHECKING:
    from .models import WalletCard


def apply_wallet_card_overrides(
    card_data_list: list[CardData],
    wallet_cards: list["WalletCard"],
    wallet_credit_rows: dict[int, list[WalletCardCredit]] | None = None,
    cpp_overrides: dict[int, float] | None = None,
    currency_defaults: dict[int, float] | None = None,
    currency_kinds: dict[int, str] | None = None,
) -> list[CardData]:
    """
    Return CardData copies with wallet-level overrides: SUB fields, fees, statement credits.
    Null wallet fields keep the library Card value.

    Statement credits live exclusively on wallet cards: each WalletCardCredit row
    (joined to its Credit library entry) becomes one CreditLine on the
    resulting CardData. wallet_credit_rows: dict keyed by wallet_card_id.

    For point-based credits (point_value + credit_currency_id set on the library
    credit), the dollar value is computed as ``point_value * cpp / 100`` using the
    wallet CPP override or the currency's default CPP.
    """
    wc_by_card_id: dict[int, "WalletCard"] = {wc.card_id: wc for wc in wallet_cards}
    rows_by_wc_id: dict[int, list[WalletCardCredit]] = wallet_credit_rows or {}

    out: list[CardData] = []
    for cd in card_data_list:
        wc = wc_by_card_id.get(cd.id)
        if not wc:
            out.append(cd)
            continue

        annual_fee = (
            wc.annual_fee if wc.annual_fee is not None else cd.annual_fee
        )
        first_year_fee = (
            wc.first_year_fee if wc.first_year_fee is not None else cd.first_year_fee
        )

        merged_lines: list[CreditLine] = []
        _cpp = cpp_overrides or {}
        _cur_defaults = currency_defaults or {}
        _kinds = currency_kinds or {}
        for row in rows_by_wc_id.get(wc.id, []):
            lib_credit = row.library_credit
            if lib_credit is None:
                continue
            # wallet_card_credits.value is stored in the credit's native
            # currency (dollars for Cash, points for points currencies).
            # Resolve to dollars here using the wallet's CPP.
            dollar_value = row.value
            cur_id = lib_credit.credit_currency_id
            if cur_id is not None and _kinds.get(cur_id) != "cash":
                cpp = _cpp.get(cur_id) or _cur_defaults.get(cur_id, 1.0)
                dollar_value = row.value * cpp / 100.0
            merged_lines.append(
                CreditLine(
                    library_credit_id=row.library_credit_id,
                    name=lib_credit.credit_name,
                    value=dollar_value,
                    excludes_first_year=lib_credit.excludes_first_year,
                    is_one_time=lib_credit.is_one_time,
                )
            )

        out.append(
            dataclasses.replace(
                cd,
                sub_points=wc.sub_points if wc.sub_points is not None else cd.sub_points,
                sub_min_spend=(
                    wc.sub_min_spend
                    if wc.sub_min_spend is not None
                    else cd.sub_min_spend
                ),
                sub_months=(
                    wc.sub_months if wc.sub_months is not None else cd.sub_months
                ),
                sub_spend_earn=(
                    wc.sub_spend_earn
                    if wc.sub_spend_earn is not None
                    else cd.sub_spend_earn
                ),
                annual_bonus=(
                    wc.annual_bonus if wc.annual_bonus is not None else cd.annual_bonus
                ),
                annual_bonus_percent=(
                    wc.annual_bonus_percent if wc.annual_bonus_percent is not None else cd.annual_bonus_percent
                ),
                annual_bonus_first_year_only=(
                    wc.annual_bonus_first_year_only if wc.annual_bonus_first_year_only is not None else cd.annual_bonus_first_year_only
                ),
                annual_fee=annual_fee,
                first_year_fee=first_year_fee,
                credit_lines=merged_lines,
                secondary_currency_rate=(
                    wc.secondary_currency_rate
                    if wc.secondary_currency_rate is not None
                    else cd.secondary_currency_rate
                ),
                wallet_added_date=wc.added_date,
                wallet_closed_date=wc.closed_date,
                sub_projected_earn_date=wc.sub_projected_earn_date,
            )
        )
    return out


def apply_wallet_card_multiplier_overrides(
    card_data_list: list[CardData],
    wallet_multipliers: list[WalletCardMultiplier],
) -> list[CardData]:
    """
    Return CardData copies with wallet-level multiplier overrides applied.
    For each WalletCardMultiplier row, patches card_data.multipliers[category] = override_multiplier.
    Applied before the calculator runs, so top-N group logic sees the patched values.
    """
    if not wallet_multipliers:
        return card_data_list

    # Build lookup: card_id -> {category_name: multiplier}
    overrides_by_card: dict[int, dict[str, float]] = {}
    for wm in wallet_multipliers:
        cat = wm.category
        if cat:
            overrides_by_card.setdefault(wm.card_id, {})[cat] = wm.multiplier

    out: list[CardData] = []
    for cd in card_data_list:
        card_overrides = overrides_by_card.get(cd.id)
        if not card_overrides:
            out.append(cd)
            continue
        patched_multipliers = dict(cd.multipliers)
        patched_multipliers.update(card_overrides)
        out.append(dataclasses.replace(cd, multipliers=patched_multipliers))
    return out


def apply_wallet_card_category_priorities(
    card_data_list: list[CardData],
    priorities_by_card: dict[int, frozenset[str]],
) -> list[CardData]:
    """
    Return CardData copies with ``priority_categories`` populated from the
    wallet's manual pin overrides.
    """
    if not priorities_by_card:
        return card_data_list
    out: list[CardData] = []
    for cd in card_data_list:
        pins = priorities_by_card.get(cd.id)
        if not pins:
            out.append(cd)
            continue
        out.append(dataclasses.replace(cd, priority_categories=pins))
    return out


def apply_wallet_portal_shares(
    card_data_list: list[CardData],
    shares_by_portal: dict[int, float],
    card_ids_by_portal: dict[int, set[int]],
) -> list[CardData]:
    """
    Return CardData copies with `portal_share` and `portal_memberships` set
    from the wallet's per-portal shares.

    `portal_memberships` is a `{portal_id: share}` dict listing every portal
    this card belongs to (with a positive share). The LP uses this to build
    pooled portal-cap constraints so cards sharing a portal share one cap
    instead of stacking caps independently.

    `portal_share` is the maximum share across the card's portals — used by
    the legacy greedy path and as a quick "is the card portal-eligible at all"
    flag.
    """
    if not shares_by_portal or not card_data_list:
        return card_data_list
    # Invert: card_id -> {portal_id: share} for portals with a positive share.
    memberships_by_card: dict[int, dict[int, float]] = {}
    for portal_id, share in shares_by_portal.items():
        if share <= 0.0:
            continue
        for cid in card_ids_by_portal.get(portal_id, ()):
            memberships_by_card.setdefault(cid, {})[portal_id] = share
    if not memberships_by_card:
        return card_data_list
    out: list[CardData] = []
    for cd in card_data_list:
        memberships = memberships_by_card.get(cd.id)
        if not memberships:
            out.append(cd)
            continue
        out.append(
            dataclasses.replace(
                cd,
                portal_share=max(memberships.values()),
                portal_memberships=dict(memberships),
            )
        )
    return out
