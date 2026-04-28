"""Bilt 2.0 housing mechanic.

A card with ``housing_tiered_enabled=True`` offers two mutually exclusive
earning modes per cardholder. ``apply_bilt_2_housing_mode`` evaluates both
for every tiered card, picks whichever produces higher dollar value, and
patches the card's effective multipliers / ``annual_bonus`` before the main
compute pipeline runs.

**Tiered housing mode** — points directly on Rent/Mortgage at 0.5x–1.25x
scaled by the non-housing/housing spend ratio on the card, with a flat
250 pts/month floor (3,000/yr). No secondary-currency earn.

Tier table (ratio = non_housing_allocated_to_card / total_housing_spend):

    <25%  → 0x   (+ 3000 pt/yr floor)
    <50%  → 0.5x
    <75%  → 0.75x
    <100% → 1.0x
    ≥100% → 1.25x

**Bilt Cash mode** — housing spend earns 1 BP per dollar (locked) and
non-housing spend earns the card's base multiplier plus 4% Bilt Cash. BC is
then consumed at the housing-payment redemption (1 BC = $1; $30 BC unlocks
1,000 locked BP) so the previously-locked housing BP convert to redeemable.
Beyond what's needed to unlock all housing BP, excess BC funds the Point
Accelerator.

The locked → unlocked conversion is modeled by attributing the realized
unlock value back to **housing** (not to non-housing): the patched housing
multiplier is the per-dollar realized unlock rate, and the Point
Accelerator bonus is the only piece kept as a lump-sum ``annual_bonus``.

Three conceptual tiers of non-housing spend:

    Tier 1 — first ``0.75 × housing`` non-housing dollars:
        BC earned here is fully consumed by the housing redemption. Each
        Tier 1 BC dollar unlocks ``1000/30 = 33.33`` locked housing BP.
        At the cap, Tier 1 BC = ``housing × secondary_rate × cap_rate``
        unlocks exactly ``housing × 1`` BP — the entire locked pool.
    Tier 2 — next ``max_activations × spend_limit`` non-housing dollars:
        Funds Point Accelerator activations. Each activation: pay
        ``accelerator_cost`` BC, earn ``accelerator_bonus_multiplier × spend_limit``
        bonus BP. (Palladium: $200 BC for +1,000 BP per $1,000 of spend.)
    Tier 3 — remaining non-housing dollars:
        Base category multiplier only. The 4% BC earned here has no
        modeled redemption path beyond housing/accelerator and is held as
        a tracked balance (no realized dollar value).

Housing categories on the patched card are pinned to Bilt via
``priority_categories`` so the user's housing spend actually flows to the
Bilt card in allocation — the unlock mechanic only fires when housing is
paid through the Bilt portal, so allocation must reflect that constraint.

The non-housing estimate used by the tier math is the card's baseline
category allocation under each candidate (Tiered / Bilt Cash) — neither
path's parameters leak into the other's comparison.
"""
from __future__ import annotations

from dataclasses import replace

from .allocation import _tied_cards_for_category
from .types import CardData

# (upper_bound_exclusive, multiplier)
_TIER_TABLE: list[tuple[float, float]] = [
    (0.25, 0.0),
    (0.50, 0.5),
    (0.75, 0.75),
    (1.00, 1.0),
]
_TOP_MULTIPLIER = 1.25
MONTHLY_FLOOR_PTS = 250
ANNUAL_FLOOR_PTS = MONTHLY_FLOOR_PTS * 12  # 3000

# Bilt Cash → Bilt Points conversion rate for the housing-payment redemption
# path. $30 of Bilt Cash unlocks 1,000 Bilt Points, so each Bilt Cash dollar
# converts to 1000/30 = 33.33 BP.
_BILT_CASH_DOLLARS_TO_POINTS = 1000.0 / 30.0


def tiered_housing_multiplier(ratio: float) -> float:
    """Look up the housing multiplier for a non-housing/housing ratio."""
    for upper, mult in _TIER_TABLE:
        if ratio < upper:
            return mult
    return _TOP_MULTIPLIER


def _non_housing_allocated_to_card(
    card: CardData,
    selected_cards: list[CardData],
    spend: dict[str, float],
    wallet_currency_ids: set[int],
    housing_names_lower: set[str],
    foreign_prefix: str,
) -> float:
    """Non-housing dollars allocated to ``card`` under standard category
    allocation. Mirrors ``calc_annual_allocated_spend`` but skips housing
    categories (both plain and ``__foreign__`` variants)."""
    def _is_housing(cat: str) -> bool:
        base = cat[len(foreign_prefix):] if cat.startswith(foreign_prefix) else cat
        return base.lower() in housing_names_lower

    if len(selected_cards) <= 1:
        return sum(s for cat, s in spend.items() if s > 0 and not _is_housing(cat))
    total = 0.0
    for cat, s in spend.items():
        if s <= 0 or _is_housing(cat):
            continue
        tied = _tied_cards_for_category(selected_cards, spend, cat, wallet_currency_ids)
        if not tied or card.id not in {c.id for c in tied}:
            continue
        total += s / len(tied)
    return total


def _bilt_cash_mode_bonus_bp(
    card: CardData,
    non_housing: float,
    housing_spend_total: float,
) -> tuple[float, float, float, float, float, float]:
    """Compute the BP each tier of the Bilt Cash mode produces.

    Returns ``(tier1_spend, tier2_spend, tier3_spend, tier1_bonus_bp,
    tier2_bonus_bp, bilt_cash_consumed)``.

    ``tier1_bonus_bp`` is the **unlocked housing BP** — locked housing
    points (earned at 1x on Rent/Mortgage) that get redeemed via the
    Bilt Cash → Bilt Points conversion at housing-payment time. At the cap
    this equals ``housing_spend_total × 1`` (the full locked pool); below
    the cap it's the partial unlock allowed by the BC the user earns. The
    caller attributes this back to the housing categories.

    ``tier2_bonus_bp`` is the Point Accelerator bonus — extra BP earned on
    Tier 2 spend by activating the accelerator. The caller folds this into
    ``annual_bonus`` since it isn't tied to a specific category.

    ``bilt_cash_consumed`` is the annual Bilt Cash spent to *unlock* those
    BP: Tier 1 BC consumed at the housing-payment redemption, plus BC
    spent on accelerator activations. Subtracted from the card's displayed
    Bilt Cash balance so the UI shows what's actually left.
    """
    rate = card.secondary_currency_rate or 0.0
    cap_rate = card.secondary_currency_cap_rate or 0.0
    bonus_bc = float(card.secondary_currency_annual_bonus or 0)

    # Tier 1: first ``cap_rate × housing_spend`` dollars of non-housing spend
    # redeemed via the housing-payment path. BC earned on this spend, plus any
    # annual BC bonus, is consumed by the redemption — capped at the locked
    # housing pool (``housing_spend_total`` BP @ 33.33 BP/BC). Once the pool
    # is fully unlocked, leftover bonus BC flows to the accelerator budget
    # rather than overflowing the unlock.
    tier1_cap = cap_rate * housing_spend_total if cap_rate > 0 else 0.0
    tier1_spend = min(non_housing, tier1_cap)
    tier1_bc_from_spend = rate * tier1_spend
    locked_pool_bc = housing_spend_total / _BILT_CASH_DOLLARS_TO_POINTS
    bonus_bc_for_unlock = max(
        0.0, min(bonus_bc, locked_pool_bc - tier1_bc_from_spend)
    )
    tier1_bc_consumed = tier1_bc_from_spend + bonus_bc_for_unlock
    bonus_bc_remaining = bonus_bc - bonus_bc_for_unlock

    # Tier 2: Point Accelerator activations. Each activation costs
    # ``accelerator_cost`` BC for a bonus on ``accelerator_spend_limit``
    # dollars of spend. Activations are capped by three independent limits:
    # max/year, spend available (after Tier 1), and *BC budget* — the BC
    # earned on Tier 2 + Tier 3 spend plus any annual BC bonus left over
    # after Tier 1 unlock. The BC budget cap prevents assuming more
    # activations than the user's BC inflow funds.
    accelerator_available = (
        card.accelerator_cost > 0
        and card.accelerator_spend_limit > 0
        and card.accelerator_bonus_multiplier > 0
        and card.accelerator_max_activations > 0
    )
    remaining_spend = max(0.0, non_housing - tier1_spend)
    if accelerator_available:
        max_by_year = card.accelerator_max_activations
        max_by_spend = int(remaining_spend / card.accelerator_spend_limit)
        # BC available for activations = BC earned on non-Tier-1 spend
        # + leftover annual bonus BC. Each activation costs ``accelerator_cost`` BC.
        available_bc = rate * remaining_spend + bonus_bc_remaining
        max_by_bc = int(available_bc / card.accelerator_cost)
        activations = min(max_by_year, max_by_spend, max_by_bc)
    else:
        activations = 0

    tier2_spend = activations * card.accelerator_spend_limit if accelerator_available else 0.0
    tier3_spend = max(0.0, remaining_spend - tier2_spend)
    activation_bc_consumed = activations * card.accelerator_cost

    # Tier 1 bonus: each Bilt Cash dollar converts to (1000/30) BP via the
    # housing-payment redemption — so ``tier1_bc_consumed × (1000/30)`` is
    # the count of locked housing BP that get unlocked. At the unlock cap
    # this equals ``housing_spend_total × 1``.
    tier1_bonus_bp = tier1_bc_consumed * _BILT_CASH_DOLLARS_TO_POINTS

    # Tier 2 bonus: accelerator adds ``bonus_multiplier`` BP per dollar on the
    # covered spend. ``tier2_spend`` already reflects the BC-budget cap, so
    # this can't overstate the bonus relative to funded activations.
    tier2_bonus_bp = tier2_spend * card.accelerator_bonus_multiplier

    bilt_cash_consumed = tier1_bc_consumed + activation_bc_consumed

    return (
        tier1_spend,
        tier2_spend,
        tier3_spend,
        tier1_bonus_bp,
        tier2_bonus_bp,
        bilt_cash_consumed,
    )


def _build_tiered_mode_card(
    card: CardData,
    tier_mult: float,
    floor_bonus_pts: float,
    housing_category_names: set[str],
    foreign_prefix: str,
) -> CardData:
    """Patch a card into Tiered housing mode: Rent/Mortgage earn at
    ``tier_mult``, the 250 pts/mo floor is added as ``annual_bonus``, and
    every Bilt Cash / accelerator field is disabled."""
    new_mults = dict(card.multipliers)
    for name in housing_category_names:
        new_mults[name] = tier_mult
        new_mults[f"{foreign_prefix}{name}"] = tier_mult
    return replace(
        card,
        multipliers=new_mults,
        annual_bonus=card.annual_bonus + int(round(floor_bonus_pts)),
        secondary_currency=None,
        secondary_currency_rate=0.0,
        secondary_currency_cap_rate=0.0,
        accelerator_cost=0,
        accelerator_spend_limit=0.0,
        accelerator_bonus_multiplier=0.0,
        accelerator_max_activations=0,
        secondary_ineligible_categories=frozenset(),
    )


def _build_bilt_cash_mode_card(
    card: CardData,
    tier1_bonus_bp: float,
    tier2_bonus_bp: float,
    bilt_cash_consumed: float,
    housing_spend_total: float,
    housing_category_names: set[str],
    foreign_prefix: str,
) -> CardData:
    """Patch a card into Bilt Cash mode.

    The locked → unlocked conversion is attributed to housing: each housing
    dollar earns ``tier1_bonus_bp / housing_spend_total`` BP (the per-dollar
    realized unlock rate, ≤ 1.0 — equals 1.0 when BC fully covers the
    locked pool, fractional when BC runs out before all locked BP unlock).
    Housing categories are pinned to Bilt via ``priority_categories`` so the
    user's housing spend actually flows here in allocation — the unlock
    mechanic only fires when housing is paid through the Bilt portal.

    Only the **Point Accelerator** bonus (``tier2_bonus_bp``) is folded
    into ``annual_bonus`` as a lump sum, since it isn't tied to a specific
    category.

    Bilt Cash is kept on the card as a **display-only balance** — its
    per-point dollar value is forced to 0 so the flat-rate
    secondary-currency pipeline doesn't double-count on top of the
    re-attributed housing earn we just patched in. The Bilt Cash gross
    earn still flows into ``CardResult.secondary_currency_earn`` so the UI
    can show "$X earned in Bilt Cash" as a tracker; subtracting
    ``secondary_consumption_pts`` from that gross gives the BC remaining
    after Tier 1 unlock + accelerator activations.
    """
    new_mults = dict(card.multipliers)
    if housing_spend_total > 0:
        # Re-attribute the unlock value to housing categories. With no
        # housing spend, leave the native multipliers in place so the card
        # still shows its library Rent/Mortgage rate (e.g. 1× BP for
        # Palladium) — there's nothing to unlock, but Top-ROS / display
        # logic shouldn't see a 0× housing rate that doesn't exist.
        unlock_per_housing_dollar = tier1_bonus_bp / housing_spend_total
        for name in housing_category_names:
            new_mults[name] = unlock_per_housing_dollar
            new_mults[f"{foreign_prefix}{name}"] = unlock_per_housing_dollar
    # Pin housing to this card so allocation routes the housing dollars
    # here. ``priority_categories`` is matched lowercase (with the foreign
    # prefix stripped) — see ``_category_priority_cards``.
    pinned = set(card.priority_categories)
    for name in housing_category_names:
        pinned.add(name.lower())
    ineligible = frozenset(
        v
        for name in housing_category_names
        for v in (name.lower(), f"{foreign_prefix}{name}".lower())
    )
    # Shadow copy of the Bilt Cash currency with zero value so the gross-pts
    # tracker keeps working but both the scoring bonus and the per-year
    # dollar valuation evaluate to 0.
    display_currency = card.secondary_currency
    if display_currency is not None:
        display_currency = replace(
            display_currency,
            cents_per_point=0.0,
            comparison_cpp=0.0,
        )
    return replace(
        card,
        multipliers=new_mults,
        annual_bonus=card.annual_bonus + int(round(tier2_bonus_bp)),
        secondary_currency=display_currency,
        secondary_currency_cap_rate=0.0,
        accelerator_cost=0,
        accelerator_spend_limit=0.0,
        accelerator_bonus_multiplier=0.0,
        accelerator_max_activations=0,
        secondary_ineligible_categories=ineligible,
        secondary_consumption_pts=bilt_cash_consumed,
        priority_categories=frozenset(pinned),
    )


def apply_bilt_2_housing_mode(
    cards: list[CardData],
    selected_ids: set[int],
    spend: dict[str, float],
    wallet_currency_ids: set[int],
    housing_spend_total: float,
    housing_category_names: set[str],
    foreign_prefix: str,
) -> list[CardData]:
    """Patch each ``housing_tiered_enabled`` card into its best-EV mode.

    The tiered-housing path and the Bilt-Cash path are evaluated as
    completely isolated candidate card states:

    * A **tiered candidate** card is built by patching Rent/Mortgage to the
      tier multiplier and adding the floor bonus — nothing about the
      Bilt Cash mechanics (secondary currency, accelerator) leaks in.
    * A **bilt-cash candidate** card attributes the housing locked → unlocked
      conversion back to housing categories (per-dollar realized unlock
      rate) and folds only the Point Accelerator (Tier 2) bonus into
      ``annual_bonus``. Housing categories are pinned to the candidate via
      ``priority_categories`` so allocation routes them here.

    For each candidate we compute the card's own per-dollar earn value
    (housing-attributed unlock + accelerator lump). The Tier 1 unlock and
    Tier 2 accelerator are summed for the mode-selection comparison since
    both contribute to total Bilt Cash mode value.

    The non-housing allocation estimate used by both candidates is drawn
    from the candidate's own view of the wallet (its own multipliers,
    competing against the other wallet cards' static multipliers), so
    neither path reuses allocation assumptions from the other.
    """
    if not any(c.housing_tiered_enabled for c in cards if c.id in selected_ids):
        return cards

    housing_names_lower = {n.lower() for n in housing_category_names}
    selected_cards = [c for c in cards if c.id in selected_ids]
    out: list[CardData] = []
    for c in cards:
        if not c.housing_tiered_enabled or c.id not in selected_ids:
            out.append(c)
            continue

        primary_cpp = c.currency.cents_per_point

        # --- Tiered mode candidate ------------------------------------
        # The tier multiplier depends on non_housing/housing ratio, which
        # in turn depends on the tiered candidate's own non-housing
        # allocation. Since the tier multiplier only affects housing
        # categories (not non-housing), we can compute the non-housing
        # allocation against a provisional tiered card — the choice of
        # tier_mult doesn't change which non-housing categories Bilt wins.
        provisional_tiered = _build_tiered_mode_card(
            c, tier_mult=1.25, floor_bonus_pts=0.0,
            housing_category_names=housing_category_names,
            foreign_prefix=foreign_prefix,
        )
        tiered_selected = [
            provisional_tiered if sc.id == c.id else sc for sc in selected_cards
        ]
        tiered_non_housing = _non_housing_allocated_to_card(
            provisional_tiered, tiered_selected, spend, wallet_currency_ids,
            housing_names_lower, foreign_prefix,
        )
        ratio = tiered_non_housing / housing_spend_total if housing_spend_total > 0 else 0.0
        tier_mult = tiered_housing_multiplier(ratio)
        tiered_housing_pts = housing_spend_total * tier_mult
        floor_bonus_pts = (
            max(0.0, ANNUAL_FLOOR_PTS - tiered_housing_pts)
            if housing_spend_total > 0
            else 0.0
        )
        tiered_value_dollars = (tiered_housing_pts + floor_bonus_pts) * primary_cpp / 100.0

        # --- Bilt Cash mode candidate ---------------------------------
        # Build a provisional candidate to estimate the card's non-housing
        # allocation. The provisional uses ``tier1_bonus_bp=0`` /
        # ``tier2_bonus_bp=0`` so neither path's bonus value leaks into the
        # other's competing-cards view; the housing pin and disabled
        # secondary mechanics still apply.
        provisional_bilt_cash = _build_bilt_cash_mode_card(
            c,
            tier1_bonus_bp=0.0,
            tier2_bonus_bp=0.0,
            bilt_cash_consumed=0.0,
            housing_spend_total=housing_spend_total,
            housing_category_names=housing_category_names,
            foreign_prefix=foreign_prefix,
        )
        bilt_cash_selected = [
            provisional_bilt_cash if sc.id == c.id else sc for sc in selected_cards
        ]
        bilt_cash_non_housing = _non_housing_allocated_to_card(
            provisional_bilt_cash, bilt_cash_selected, spend, wallet_currency_ids,
            housing_names_lower, foreign_prefix,
        )
        (
            _t1_spend,
            _t2_spend,
            _t3_spend,
            tier1_bonus_bp,
            tier2_bonus_bp,
            bilt_cash_consumed,
        ) = _bilt_cash_mode_bonus_bp(c, bilt_cash_non_housing, housing_spend_total)
        # Mode-selection compares total Bilt Cash mode value (locked-housing
        # unlock + accelerator) against the tiered mode's housing-direct earn.
        bilt_cash_value_dollars = (tier1_bonus_bp + tier2_bonus_bp) * primary_cpp / 100.0

        if tiered_value_dollars >= bilt_cash_value_dollars and housing_spend_total > 0:
            out.append(_build_tiered_mode_card(
                c, tier_mult, floor_bonus_pts,
                housing_category_names, foreign_prefix,
            ))
        else:
            out.append(_build_bilt_cash_mode_card(
                c,
                tier1_bonus_bp=tier1_bonus_bp,
                tier2_bonus_bp=tier2_bonus_bp,
                bilt_cash_consumed=bilt_cash_consumed,
                housing_spend_total=housing_spend_total,
                housing_category_names=housing_category_names,
                foreign_prefix=foreign_prefix,
            ))
    return out
