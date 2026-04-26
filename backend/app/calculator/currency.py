"""Currency helpers: CPP, transfer enablement, effective currency selection.

Pure functions over ``CardData`` / ``CurrencyData``. No DB dependency.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Optional

from .types import CardData, CurrencyData


def _wallet_currency_ids(selected_cards: list[CardData]) -> set[int]:
    """IDs of all currencies directly earned by selected cards."""
    return {c.currency.id for c in selected_cards}


def _transfer_enabled_currency_ids(selected_cards: list[CardData]) -> set[int]:
    """IDs of currencies that have a transfer enabler card in the wallet."""
    return {c.currency.id for c in selected_cards if c.transfer_enabler}


def _enabler_model_currency_ids(all_cards: list[CardData]) -> set[int]:
    """IDs of currencies that use the transfer-enabler model.

    A currency uses the enabler model if any card in the library is marked as a
    transfer enabler for it. These currencies fall back to a reduced CPP (rate,
    fixed, or cash) when no enabler is present in the wallet.
    """
    return {c.currency.id for c in all_cards if c.transfer_enabler}


def _adjust_currency_for_transfer(
    cur: CurrencyData,
    transfer_enabled: set[int],
    uses_enabler_model: set[int],
) -> CurrencyData:
    """Return a CurrencyData copy with CPP reduced when no transfer enabler is present.

    When no transfer enabler exists in the wallet, the CPP falls back to the *higher*
    (better) of two options:
    - **Reduced transfer**: a partial transfer access that still beats cash, expressed
      either as ``no_transfer_rate`` (multiplier on the current CPP, e.g. 0.7 for Citi
      without Strata Premier) or ``no_transfer_cpp`` (fixed fallback, e.g. 1.0).
    - **Cash redemption**: ``cash_transfer_rate`` is the cents-per-point achievable by
      cashing out (e.g. 1.0 for Chase UR portal, 0.5 for Capital One cash erase).

    The two are computed independently and the larger value is used. If neither is
    set, the CPP is unchanged.
    """
    new_converts = None
    if cur.converts_to_currency is not None:
        new_converts = _adjust_currency_for_transfer(
            cur.converts_to_currency, transfer_enabled, uses_enabler_model
        )

    has_enabler = cur.id in transfer_enabled
    # A currency uses the enabler model if any card in the library is marked as
    # a transfer enabler for it. Such currencies fall back to a reduced CPP when
    # no enabler is present in the wallet.
    is_enabler_model = cur.id in uses_enabler_model
    if (has_enabler or not is_enabler_model) and new_converts is None:
        return cur

    new_cpp: Optional[float] = None
    new_comparison: Optional[float] = None

    if not has_enabler and is_enabler_model:
        # Build candidate CPPs from each available fallback mechanism, then take
        # the highest (best) value the user could realize without an enabler card.
        candidates_cpp: list[float] = []
        candidates_comparison: list[float] = []

        if cur.no_transfer_rate is not None:
            candidates_cpp.append(cur.cents_per_point * cur.no_transfer_rate)
            candidates_comparison.append(cur.comparison_cpp * cur.no_transfer_rate)
        elif cur.no_transfer_cpp is not None:
            candidates_cpp.append(cur.no_transfer_cpp)
            candidates_comparison.append(cur.no_transfer_cpp)

        # cash_transfer_rate is the cents-per-point you'd get by cashing out.
        if cur.cash_transfer_rate is not None:
            candidates_cpp.append(cur.cash_transfer_rate)
            candidates_comparison.append(cur.cash_transfer_rate)

        best_cpp = max(candidates_cpp)
        best_comparison = max(candidates_comparison)
        # Only adjust if the fallback is actually a reduction.
        if best_cpp < cur.cents_per_point:
            new_cpp = best_cpp
        if best_comparison < cur.comparison_cpp:
            new_comparison = best_comparison

    if new_cpp is None and new_comparison is None and new_converts is None:
        return cur

    kwargs: dict = {}
    if new_converts is not None:
        kwargs["converts_to_currency"] = new_converts
    if new_cpp is not None:
        kwargs["cents_per_point"] = new_cpp
    if new_comparison is not None:
        kwargs["comparison_cpp"] = new_comparison
    return replace(cur, **kwargs)


def _apply_transfer_enabler_cpp(
    cards: list[CardData],
    selected_cards: list[CardData],
    uses_enabler_model: set[int] | None = None,
) -> list[CardData]:
    """Return card copies with CPP adjusted when no transfer enabler is present.

    A currency uses the transfer-enabler model if any card in the library is
    marked as ``transfer_enabler``. For such currencies, when no enabler is in
    the selected wallet, the CPP falls back to the best available reduction:
    ``no_transfer_rate`` (rate-based), ``no_transfer_cpp`` (fixed), and/or
    ``cash_transfer_rate`` (cash-out value) — whichever is highest.

    ``uses_enabler_model`` should be precomputed from the full card library by
    the caller. When ``None``, falls back to deriving it from ``cards``, which
    is only correct when ``cards`` actually IS the full library (e.g.
    self-contained calculator tests). Production callers pass the wallet's
    resolved instances as ``cards`` and must supply this set explicitly.
    """
    transfer_enabled = _transfer_enabled_currency_ids(selected_cards)
    if uses_enabler_model is None:
        uses_enabler_model = _enabler_model_currency_ids(cards)
    return [
        replace(
            card,
            currency=_adjust_currency_for_transfer(
                card.currency, transfer_enabled, uses_enabler_model
            ),
        )
        for card in cards
    ]


def _effective_currency(card: CardData, wallet_currency_ids: set[int]) -> CurrencyData:
    """
    Return the currency this card actually earns given the wallet state.
    When this card's currency has a converts_to_currency and the target
    currency is earned directly by any card in the wallet, use the target.
    """
    cur = card.currency
    if cur.converts_to_currency and cur.converts_to_currency.id in wallet_currency_ids:
        return cur.converts_to_currency
    return cur


def _comparison_cpp(card: CardData, wallet_currency_ids: set[int], for_balance: bool = False) -> float:
    """
    CPP used when comparing cards for category allocation.
    Cash should always compete at face value: 1 cent per point/unit.

    The ``for_balance`` flag is retained for call-site clarity, but ``comparison_cpp``
    now mirrors the wallet-overridden ``cents_per_point`` so balance/total-points views
    use the same wallet CPP as the EV view.
    """
    eff = _effective_currency(card, wallet_currency_ids)
    if for_balance:
        return 1.0 if eff.reward_kind == "cash" else eff.comparison_cpp
    return 1.0 if eff.reward_kind == "cash" else eff.cents_per_point


def _conversion_rate(card: CardData, wallet_currency_ids: set[int]) -> float:
    """Multiplier from card's currency to effective currency (1.0 or converts_at_rate when upgraded)."""
    eff = _effective_currency(card, wallet_currency_ids)
    return card.currency.converts_at_rate if eff.id != card.currency.id else 1.0


def _secondary_currency_comparison_bonus(
    card: CardData,
    category: str = "",
    for_balance: bool = False,
) -> float:
    """
    Cents-per-dollar bonus from the secondary currency for allocation scoring.

    Returns the additional value (in cents) that each dollar spent on this card
    generates via the secondary currency. This is added to the primary
    ``multiplier × CPP`` score so allocation accounts for the secondary earn.

    The value is scaled by ``card.secondary_scoring_factor``, which accounts
    for the convertibility cap (cap_rate × housing_spend) so cards like Bilt
    don't get credited with the full 4% bonus on every dollar when only a
    portion of their winnings can actually convert to value.

    When ``category`` is in ``card.secondary_ineligible_categories`` the bonus
    is zero — e.g. Bilt 2.0 in Bilt Cash mode earns nothing on Rent/Mortgage.
    """
    if card.secondary_currency is None or card.secondary_currency_rate <= 0:
        return 0.0
    if category and card.secondary_ineligible_categories:
        if category.lower() in card.secondary_ineligible_categories:
            return 0.0
    sec = card.secondary_currency
    # secondary_currency_rate is a fraction (e.g. 0.04 for 4%). One
    # secondary-currency unit is valued at ``cents_per_point`` cents, so
    # rate × cpp gives the bonus cents earned per dollar of spend.
    if sec.converts_to_currency:
        target_cpp = sec.converts_to_currency.comparison_cpp if for_balance else sec.converts_to_currency.cents_per_point
        return card.secondary_currency_rate * sec.converts_at_rate * target_cpp * card.secondary_scoring_factor
    cpp = sec.comparison_cpp if for_balance else sec.cents_per_point
    return card.secondary_currency_rate * cpp * card.secondary_scoring_factor
