"""Optimal per-segment allocation via scipy.linprog.

Solves one segment at a time, mutating ``cap_state`` to let downstream
segments see the remaining cap budget. Falls back to a per-card greedy via
``_segment_card_earn_pts_per_cat`` when scipy is unavailable or the LP
fails.

This module is deliberately isolated from the rest of the calculator so the
scipy dependency stays quarantined and the LP logic can be unit-tested
without pulling in the full engine.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .allocation import FOREIGN_CAT_PREFIX as _FOREIGN_CAT_PREFIX
from .currency import _comparison_cpp, _secondary_currency_comparison_bonus
from .multipliers import _all_other_multiplier, _build_effective_multipliers
from .segments import _cap_period_bounds, _segment_card_earn_pts_per_cat
from .types import CardData


def _solve_segment_allocation_lp(
    active_cards: list[CardData],
    spend: dict[str, float],
    seg_currency_ids: set[int],
    sub_priority_card_ids: set[int] | None,
    seg_days: int,
    seg_start: date,
    cap_state: dict[tuple, float],
    for_balance: bool = False,
) -> dict[int, dict[str, float]]:
    """
    Optimally allocate one segment's spend across the active cards using
    scipy.linprog. Honors:
      - per-category flow conservation (Σ_k allocated = segment_dollars)
      - pooled cap constraints on non-rotating capped groups
      - frequency-weighted allocation for rotating groups: each card can
        capture at most p_C share of category spend at the full bonus rate
      - pooled cap constraints on rotating groups (one cap per group per
        period, shared across every category in the rotating universe on
        that card)
      - SUB priority filtering (when SUB-priority cards are present, they
        are the only candidates)
      - segment-prorated cap budgets that flow forward via cap_state

    Returns ``{card_id: {category_name: segment_points_raw_currency}}``.
    Mutates cap_state to record cap consumption for downstream segments.

    Falls back to a per-card greedy via ``_segment_card_earn_pts_per_cat``
    if scipy isn't available or the LP solve fails.
    """
    if seg_days <= 0 or not active_cards:
        return {c.id: {} for c in active_cards}
    seg_years = seg_days / 365.25

    # SUB-priority filter: if any priority cards are active in this segment,
    # only they compete for category allocation. SUB priority takes precedence
    # over manual category pins since hitting minimum spend is critical.
    competing = active_cards
    if sub_priority_card_ids:
        priority = [c for c in active_cards if c.id in sub_priority_card_ids]
        if priority:
            competing = priority

    # Effective per-card multipliers and CPPs.
    card_mult: dict[int, dict[str, float]] = {}  # card_idx -> cat_lower -> mult
    card_all_other: dict[int, float] = {}
    card_cpp: dict[int, float] = {}
    for k_idx, c in enumerate(competing):
        eff_mults = _build_effective_multipliers(c, spend)
        # Lowercase keys for case-insensitive matching against spend keys
        card_mult[k_idx] = {(k or "").strip().lower(): v for k, v in eff_mults.items()}
        card_all_other[k_idx] = _all_other_multiplier(eff_mults)
        card_cpp[k_idx] = _comparison_cpp(c, seg_currency_ids, for_balance=for_balance) * c.earn_bonus_factor

    # Categories with positive segment spend.
    cat_dollars: list[tuple[str, float]] = []
    for cat, s in spend.items():
        if s > 0:
            cat_dollars.append((cat, s * seg_years))
    if not cat_dollars:
        return {c.id: {} for c in active_cards}

    # ---- Build cap constraints. ----
    # Each constraint: list of (k_idx, cat_lower) with bonus var in this row,
    # plus cap_remaining (derived from cap_state) and the state_key to update.
    @dataclass
    class _CapConstraint:
        members: list[tuple[int, str]]  # (k_idx, cat_lower) for variables in this row
        remaining: float
        state_key: tuple

    constraints: list[_CapConstraint] = []
    # Track per-(k_idx, cat_lower) the BONUS multiplier when capped, for the
    # variable's coefficient in the objective. Categories without entries here
    # only have a base variable (no bonus path).
    bonus_mult: dict[tuple[int, str], float] = {}
    # Variables that are explicitly capped — every (k_idx, cat_lower) pair
    # the LP needs a separate `b` variable for. Pairs not in this set have
    # only a base variable (their entire allocation earns at base rate).
    capped_pairs: set[tuple[int, str]] = set()
    # For each (k_idx, cat_lower) pair with a bonus path, whether the bonus
    # is additive (stacks on the always-on rate) or replacement (the legacy
    # "highest rate wins" model). Determines whether the BASE variable for
    # that pair earns at the always-on rate (additive) or at the card's All
    # Other (non-additive) — i.e., what overflow above the cap looks like.
    pair_is_additive: dict[tuple[int, str], bool] = {}
    # For rotating categories, track the frequency (activation probability).
    # Used to constrain each card's allocation to its frequency share.
    rotating_freq: dict[tuple[int, str], float] = {}

    def _bonus_rate_for_pair(
        k_idx: int, cl: str, g_mult: float, g_is_add: bool, is_rotating: bool = False
    ) -> float:
        """Effective bonus rate when this group's cap applies. For additive
        groups the premium stacks onto the always-on rate; for non-additive
        groups the group multiplier replaces the base entirely.

        For *rotating* additive groups ``card_mult`` already includes the
        premium (baked in by ``_build_effective_multipliers``), so returning
        ``card_mult`` IS the full bonus rate — adding ``g_mult`` again would
        double-count."""
        if g_is_add:
            cm = card_mult[k_idx].get(cl, card_all_other[k_idx])
            return cm if is_rotating else (cm + g_mult)
        return g_mult

    # ---- Portal premiums. ----
    # Each TravelPortal in the wallet has one share value that represents
    # "fraction of travel-coverable spend booked through this portal." The
    # cap is therefore POOLED across every card belonging to that portal —
    # the user can only book each $1 of travel through the portal once, so
    # the total bonus dollars across all member cards must respect that
    # single share × seg_dollars[cat] limit.
    #
    # `portal_buckets[(portal_id, cat_lower)] = (share, [(k_idx, premium, is_add), ...])`
    portal_buckets: dict[tuple[int, str], tuple[float, list[tuple[int, float, bool]]]] = {}
    for k_idx, c in enumerate(competing):
        if not c.portal_memberships or not c.portal_premiums:
            continue
        for portal_id, share in c.portal_memberships.items():
            if share <= 0.0:
                continue
            for cat_lower, premium, p_is_add in c.portal_premiums:
                bucket = portal_buckets.get((portal_id, cat_lower))
                if bucket is None:
                    portal_buckets[(portal_id, cat_lower)] = (
                        float(share),
                        [(k_idx, float(premium), bool(p_is_add))],
                    )
                else:
                    bucket[1].append((k_idx, float(premium), bool(p_is_add)))

    for k_idx, c in enumerate(competing):
        for (
            g_mult, g_cats, _topn, g_id,
            g_cap_amt, g_cap_months, g_is_rot, g_rot_weights, g_is_add,
        ) in c.multiplier_groups:
            if g_id is None or g_cap_amt is None or not g_cap_months or g_cap_months <= 0:
                continue
            period_start, _ = _cap_period_bounds(seg_start, g_cap_months)
            cat_lower_set = {(x or "").strip().lower() for x in g_cats}

            if g_is_rot:
                # Frequency-weighted allocation: rotating cards capture only
                # their frequency share of category spend at the FULL bonus
                # rate (not EV-blended). The frequency constraint is enforced
                # via upper bounds on the card's allocation variables. The
                # cap is **pooled** across every category in the rotating
                # group on this card per period (one constraint per group),
                # mirroring how the issuer enforces the cap on combined
                # rotating-bonus spend per quarter.
                rot_lookup = {(k or "").strip().lower(): float(v) for k, v in g_rot_weights.items()}
                state_key = ("rot", g_id, period_start)
                if state_key not in cap_state:
                    cap_state[state_key] = float(g_cap_amt)
                rot_members: list[tuple[int, str]] = []
                for cl in cat_lower_set:
                    p_c = rot_lookup.get(cl, 0.0)
                    if p_c <= 0.0:
                        # No bonus path for this category; it earns base only.
                        continue
                    # Use the FULL bonus rate since frequency is enforced via
                    # upper bounds on allocation, not via EV-blended rates.
                    active_bonus_rate = _bonus_rate_for_pair(
                        k_idx, cl, float(g_mult), g_is_add, is_rotating=True
                    )
                    bonus_mult[(k_idx, cl)] = active_bonus_rate
                    pair_is_additive[(k_idx, cl)] = g_is_add
                    capped_pairs.add((k_idx, cl))
                    rotating_freq[(k_idx, cl)] = p_c
                    rot_members.append((k_idx, cl))
                if rot_members and cap_state[state_key] > 0:
                    constraints.append(_CapConstraint(
                        members=rot_members,
                        remaining=cap_state[state_key],
                        state_key=state_key,
                    ))
            else:
                # Pooled non-rotating cap.
                state_key = ("pool", g_id, period_start)
                if state_key not in cap_state:
                    cap_state[state_key] = float(g_cap_amt)
                members = []
                ao = card_all_other[k_idx]
                for cl in cat_lower_set:
                    # For top-N groups, only categories that won the top-N
                    # selection (i.e., have a bonus mult above all_other in
                    # card_mult) get a capped bonus variable.  Non-top-N
                    # categories are already at all_other in card_mult and have
                    # no bonus path here — adding them would let the LP
                    # incorrectly exploit the cap budget on categories that
                    # should earn at 1x regardless.
                    if _topn is not None and _topn > 0:
                        if card_mult[k_idx].get(cl, ao) <= ao + 1e-9:
                            continue
                    members.append((k_idx, cl))
                    bonus_mult[(k_idx, cl)] = _bonus_rate_for_pair(k_idx, cl, float(g_mult), g_is_add)
                    pair_is_additive[(k_idx, cl)] = g_is_add
                    capped_pairs.add((k_idx, cl))
                if members and cap_state[state_key] > 0:
                    constraints.append(_CapConstraint(
                        members=members,
                        remaining=cap_state[state_key],
                        state_key=state_key,
                    ))

    # ---- Portal premium constraints (pooled per portal). ----
    for (portal_id, spec_cl), (share, members_spec) in portal_buckets.items():
        # Find the matching category (case-insensitive) in cat_dollars.
        cat_seg_dollars = 0.0
        for cat, d_c in cat_dollars:
            if cat.strip().lower() == spec_cl:
                cat_seg_dollars = d_c
                break
        if cat_seg_dollars <= 0.0 or share <= 0.0:
            continue
        portal_cap = share * cat_seg_dollars
        if portal_cap <= 0.0:
            continue
        state_key = ("portal", portal_id, spec_cl, seg_start)
        # Always re-initialize per segment (portal shares are per-quarter
        # intent, not cumulative).
        cap_state[state_key] = portal_cap
        constraint_members: list[tuple[int, str]] = []
        for spec_k_idx, spec_premium, spec_is_add in members_spec:
            # Each member gets its own bonus var with its own rate.
            rate = _bonus_rate_for_pair(spec_k_idx, spec_cl, spec_premium, spec_is_add)
            existing_bonus = bonus_mult.get((spec_k_idx, spec_cl))
            if existing_bonus is None or rate > existing_bonus:
                bonus_mult[(spec_k_idx, spec_cl)] = rate
                pair_is_additive[(spec_k_idx, spec_cl)] = spec_is_add
            capped_pairs.add((spec_k_idx, spec_cl))
            constraint_members.append((spec_k_idx, spec_cl))
        if constraint_members:
            constraints.append(
                _CapConstraint(
                    members=constraint_members,
                    remaining=portal_cap,
                    state_key=state_key,
                )
            )

    # ---- Build LP variables and matrices. ----
    # For each (k_idx, cat_idx) pair we always have a `base` variable (e).
    # If (k_idx, cat_lower) ∈ capped_pairs, we additionally have a `bonus` (b)
    # variable.
    cat_index: dict[str, int] = {cat: i for i, (cat, _) in enumerate(cat_dollars)}
    var_indices: list[tuple[str, int, int]] = []  # ("e"|"b", k_idx, cat_idx)
    var_lookup: dict[tuple[str, int, int], int] = {}

    def _add_var(kind: str, k_idx: int, cat_idx: int) -> int:
        key = (kind, k_idx, cat_idx)
        if key in var_lookup:
            return var_lookup[key]
        var_lookup[key] = len(var_indices)
        var_indices.append(key)
        return var_lookup[key]

    # Add base variables for every (k_idx, cat_idx).
    for k_idx in range(len(competing)):
        for cat, _d in cat_dollars:
            cat_idx = cat_index[cat]
            _add_var("e", k_idx, cat_idx)
    # Add bonus variables wherever the card has a real bonus path.
    for k_idx in range(len(competing)):
        ao = card_all_other[k_idx]
        for cat, _d in cat_dollars:
            cat_lower = cat.strip().lower()
            cat_idx = cat_index[cat]
            in_capped = (k_idx, cat_lower) in capped_pairs
            mult = card_mult[k_idx].get(cat_lower, ao)
            uncapped_bonus = mult > ao + 1e-9
            if in_capped or uncapped_bonus:
                _add_var("b", k_idx, cat_idx)
                # If not already set (uncapped bonus path), record the multiplier.
                if uncapped_bonus:
                    bonus_mult.setdefault((k_idx, cat_lower), mult)

    n_vars = len(var_indices)
    if n_vars == 0:
        return {c.id: {} for c in active_cards}

    # Objective coefficients: maximize Σ rate × var. linprog minimizes,
    # so we use negative coefficients.
    obj_c = [0.0] * n_vars
    for i, (kind, k_idx, cat_idx) in enumerate(var_indices):
        cat_name = cat_dollars[cat_idx][0]
        cat_lower = cat_name.strip().lower()
        cpp = card_cpp[k_idx]
        if kind == "e":
            # For non-additive capped categories the base (overflow) variable
            # earns at all_other, NOT at card_mult. Using card_mult here would
            # make the e and b variables identical in the objective so HiGHS
            # could arbitrarily split spend between them, producing a blended
            # rate somewhere between all_other and bonus_mult in the output.
            # Using all_other creates a clear gradient: LP fills b (high rate)
            # before e (low rate), which is what the cap is supposed to enforce.
            #
            # Rotating additive categories also overflow to all_other — the
            # bonus only applies when the category is the active rotating
            # quarter; the rest of the year the card earns its base rate.
            # ``card_mult`` already includes the rotating premium (baked in
            # by ``_build_effective_multipliers``), so using it here would
            # pretend the bonus is always-on.
            is_rotating_pair = (k_idx, cat_lower) in rotating_freq
            in_capped = (k_idx, cat_lower) in capped_pairs
            is_additive_pair = pair_is_additive.get((k_idx, cat_lower), True)
            if in_capped and (not is_additive_pair or is_rotating_pair):
                mult = card_all_other[k_idx]
            else:
                mult = card_mult[k_idx].get(cat_lower, card_all_other[k_idx])
        else:
            mult = bonus_mult.get((k_idx, cat_lower), card_all_other[k_idx])
        # Effective $ earned per $ spent (primary earn + secondary currency bonus).
        sec_bonus = _secondary_currency_comparison_bonus(competing[k_idx], category=cat_name, for_balance=for_balance)
        rate = mult * cpp / 100.0 + sec_bonus / 100.0
        obj_c[i] = -rate

    # Equality constraints: per category, Σ_k (e + b) = d_C
    n_cats = len(cat_dollars)
    A_eq = [[0.0] * n_vars for _ in range(n_cats)]
    b_eq = [0.0] * n_cats
    for cat_idx, (cat, d_c) in enumerate(cat_dollars):
        b_eq[cat_idx] = d_c
        for k_idx in range(len(competing)):
            i_e = var_lookup[("e", k_idx, cat_idx)]
            A_eq[cat_idx][i_e] = 1.0
            i_b = var_lookup.get(("b", k_idx, cat_idx))
            if i_b is not None:
                A_eq[cat_idx][i_b] = 1.0

    # Inequality constraints: each cap constraint sums its bonus variables.
    A_ub: list[list[float]] = []
    b_ub: list[float] = []
    for cc in constraints:
        row = [0.0] * n_vars
        any_member = False
        for (k_idx, cl) in cc.members:
            # Find the cat_idx whose lowercased name matches cl.
            cat_idx = None
            for idx, (cat, _d) in enumerate(cat_dollars):
                if cat.strip().lower() == cl:
                    cat_idx = idx
                    break
            if cat_idx is None:
                continue
            i_b = var_lookup.get(("b", k_idx, cat_idx))
            if i_b is None:
                continue
            row[i_b] = 1.0
            any_member = True
        if any_member:
            A_ub.append(row)
            b_ub.append(cc.remaining)

    # Variable bounds: 0 ≤ var ≤ d_C (a single category never receives more
    # than its own segment dollars on any one card).
    #
    # Manual category priority: for every category pinned by some competing
    # card, zero-bound the base + bonus variables for every OTHER competing
    # card on that category. This forces all of that category's segment
    # dollars onto the pinned card without breaking flow conservation (the
    # pinned card still has positive upper bounds). Note: pins only affect
    # cards in `competing` — if SUB priority filtered the pinned card out,
    # the pin has no effect and SUB cards get the spend.
    pinned_by_cat: dict[int, set[int]] = {}
    for cat, _d in cat_dollars:
        base_cat = cat[len(_FOREIGN_CAT_PREFIX):] if cat.startswith(_FOREIGN_CAT_PREFIX) else cat
        key = (base_cat or "").strip().lower()
        if not key:
            continue
        pinned_idxs = {
            k_idx for k_idx, c in enumerate(competing)
            if key in c.priority_categories
        }
        if pinned_idxs:
            pinned_by_cat[cat_index[cat]] = pinned_idxs

    bounds = []
    for kind, k_idx, cat_idx in var_indices:
        cat_name, d_c = cat_dollars[cat_idx]
        cat_lower = cat_name.strip().lower()
        pinned_set = pinned_by_cat.get(cat_idx)
        if pinned_set is not None and k_idx not in pinned_set:
            bounds.append((0.0, 0.0))
        else:
            # Per-variable upper bound caps only the individual variable at
            # d_c. The frequency share for rotating categories is applied as
            # a combined (e + b) constraint below, so the LP can't double-dip
            # by filling both the base and bonus variables up to freq × d_c
            # separately.
            bounds.append((0.0, d_c))

    # Combined (e + b) upper bound per (card, rotating category): total spend
    # allocated to this card on this category cannot exceed its frequency
    # share of the segment's category dollars. Applied as an inequality on
    # the sum of the base and bonus variables — NOT as per-variable upper
    # bounds — so the LP can freely shift between e and b under the bonus
    # cap but cannot exceed the frequency share in aggregate.
    for (k_idx, cat_lower), freq in rotating_freq.items():
        if freq >= 1.0:
            continue
        cat_idx = None
        for idx, (cat, _d) in enumerate(cat_dollars):
            if cat.strip().lower() == cat_lower:
                cat_idx = idx
                break
        if cat_idx is None:
            continue
        _cat_name, d_c = cat_dollars[cat_idx]
        row = [0.0] * n_vars
        any_member = False
        i_e = var_lookup.get(("e", k_idx, cat_idx))
        if i_e is not None:
            row[i_e] = 1.0
            any_member = True
        i_b = var_lookup.get(("b", k_idx, cat_idx))
        if i_b is not None:
            row[i_b] = 1.0
            any_member = True
        if any_member:
            A_ub.append(row)
            b_ub.append(d_c * freq)

    # Solve. Only scipy-missing (ImportError) should trigger the greedy
    # fallback silently — real solver errors indicate a bug in our LP setup
    # and must propagate so they are caught in tests / observability.
    try:
        from scipy.optimize import linprog
    except ImportError:
        import logging
        logging.getLogger(__name__).warning(
            "scipy not installed; falling back to greedy allocation. "
            "Portal and cap accuracy may be reduced."
        )
        return _greedy_segment_fallback(
            active_cards, spend, seg_currency_ids, sub_priority_card_ids,
            seg_days, seg_start, cap_state, for_balance,
        )

    # Dense matrices are fine for our small problem sizes.
    res = linprog(
        c=obj_c,
        A_ub=A_ub if A_ub else None,
        b_ub=b_ub if b_ub else None,
        A_eq=A_eq,
        b_eq=b_eq,
        bounds=bounds,
        method="highs",
    )

    if not res.success:
        return _greedy_segment_fallback(
            active_cards, spend, seg_currency_ids, sub_priority_card_ids,
            seg_days, seg_start, cap_state, for_balance,
        )

    # ---- Extract per-(card, category) bonus / base dollars from LP. ----
    alloc: dict[tuple[int, int], list[float]] = {}
    for i, (kind, k_idx, cat_idx) in enumerate(var_indices):
        x = float(res.x[i])
        if x <= 1e-12:
            continue
        slot = alloc.setdefault((k_idx, cat_idx), [0.0, 0.0])
        if kind == "b":
            slot[0] += x
        else:
            slot[1] += x

    # ---- Tie-split redistribution across cards on a single category. ----
    # The LP solver picks a degenerate vertex when multiple cards have identical
    # rates on a category, assigning all spend to one card. Detect and correct
    # this by redistributing that category's dollars evenly among tied winners,
    # matching the simple-path _tied_cards_for_category behaviour.
    for cat_idx, (cat_name, _d_c) in enumerate(cat_dollars):
        cat_lower = cat_name.strip().lower()
        card_rates: list[tuple[int, float]] = []
        for k_idx in range(len(competing)):
            cpp = card_cpp[k_idx]
            mult = card_mult[k_idx].get(cat_lower, card_all_other[k_idx])
            sec_bonus = _secondary_currency_comparison_bonus(
                competing[k_idx], category=cat_name, for_balance=for_balance
            )
            card_rates.append((k_idx, mult * cpp / 100.0 + sec_bonus / 100.0))
        if not card_rates:
            continue
        best_rate = max(r for _, r in card_rates)
        tied = [k for k, r in card_rates if abs(r - best_rate) <= 1e-9]
        if len(tied) <= 1:
            continue
        # Sum dollars allocated to tied cards only (non-tied cards at lower rates
        # should have received nothing from the LP).
        total_tied = sum(
            sum(alloc.get((k, cat_idx), [0.0, 0.0]))
            for k in tied
        )
        if total_tied <= 1e-12:
            continue
        per_card = total_tied / len(tied)
        for k in tied:
            alloc[(k, cat_idx)] = [0.0, per_card]

    # ---- Cosmetic redistribution for pooled constraints. ----
    # The LP can pick degenerate solutions when multiple categories within a
    # pooled group have identical bonus rates. The total earn is correct,
    # but the per-category split collapses onto whichever variable the
    # simplex picked first. Redistribute bonus dollars proportionally so
    # the category breakdown looks balanced.
    for cc in constraints:
        if len(cc.members) <= 1:
            continue
        members_with_idx: list[tuple[int, int, float]] = []
        total_bonus = 0.0
        total_spend = 0.0
        for (k_idx, cl) in cc.members:
            cat_idx = None
            for idx, (cat, _d) in enumerate(cat_dollars):
                if cat.strip().lower() == cl:
                    cat_idx = idx
                    break
            if cat_idx is None:
                continue
            slot = alloc.get((k_idx, cat_idx))
            if slot is None:
                continue
            members_with_idx.append((k_idx, cat_idx, slot[0] + slot[1]))
            total_bonus += slot[0]
            total_spend += slot[0] + slot[1]
        if total_bonus <= 0 or total_spend <= 0:
            continue
        for k_idx, cat_idx, cat_total in members_with_idx:
            new_bonus = total_bonus * (cat_total / total_spend)
            new_base = cat_total - new_bonus
            slot = alloc[(k_idx, cat_idx)]
            slot[0] = new_bonus
            slot[1] = new_base

    # ---- Convert to per-card per-category points. ----
    out: dict[int, dict[str, float]] = {c.id: {} for c in active_cards}
    for (k_idx, cat_idx), (b_dol, e_dol) in alloc.items():
        cat_name = cat_dollars[cat_idx][0]
        cat_lower = cat_name.strip().lower()
        # Mirror the LP objective rate logic for consistency.
        bonus_m = bonus_mult.get(
            (k_idx, cat_lower),
            card_mult[k_idx].get(cat_lower, card_all_other[k_idx]),
        )
        if pair_is_additive.get((k_idx, cat_lower), True) is False:
            base_m = card_all_other[k_idx]
        else:
            base_m = card_mult[k_idx].get(cat_lower, card_all_other[k_idx])
        pts = b_dol * bonus_m + e_dol * base_m
        if pts <= 0:
            continue
        card_id = competing[k_idx].id
        out[card_id][cat_name] = out[card_id].get(cat_name, 0.0) + pts

    # ---- Update cap_state with bonus dollars consumed by each constraint. ----
    for cc in constraints:
        consumed = 0.0
        for (k_idx, cl) in cc.members:
            cat_idx = None
            for idx, (cat, _d) in enumerate(cat_dollars):
                if cat.strip().lower() == cl:
                    cat_idx = idx
                    break
            if cat_idx is None:
                continue
            i_b = var_lookup.get(("b", k_idx, cat_idx))
            if i_b is None:
                continue
            consumed += float(res.x[i_b])
        cap_state[cc.state_key] = max(0.0, cc.remaining - consumed)

    return out


def _greedy_segment_fallback(
    active_cards: list[CardData],
    spend: dict[str, float],
    seg_currency_ids: set[int],
    sub_priority_card_ids: set[int] | None,
    seg_days: int,
    seg_start: date,
    cap_state: dict[tuple, float],
    for_balance: bool = False,
) -> dict[int, dict[str, float]]:
    """Per-card greedy fallback when scipy/LP solve fails. Uses the existing
    _segment_card_earn_pts_per_cat path for each card with a SHARED cap_state
    so per-card overflow at least respects prior consumption."""
    out: dict[int, dict[str, float]] = {}
    for c in active_cards:
        out[c.id] = _segment_card_earn_pts_per_cat(
            c, spend, active_cards, seg_currency_ids,
            sub_priority_card_ids, seg_days, seg_start, cap_state, for_balance,
        )
    return out
