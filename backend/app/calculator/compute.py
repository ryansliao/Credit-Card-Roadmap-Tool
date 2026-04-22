"""Wallet-level orchestrator.

Top-level entry point. Reads the full set of ``CardData`` + spend + window,
threads through foreign-spend splitting, transfer-enabler CPP adjustment,
segmented-vs-simple path selection, and per-card assembly into a
``WalletResult``. This module owns the foreign-spend helpers because they
are effectively private to ``compute_wallet``.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Optional

from ..constants import HOUSING_PROCESSING_FEE_PERCENT, PREFERRED_FOREIGN_NETWORKS
from .allocation import (
    FOREIGN_CAT_PREFIX,
    _effective_annual_earn_allocated,
    calc_annual_allocated_spend,
    calc_category_earn_breakdown,
)
from .credits import (
    calc_avg_spend_multiplier,
    calc_credit_valuation,
    calc_sub_extra_spend,
    calc_sub_opportunity_cost,
    calc_total_points,
)
from .currency import (
    _apply_transfer_enabler_cpp,
    _effective_currency,
    _wallet_currency_ids,
)
from .multipliers import (
    _all_other_multiplier,
    _build_effective_multipliers,
    _calc_earn_bonus_factor,
    _compute_optimal_topn_selections,
    _first_year_pct_bonus,
    _segment_earn_bonus_factor,
)
from .housing_tiered import apply_bilt_2_housing_mode
from .secondary import _average_annual_net_dollars, _calc_secondary_currency
from .segment_lp import _solve_segment_allocation_lp
from .segmented_ev import _segmented_card_net_per_year
from .segments import (
    _build_segments,
    _segmented_category_earn_breakdown,
    _sub_priority_ids_for_segment,
)
from .types import CardData, CardResult, WalletResult


def _split_spend_for_foreign(
    cards: list[CardData],
    selected_ids: set[int],
    spend: dict[str, float],
    foreign_spend_pct: float,
    foreign_eligible_categories: set[str] | None = None,
) -> tuple[list[CardData], dict[str, float]]:
    """
    Split each spend category into a domestic portion and a foreign portion.

    The foreign portion is given a unique key prefix (``__foreign__``) so the
    existing allocation logic treats it as a separate category. Each card's
    multipliers dict is augmented with an explicit entry for every foreign
    category, computed as:

      - 0 (effectively excluded) if the card has FTF and any selected no-FTF
        card exists, OR if the card is not on a preferred network and any
        selected no-FTF Visa/Mastercard exists.
      - Otherwise: max(card's category multiplier, card's "Foreign Transactions"
        multiplier) — so a card like Summit with 3x Foreign Transactions still
        earns its base 3x Dining on foreign Dining (no double-up), but earns
        3x on foreign Groceries (replacing 1x All Other).

    ``foreign_eligible_categories``: when provided (case-insensitive name set),
    only spend categories in the set are split into a foreign bucket. US-only
    recurring categories (Phone, Internet, Streaming, Amazon, …) are passed
    through untouched so the wallet-level foreign percentage doesn't bleed into
    spend that can't physically be foreign. When ``None`` every category is
    split (legacy behaviour).
    """
    if foreign_spend_pct <= 0:
        return cards, spend
    frac = max(0.0, min(1.0, foreign_spend_pct / 100.0))
    if frac <= 0:
        return cards, spend

    selected = [c for c in cards if c.id in selected_ids]
    has_no_ftf = any(not c.has_foreign_transaction_fee for c in selected)
    has_no_ftf_visa_mc = any(
        (not c.has_foreign_transaction_fee)
        and c.network_name in PREFERRED_FOREIGN_NETWORKS
        for c in selected
    )

    eligible_lower: set[str] | None
    if foreign_eligible_categories is None:
        eligible_lower = None
    else:
        eligible_lower = {
            (c or "").strip().lower() for c in foreign_eligible_categories
        }

    def _is_foreign_eligible(cat: str) -> bool:
        if eligible_lower is None:
            return True
        return (cat or "").strip().lower() in eligible_lower

    # Build modified spend dict with split categories
    new_spend: dict[str, float] = {}
    foreign_keys: dict[str, str] = {}  # category -> foreign key
    for cat, amt in spend.items():
        if amt > 0 and _is_foreign_eligible(cat):
            new_spend[cat] = amt * (1 - frac)
            fk = f"{FOREIGN_CAT_PREFIX}{cat}"
            new_spend[fk] = amt * frac
            foreign_keys[cat] = fk
        else:
            new_spend[cat] = amt

    # Build modified card list with explicit foreign multipliers per category
    new_cards: list[CardData] = []
    for card in cards:
        # Eligibility for foreign spend allocation:
        # - If any no-FTF card exists, FTF cards are excluded
        # - If any no-FTF Visa/MC card exists, non-Visa/MC cards are excluded
        eligible = True
        if has_no_ftf and card.has_foreign_transaction_fee:
            eligible = False
        elif has_no_ftf_visa_mc and (
            not card.network_name or card.network_name not in PREFERRED_FOREIGN_NETWORKS
        ):
            eligible = False

        # The "foreign rate" any selected card uses on a foreign category C is
        # max(its multiplier on C, its Foreign Transactions multiplier).
        foreign_base = card.foreign_multiplier_bonus  # from "Foreign Transactions"
        # Compute the card's All Other rate (used as fallback for categories
        # not explicitly in the multipliers dict).
        ao_rate = _all_other_multiplier(card.multipliers)

        new_mults = dict(card.multipliers)
        for orig_cat, fk in foreign_keys.items():
            if not eligible:
                new_mults[fk] = 0.0
                continue
            # Effective per-category rate: explicit if present, else All Other
            cat_rate = card.multipliers.get(orig_cat, ao_rate)
            # Case-insensitive lookup fallback
            if orig_cat not in card.multipliers:
                for k, v in card.multipliers.items():
                    if k.strip().lower() == orig_cat.strip().lower():
                        cat_rate = v
                        break
            new_mults[fk] = max(cat_rate, foreign_base)

        new_cards.append(replace(card, multipliers=new_mults))

    return new_cards, new_spend


def _merge_foreign_breakdown(
    breakdown: list[tuple[str, float]],
) -> list[tuple[str, float]]:
    """Combine ``__foreign__X`` entries back into ``X`` for display."""
    merged: dict[str, float] = {}
    order: list[str] = []
    for label, pts in breakdown:
        if label.startswith(FOREIGN_CAT_PREFIX):
            base = label[len(FOREIGN_CAT_PREFIX):]
        else:
            base = label
        if base not in merged:
            merged[base] = 0.0
            order.append(base)
        merged[base] += pts
    out = [(name, round(merged[name], 2)) for name in order if merged[name] > 0]
    out.sort(key=lambda x: x[1], reverse=True)
    return out


def compute_wallet(
    all_cards: list[CardData],
    selected_ids: set[int],
    spend: dict[str, float],
    years: int,
    window_start: Optional[date] = None,
    window_end: Optional[date] = None,
    sub_priority_card_ids: set[int] | None = None,
    housing_category_names: set[str] | None = None,
    foreign_spend_pct: float = 0.0,
    foreign_eligible_categories: set[str] | None = None,
    include_subs: bool = True,
) -> WalletResult:
    """
    Compute results for every card in `all_cards`.
    Only cards with id in `selected_ids` contribute to totals and currency points.

    window_start / window_end: when provided and any selected card has date info,
    the earn calculation is time-weighted across segments based on card open/close
    and SUB earn boundaries (per-day optimisation).

    foreign_eligible_categories: names (case-insensitive) of spend categories
    that can plausibly have foreign spend. Only these are split into a foreign
    bucket by the wallet-level ``foreign_spend_pct``; everything else stays
    100% domestic. Pass ``None`` to split every category (legacy behaviour).

    include_subs: wallet-wide toggle for whether Sign Up Bonuses contribute to
    effective annual fee. When False, the SUB bonus, sub_spend_earn,
    sub_cash, sub_secondary_points, and SUB opportunity cost are stripped
    from the EAF dollar formula on both the simple and segmented paths. The
    toggle intentionally leaves allocation, SUB-window priority routing, and
    per-card recurring income (``annual_point_earn``) untouched — those
    reflect the wallet's earning behaviour, which does not change just
    because the user wants to exclude welcome offers from EAF. Balances
    (``total_points`` / ``currency_pts``) and manually tracked
    WalletCurrencyBalance rows are also unaffected.
    """
    selected_cards = [c for c in all_cards if c.id in selected_ids]

    # Foreign spend: split each category into a domestic and a foreign portion,
    # injecting per-card "foreign category" multipliers that account for
    # FTF priority filtering (no-FTF cards win all foreign spend if any exist;
    # no-FTF Visa/MC win over no-FTF other networks).
    all_cards, spend = _split_spend_for_foreign(
        all_cards, selected_ids, spend, foreign_spend_pct,
        foreign_eligible_categories=foreign_eligible_categories,
    )
    selected_cards = [c for c in all_cards if c.id in selected_ids]

    # Adjust CPP for currencies that lack a transfer enabler in the wallet.
    all_cards = _apply_transfer_enabler_cpp(all_cards, selected_cards)
    selected_cards = [c for c in all_cards if c.id in selected_ids]

    # Apply earn_bonus_factor for percentage-based annual bonuses.
    # This factor is used by allocation scoring so cards with bonuses compete
    # at their effective earn rate. For the simple path, first-year-only bonuses
    # use an amortised factor; the segmented path overrides per-segment below.
    all_cards = [
        replace(c, earn_bonus_factor=_calc_earn_bonus_factor(c, years))
        if c.annual_bonus_percent else c
        for c in all_cards
    ]
    selected_cards = [c for c in all_cards if c.id in selected_ids]

    active_wallet_currency_ids = _wallet_currency_ids(selected_cards)

    # Pre-compute optimal top-N category selections for cards with selectable
    # bonus groups. Uses incremental value (opportunity cost) to pick the
    # categories where the bonus provides the most gain over alternatives.
    all_cards = _compute_optimal_topn_selections(
        all_cards, selected_ids, spend, active_wallet_currency_ids
    )
    selected_cards = [c for c in all_cards if c.id in selected_ids]

    # Compute total housing spend for secondary currency conversion cap.
    # When foreign spend split is in effect, housing categories may exist as both
    # "Rent" and "__foreign__Rent" entries; both contribute to total housing.
    _housing_names = housing_category_names or set()
    _housing_lower = {n.lower() for n in _housing_names}
    def _is_housing(cat: str) -> bool:
        base = cat[len(FOREIGN_CAT_PREFIX):] if cat.startswith(FOREIGN_CAT_PREFIX) else cat
        return base.lower() in _housing_lower
    housing_spend_total = sum(
        s for cat, s in spend.items() if _is_housing(cat) and s > 0
    )
    # Total non-housing spend in the wallet — used to scale secondary-currency
    # allocation scoring when a card's convertibility cap would bind.
    total_non_housing_spend = sum(
        s for cat, s in spend.items() if not _is_housing(cat) and s > 0
    )

    # Bilt 2.0: for cards with the tiered-housing option enabled, pick
    # whichever of (tiered housing multiplier) or (Bilt Cash secondary earn)
    # yields higher dollar value, and patch the card's multipliers /
    # secondary-currency fields before the main compute pipeline runs.
    all_cards = apply_bilt_2_housing_mode(
        all_cards,
        selected_ids,
        spend,
        active_wallet_currency_ids,
        housing_spend_total,
        _housing_names,
        FOREIGN_CAT_PREFIX,
    )
    selected_cards = [c for c in all_cards if c.id in selected_ids]

    # Housing processing fee: cards without housing_fee_waived incur a ~3%
    # payment platform fee when used for rent/mortgage.  Reduce their housing
    # category multipliers so allocation and earn reflect the net value after
    # the fee.  The penalty in multiplier units is fee% / (CPP/100) — e.g. at
    # 2.0 cpp the 3% fee costs 1.5x worth of points per dollar.
    if housing_spend_total > 0 and _housing_names:
        fee_rate = HOUSING_PROCESSING_FEE_PERCENT / 100.0  # 0.03
        any_waived = any(
            c.housing_fee_waived for c in selected_cards
        )
        if any_waived:
            new_cards: list[CardData] = []
            for c in all_cards:
                if c.housing_fee_waived or c.id not in selected_ids:
                    new_cards.append(c)
                    continue
                eff_cur = _effective_currency(c, active_wallet_currency_ids)
                cpp = eff_cur.cents_per_point
                if cpp <= 0:
                    new_cards.append(c)
                    continue
                fee_mult_penalty = fee_rate / (cpp / 100.0)
                new_mults = dict(c.multipliers)
                changed = False
                for name in _housing_names:
                    for key in (name, f"{FOREIGN_CAT_PREFIX}{name}"):
                        if key in new_mults:
                            new_mults[key] = max(0.0, new_mults[key] - fee_mult_penalty)
                            changed = True
                        else:
                            # Category falls through to All Other; apply penalty
                            ao = _all_other_multiplier(new_mults)
                            new_mults[key] = max(0.0, ao - fee_mult_penalty)
                            changed = True
                if changed:
                    new_cards.append(replace(c, multipliers=new_mults))
                else:
                    new_cards.append(c)
            all_cards = new_cards
            selected_cards = [c for c in all_cards if c.id in selected_ids]

    # Secondary-currency scoring adjustment for cards with a cap_rate > 0.
    # Without this the LP sees e.g. Bilt's full 4% Bilt Cash bonus on every
    # dollar and over-allocates bonus categories (Dining, Groceries) to Bilt,
    # even though the $0.75 × housing cap limits how much of that bonus is
    # actually redeemable.
    def _scoring_factor(c: CardData) -> float:
        if c.secondary_currency is None or c.secondary_currency_cap_rate <= 0:
            return 1.0
        if housing_spend_total <= 0:
            return 0.0  # fully blocked
        if total_non_housing_spend <= 0:
            return 1.0
        cap = c.secondary_currency_cap_rate * housing_spend_total
        if cap >= total_non_housing_spend:
            return 1.0  # cap never binds
        # Cap binds across the wallet — blend the rate so the marginal
        # dollar's secondary earn reflects the average effective rate.
        return cap / total_non_housing_spend

    all_cards = [
        replace(c, secondary_scoring_factor=_scoring_factor(c))
        if c.secondary_currency is not None and c.secondary_currency_cap_rate > 0
        else c
        for c in all_cards
    ]
    selected_cards = [c for c in all_cards if c.id in selected_ids]

    # Use segmented calculation when window dates are available and either:
    #   (a) any card has date context (open/close), or
    #   (b) any card has a capped multiplier group — caps need per-period
    #       segmentation to enforce, so the simple path can't model them.
    def _has_capped_group(c: CardData) -> bool:
        if any(
            cap_amt is not None and cap_months and cap_months > 0
            for _m, _cats, _topn, _gid, cap_amt, cap_months, _is_rot, _rot_weights, _is_add in c.multiplier_groups
        ):
            return True
        # A card with portal premiums and a non-zero portal share also needs
        # the segmented LP path so the per-segment portal cap can apply.
        if c.portal_share > 0.0 and c.portal_premiums:
            return True
        return False

    use_segmentation = (
        window_start is not None
        and window_end is not None
        and (
            any(
                c.wallet_added_date is not None or c.wallet_closed_date is not None
                for c in selected_cards
            )
            or any(_has_capped_group(c) for c in selected_cards)
        )
    )

    # When the segmented path is in play, pre-solve the optimal cross-card
    # allocation for every segment ONCE — both for wallet-CPP scoring (used
    # by EV) and balance-CPP scoring (used by point totals). Each card then
    # reads its own allocation out of the cache. cap_state mutates forward
    # in time as segments consume cap budgets within the same period.
    seg_alloc_cache: list[dict[int, dict[str, float]]] | None = None
    seg_alloc_cache_balance: list[dict[int, dict[str, float]]] | None = None
    if use_segmentation and window_start is not None and window_end is not None:
        segments_for_cache = _build_segments(window_start, window_end, selected_cards)
        seg_alloc_cache = []
        seg_alloc_cache_balance = []
        cap_state_lp: dict[tuple, float] = {}
        cap_state_lp_balance: dict[tuple, float] = {}
        # Any first-year-only bonus cards need per-segment factor overrides so
        # the LP allocates categories correctly during vs. after the match year.
        has_fy_bonus = any(c.annual_bonus_percent and c.annual_bonus_first_year_only for c in selected_cards)
        for seg_start, seg_end, active in segments_for_cache:
            seg_days = (seg_end - seg_start).days
            # Override earn_bonus_factor per-segment for first-year-only cards.
            if has_fy_bonus:
                active = [
                    replace(c, earn_bonus_factor=_segment_earn_bonus_factor(c, seg_start))
                    if c.annual_bonus_percent and c.annual_bonus_first_year_only else c
                    for c in active
                ]
            seg_currency_ids = {c.currency.id for c in active}
            sub_prio = _sub_priority_ids_for_segment(active, seg_start, spend, seg_currency_ids)
            seg_alloc_cache.append(
                _solve_segment_allocation_lp(
                    active, spend, seg_currency_ids, sub_prio,
                    seg_days, seg_start, cap_state_lp, for_balance=False,
                )
            )
            seg_alloc_cache_balance.append(
                _solve_segment_allocation_lp(
                    active, spend, seg_currency_ids, sub_prio,
                    seg_days, seg_start, cap_state_lp_balance, for_balance=True,
                )
            )

    card_results: list[CardResult] = []

    for card in all_cards:
        selected = card.id in selected_ids

        if not selected:
            card_results.append(
                CardResult(
                    card_id=card.id,
                    card_name=card.name,
                    selected=False,
                    annual_fee=card.annual_fee,
                    first_year_fee=card.first_year_fee,
                    sub_points=card.sub_points,
                    cents_per_point=card.currency.cents_per_point,
                    effective_currency_name=card.currency.name,
                    effective_currency_id=card.currency.id,
                    effective_reward_kind=card.currency.reward_kind,
                    effective_currency_photo_slug=card.currency.photo_slug,
                )
            )
            continue

        eff_currency = _effective_currency(card, active_wallet_currency_ids)

        # Card's own active duration in years within the wallet window.
        if use_segmentation and window_start is not None and window_end is not None:
            _card_start = max(card.wallet_added_date or window_start, window_start)
            _card_end = min(card.wallet_closed_date or window_end, window_end)
            _card_active_days = max(0, (_card_end - _card_start).days)
            card_active_years = max(_card_active_days / 365.25, 1 / 12)
        else:
            card_active_years = float(years)

        if use_segmentation:
            net_annual, annual_point_earn, annual_point_earn_for_balance = _segmented_card_net_per_year(
                card, selected_cards, spend,
                window_start, window_end,  # type: ignore[arg-type]
                precomputed_seg_alloc=seg_alloc_cache,
                precomputed_seg_alloc_balance=seg_alloc_cache_balance,
                housing_spend=housing_spend_total,
                include_subs=include_subs,
            )
            effective_annual_fee = round(-net_annual, 4)
            # Per-card EAF: re-annualize using the card's own active years.
            # net_annual = total_net / wallet_years, so total_net = net_annual * wallet_years.
            total_years_window = (window_end - window_start).days / 365.25  # type: ignore[operator]
            card_net_annual = net_annual * total_years_window / card_active_years
            card_effective_annual_fee = round(-card_net_annual, 4)
            # total_points: the displayed "annual point income" multiplied by
            # the card's active years in the window, plus one-time SUB. This
            # is what the user reads as "balance": a card earning X/year and
            # active for Y years shows a balance of X*Y, so a card active
            # less than a year shows a balance less than X. We use the
            # balance-view earn here (default CPP allocation) so wallet CPP
            # overrides don't skew the point totals.
            sub_earnable_pts = card.sub_points if card.sub_earnable else 0
            total_points = annual_point_earn_for_balance * card_active_years + sub_earnable_pts
        else:
            # Simple path has no time windowing, so the SUB priority boost
            # (which only applies during a card's SUB window) is meaningless
            # here. Passing it would redirect the full year's spend to the
            # priority card while `calc_total_points` still adds
            # `sub_spend_earn` on top, double-counting SUB-window earn.
            annual_point_earn = _effective_annual_earn_allocated(
                card, spend, selected_cards, active_wallet_currency_ids,
            )
            annual_point_earn_for_balance = _effective_annual_earn_allocated(
                card, spend, selected_cards, active_wallet_currency_ids,
                for_balance=True,
            )
            net_annual = _average_annual_net_dollars(
                card, spend, years, active_wallet_currency_ids, selected_cards,
                precomputed_earn=annual_point_earn,
                housing_spend=housing_spend_total,
                include_subs=include_subs,
            )
            effective_annual_fee = round(-net_annual, 4)
            card_effective_annual_fee = effective_annual_fee
            total_points = calc_total_points(
                card, selected_cards, spend, years, active_wallet_currency_ids,
                precomputed_earn=annual_point_earn_for_balance,
            )
        credit_val = calc_credit_valuation(card)
        sub_extra = calc_sub_extra_spend(card, spend, selected_cards, active_wallet_currency_ids)
        if include_subs:
            gross_opp, net_opp = calc_sub_opportunity_cost(card, selected_cards, spend, active_wallet_currency_ids)
        else:
            gross_opp, net_opp = 0.0, 0.0
        avg_mult = calc_avg_spend_multiplier(card, spend)
        if use_segmentation:
            # Time-weighted breakdown: reads from the same per-segment LP cache
            # the EV path used so categories match annual_point_earn exactly.
            cat_earn = _segmented_category_earn_breakdown(
                card, selected_cards, spend, window_start, window_end,  # type: ignore[arg-type]
                precomputed_seg_alloc=seg_alloc_cache,
            )
        else:
            cat_earn = calc_category_earn_breakdown(
                card, selected_cards, spend, active_wallet_currency_ids,
            )
            # sub_spend_earn is a separate one-time contribution not captured in annual_point_earn
            # on the simple path; add it explicitly. On the segmented path it is already embedded
            # in segment earn via SUB priority allocation.
            if card.sub_earnable and card.sub_spend_earn > 0:
                cat_earn = list(cat_earn) + [("SUB Spend", float(card.sub_spend_earn))]
                cat_earn.sort(key=lambda x: x[1], reverse=True)
        # First-year-only percentage bonus shown as a separate line item in the breakdown.
        if card.annual_bonus_percent and card.annual_bonus_first_year_only:
            cat_pts_for_fy = sum(pts for label, pts in cat_earn
                                if label not in ("Annual Bonus", "SUB Spend"))
            fy_bonus = _first_year_pct_bonus(card, cat_pts_for_fy)
            if fy_bonus > 0:
                cat_earn = list(cat_earn) + [(f"First Year Match ({card.annual_bonus_percent:g}%)", round(fy_bonus, 2))]
                cat_earn.sort(key=lambda x: x[1], reverse=True)

        # Merge any "__foreign__X" entries back into "X" for display
        if foreign_spend_pct > 0:
            cat_earn = _merge_foreign_breakdown(cat_earn)

        # Effective multiplier per category for the UI (top-N + manual group
        # selections applied). Strip __foreign__ variants so the map is keyed
        # by user-facing spend category names only.
        cat_mults_raw = _build_effective_multipliers(card, spend)
        category_multipliers = {
            k: round(v, 4)
            for k, v in cat_mults_raw.items()
            if not k.startswith(FOREIGN_CAT_PREFIX)
        }

        # Surface only the SUB values that were actually counted in totals.
        # When sub_earnable is False (e.g. in-wallet cards whose SUB is historical
        # or cards the user can't reach the min spend on), the calculator already
        # excluded these from total_points and effective_annual_fee — reporting
        # the raw library values here would let the UI double-subtract them.
        reported_sub = card.sub_points if card.sub_earnable else 0
        reported_sub_spend_earn = card.sub_spend_earn if card.sub_earnable else 0

        # Secondary currency result for this card. Exclude categories the
        # card marks as ineligible for secondary earn (e.g. Bilt 2.0 in Bilt
        # Cash mode excludes Rent/Mortgage).
        sec_alloc = calc_annual_allocated_spend(
            card, selected_cards, spend, active_wallet_currency_ids,
            exclude_categories=card.secondary_ineligible_categories or None,
        )
        sec = _calc_secondary_currency(card, sec_alloc, active_wallet_currency_ids, housing_spend=housing_spend_total)
        sec_cur_name = card.secondary_currency.name if card.secondary_currency else ""
        sec_cur_id = card.secondary_currency.id if card.secondary_currency else 0
        # Total secondary pts over the projection window
        sec_gross_total = sec.gross_annual_pts * years
        sec_net_total = sec.net_annual_pts * years
        sec_cost_total = sec.cost_pts_annual * years
        sec_bonus_total = sec.bonus_pts_annual * years
        # Off-band redemptions (set by ``apply_bilt_2_housing_mode`` in Bilt
        # Cash mode): Tier 1 BC consumed by the housing-payment → BP
        # conversion + BC spent on Point Accelerator activations. Subtracted
        # from the displayed balance so the UI reflects what's actually left
        # after those redemptions fire. ``_calc_secondary_currency`` can't
        # see these because the card is patched to ``accelerator_cost=0``
        # (the BP benefit is already in ``annual_bonus``).
        sec_consumption_total = card.secondary_consumption_pts * years
        sec_gross_total -= sec_consumption_total
        sec_net_total -= sec_consumption_total
        # One-time SUB in the secondary currency (e.g. Bilt Cash welcome offer)
        # — rolls into the balance once (not multiplied by years). Honors the
        # housing cap: if the cap blocks conversion, the SUB is still added to
        # the pts balance (you hold the Bilt Cash) but its dollar value is 0.
        if card.sub_earnable and card.sub_secondary_points > 0 and card.secondary_currency is not None:
            sec_gross_total += card.sub_secondary_points
            sec_net_total += card.sub_secondary_points

        card_results.append(
            CardResult(
                card_id=card.id,
                card_name=card.name,
                selected=True,
                effective_annual_fee=effective_annual_fee,
                card_effective_annual_fee=card_effective_annual_fee,
                card_active_years=round(card_active_years, 4),
                total_points=round(total_points, 2),
                annual_point_earn=round(annual_point_earn, 2),
                credit_valuation=round(credit_val, 2),
                annual_fee=card.annual_fee,
                first_year_fee=card.first_year_fee,
                sub_points=reported_sub,
                annual_bonus=card.annual_bonus,
                annual_bonus_percent=card.annual_bonus_percent,
                annual_bonus_first_year_only=card.annual_bonus_first_year_only,
                sub_extra_spend=round(sub_extra, 2),
                sub_spend_earn=reported_sub_spend_earn,
                sub_opp_cost_dollars=net_opp,
                sub_opp_cost_gross_dollars=gross_opp,
                avg_spend_multiplier=round(avg_mult, 4),
                cents_per_point=eff_currency.cents_per_point,
                effective_currency_name=eff_currency.name,
                effective_currency_id=eff_currency.id,
                effective_reward_kind=eff_currency.reward_kind,
                effective_currency_photo_slug=eff_currency.photo_slug,
                category_earn=cat_earn,
                category_multipliers=category_multipliers,
                secondary_currency_earn=round(sec_gross_total, 2),
                secondary_currency_name=sec_cur_name,
                secondary_currency_id=sec_cur_id,
                accelerator_activations=sec.activations,
                accelerator_bonus_points=round(sec_bonus_total, 2),
                accelerator_cost_points=round(sec_cost_total, 2),
                secondary_currency_net_earn=round(sec_net_total, 2),
                secondary_currency_value_dollars=round(sec.dollar_value_annual * years, 2),
            )
        )

    selected_results = [r for r in card_results if r.selected]
    total_effective_annual_fee = round(
        sum(r.effective_annual_fee for r in selected_results), 4
    )
    points_only = [r for r in selected_results if r.effective_reward_kind != "cash"]
    cash_only = [r for r in selected_results if r.effective_reward_kind == "cash"]
    total_points_earned = round(sum(r.total_points for r in points_only), 2)
    total_annual_pts = round(sum(r.annual_point_earn for r in points_only), 2)
    total_cash_reward_dollars = round(
        sum(r.total_points * r.cents_per_point / 100.0 for r in cash_only), 4
    )
    total_reward_value_usd = round(
        sum(r.total_points * r.cents_per_point / 100.0 for r in selected_results), 4
    )

    # Total raw points over the projection period, by effective currency (spend + SUB + bonuses)
    currency_pts: dict[str, float] = {}
    currency_pts_by_id: dict[int, float] = {}
    for r in selected_results:
        name = (r.effective_currency_name or "").strip()
        if name:
            currency_pts[name] = currency_pts.get(name, 0.0) + r.total_points
        cid = r.effective_currency_id
        if cid:
            currency_pts_by_id[cid] = currency_pts_by_id.get(cid, 0.0) + r.total_points
    currency_pts = {k: round(v, 2) for k, v in currency_pts.items()}
    currency_pts_by_id = {k: round(v, 2) for k, v in currency_pts_by_id.items()}

    # Secondary currency totals (e.g. Bilt Cash across all cards)
    secondary_currency_pts: dict[str, float] = {}
    secondary_currency_pts_by_id: dict[int, float] = {}
    for r in selected_results:
        if r.secondary_currency_id and r.secondary_currency_net_earn:
            name = (r.secondary_currency_name or "").strip()
            if name:
                secondary_currency_pts[name] = secondary_currency_pts.get(name, 0.0) + r.secondary_currency_net_earn
            secondary_currency_pts_by_id[r.secondary_currency_id] = (
                secondary_currency_pts_by_id.get(r.secondary_currency_id, 0.0) + r.secondary_currency_net_earn
            )
    secondary_currency_pts = {k: round(v, 2) for k, v in secondary_currency_pts.items()}
    secondary_currency_pts_by_id = {k: round(v, 2) for k, v in secondary_currency_pts_by_id.items()}

    return WalletResult(
        years_counted=years,
        total_effective_annual_fee=total_effective_annual_fee,
        total_points_earned=total_points_earned,
        total_annual_pts=total_annual_pts,
        total_cash_reward_dollars=total_cash_reward_dollars,
        total_reward_value_usd=total_reward_value_usd,
        currency_pts=currency_pts,
        currency_pts_by_id=currency_pts_by_id,
        secondary_currency_pts=secondary_currency_pts,
        secondary_currency_pts_by_id=secondary_currency_pts_by_id,
        card_results=card_results,
    )
