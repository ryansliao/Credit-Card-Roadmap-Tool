"""Data containers for the calculator engine.

Plain dataclasses — no DB dependency, no behavior. Split out so the rest of
the subpackage can import from a stable, dependency-free module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


# ---------------------------------------------------------------------------
# Card / currency inputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CreditLine:
    """Statement credit row for calculations (ids match library `credits.id`)."""

    library_credit_id: int
    name: str
    value: float
    excludes_first_year: bool = False
    is_one_time: bool = False


@dataclass
class CurrencyData:
    """Snapshot of a reward currency for use in the calculator engine."""

    id: int
    name: str
    reward_kind: str  # "points" (incl. miles) or "cash"
    cents_per_point: float
    # Default CPP from the currency definition (never overridden by wallet CPP).
    # Used for balance/point-count calculations that should be CPP-independent.
    comparison_cpp: float = 0.0
    photo_slug: Optional[str] = None
    cash_transfer_rate: float = 1.0
    partner_transfer_rate: Optional[float] = None
    # When set, this currency upgrades to the target when any wallet card earns the target directly
    converts_to_currency: Optional["CurrencyData"] = None
    # Rate when converting: 1 unit of this = converts_at_rate units of target (default 1.0)
    converts_at_rate: float = 1.0
    # CPP to use when no transfer enabler card is present; None = no reduction
    no_transfer_cpp: Optional[float] = None
    # Multiplier on wallet CPP when no transfer enabler is present (e.g. 0.7 for Citi);
    # takes precedence over no_transfer_cpp when set.
    no_transfer_rate: Optional[float] = None


@dataclass
class CardData:
    """All static data for one card, ready for the calculator engine."""

    id: int
    name: str
    issuer_name: str              # denormalised for display

    # Default currency this card earns
    currency: CurrencyData

    annual_fee: float
    sub_points: int
    sub_cash: float  # dollar-denominated SUB bonus (e.g. $200 cash back), added at face value
    sub_secondary_points: int  # SUB in the card's secondary currency (e.g. Bilt Cash)
    sub_min_spend: Optional[int]
    sub_months: Optional[int]
    sub_spend_earn: int
    annual_bonus: int
    annual_bonus_percent: float = 0.0
    annual_bonus_first_year_only: bool = False
    # Multiplier on allocation score that reflects the percentage bonus.
    # Set by compute_wallet before calculation. 1.0 = no bonus.
    # Recurring 10%: 1.1. First-year-only 100% over 2yr: 1.5.
    earn_bonus_factor: float = 1.0
    first_year_fee: Optional[float] = None

    # category -> always-on rate per dollar. For additive cards this already
    # includes the base + uncapped additive premiums. For non-additive cards
    # it's the legacy "highest standalone multiplier replaces base" value.
    multipliers: dict[str, float] = field(default_factory=dict)
    # Group metadata tuple:
    #   (multiplier, categories, top_n, group_id, cap_amount, cap_period_months,
    #    is_rotating, rotation_weights, is_additive)
    # - cap_amount:        per-period spend cap in dollars (None = uncapped)
    # - cap_period_months: 1=monthly, 3=quarterly, 6=semi-annual, 12=annual (None = uncapped)
    # - is_rotating:       True for rotating-bonus cards (Discover IT, Chase Freedom Flex).
    #                      Uses frequency-weighted allocation: each card captures
    #                      p_C share of category spend at the FULL bonus rate,
    #                      with the remainder going to the next-best card. There
    #                      is no pooling across categories within the rotating group.
    # - rotation_weights:  category_name -> p_C (activation probability in [0, 1]),
    #                      empty when is_rotating is False.
    # - is_additive:       True if the group's multiplier is a *premium* that
    #                      stacks onto the always-on rate for the matching
    #                      category. False (legacy): the multiplier replaces
    #                      the always-on rate when applied.
    multiplier_groups: list[
        tuple[
            float,
            list[str],
            Optional[int],
            Optional[int],
            Optional[float],
            Optional[int],
            bool,
            dict[str, float],
            bool,
        ]
    ] = field(default_factory=list)
    # Manual group category selections: group_id -> set of selected category names (empty/missing = auto-pick by spend)
    group_selected_categories: dict[int, set[str]] = field(default_factory=dict)
    credit_lines: list[CreditLine] = field(default_factory=list)
    # Set of category names where the multiplier only applies via the card's booking portal
    portal_categories: set[str] = field(default_factory=set)
    # Standalone is_portal=True premiums on this card. Each tuple is
    # (category_name_lowercase, premium_value, is_additive). The calculator
    # gates these by `portal_share`: only `share × spend[category]` of the
    # category's segment dollars get the portal premium; the rest fall back
    # to the card's non-portal rate on that category.
    portal_premiums: list[tuple[str, float, bool]] = field(default_factory=list)
    # Per-wallet share of travel-portal spend for this card (0..1). When the
    # card belongs to multiple TravelPortals, this is the *max* share across
    # those portals (so per-card calculations and the legacy greedy path see
    # the most-generous share). The LP path uses `portal_memberships` instead,
    # which preserves the portal_id grouping needed to pool caps across cards
    # that share a portal.
    # Set by `apply_wallet_portal_shares` from wallet_portal_shares rows.
    # Default 0 = portal premiums contribute nothing.
    portal_share: float = 0.0
    # {travel_portal_id: share} for every TravelPortal this card belongs to
    # in the current wallet. Empty when the card has no portal share rows.
    # The LP uses this to build *pooled* portal-cap constraints — all cards
    # in the same portal share one cap = `share × seg_dollars[cat]`, instead
    # of each card having its own independent cap.
    portal_memberships: dict[int, float] = field(default_factory=dict)
    # True if this card enables partner transfers for its currency (e.g. Sapphire Reserve for UR)
    transfer_enabler: bool = False

    # Foreign transaction fee: True = card charges ~3% FTF on foreign spend
    has_foreign_transaction_fee: bool = False
    # Payment network name (e.g. "Visa", "Mastercard") for FTF allocation priority
    network_name: Optional[str] = None
    # Bonus multiplier from a "Foreign Transactions" category (e.g. Summit 5x foreign)
    foreign_multiplier_bonus: float = 0.0
    # True when the card waives the ~3% housing payment processing fee
    # (e.g. Bilt's built-in rent/mortgage platform).
    housing_fee_waived: bool = False
    # Lowercase housing category names this card incurs the processing fee
    # on. Empty for waived cards. Populated by ``compute_wallet`` from the
    # wallet's housing categories. Used by allocation/LP scoring (subtract
    # the fee % from the dollar-equivalent score) and per-card EAF
    # accounting (deduct fee × allocated_housing_spend from net annual).
    housing_fee_categories: frozenset[str] = field(default_factory=frozenset)

    # Secondary currency earned at a flat rate on all allocated spend
    # (e.g. Bilt Cash at 4% alongside Bilt Points via multipliers)
    secondary_currency: Optional[CurrencyData] = None
    secondary_currency_rate: float = 0.0  # e.g. 0.04 for 4%
    # LP scoring factor for the secondary currency bonus. Accounts for the
    # convertibility cap (cap_rate × housing_spend): when the cap binds across
    # the wallet, the effective per-dollar Bilt Cash bonus is less than the
    # full rate. Set by ``compute_wallet`` before LP scoring. 1.0 = uncapped.
    # ``_calc_secondary_currency`` still uses the full rate and applies the
    # real cap when computing the actual dollar value of the secondary earn.
    secondary_scoring_factor: float = 1.0
    # Conversion cap: secondary currency can only convert to points when non-housing
    # spend on this card ≤ cap_rate × housing spend. 0 = no cap. (e.g. 0.75 for Bilt)
    secondary_currency_cap_rate: float = 0.0
    # Recurring annual bonus paid in the secondary currency (e.g. Bilt
    # Palladium: 200 BC/yr). Added to the BC budget in
    # ``apply_bilt_2_housing_mode`` so it can fund Tier 1 housing unlock or
    # Point Accelerator activations alongside spend-derived BC.
    secondary_currency_annual_bonus: int = 0
    # Spend category names (lowercase; may include ``__foreign__`` prefix) on
    # which the secondary currency earns *nothing* — neither points nor the
    # scoring bonus. Bilt 2.0 in Bilt Cash mode populates this with Rent /
    # Mortgage so housing spend doesn't wrongly get 4% Bilt Cash or win
    # allocation via the secondary comparison bonus.
    secondary_ineligible_categories: frozenset[str] = field(default_factory=frozenset)

    # Point accelerator: spend secondary currency to earn bonus primary points
    # (e.g. Bilt: $200 Bilt Cash for +1x on next $5,000, up to 5x/year)
    accelerator_cost: int = 0           # secondary currency points per activation
    accelerator_spend_limit: float = 0.0  # spend cap per activation in dollars
    accelerator_bonus_multiplier: float = 0.0  # extra primary multiplier per activation
    accelerator_max_activations: int = 0  # max activations per year

    # Annual secondary-currency units consumed by off-band redemptions that
    # ``_calc_secondary_currency`` can't see. Currently populated only by
    # ``apply_bilt_2_housing_mode`` in Bilt Cash mode to account for Tier 1
    # Bilt Cash spent on the housing-payment → Bilt Points redemption and
    # Tier 2 Bilt Cash spent on Point Accelerator activations. Subtracted
    # from the card's displayed secondary-currency balance.
    secondary_consumption_pts: float = 0.0

    # Bilt 2.0: when true, the card has two mutually exclusive housing
    # earning modes — direct tiered points on Rent/Mortgage scaled by the
    # non-housing:housing spend ratio on this card, OR the secondary-currency
    # (Bilt Cash) path. ``compute_wallet`` picks whichever produces higher
    # per-card net value and patches the card's effective multipliers /
    # secondary-currency rate accordingly before running the main compute.
    housing_tiered_enabled: bool = False

    # Spend categories pinned to this card by a manual wallet override.
    # Category names are stored lowercase/stripped for case-insensitive lookup.
    # When a category appears in any selected card's ``priority_categories``,
    # that card is the sole allocation winner for the category across both
    # the simple and segmented calculation paths.
    priority_categories: frozenset[str] = field(default_factory=frozenset)

    # Wallet-specific date context (None = active for the full calculation window)
    wallet_added_date: Optional[date] = None
    wallet_closed_date: Optional[date] = None
    # sub_projected_earn_date: auto-calculated from spend profile
    sub_projected_earn_date: Optional[date] = None
    # sub_earnable: False when spend rate is too low to hit the SUB min within the SUB window
    sub_earnable: bool = True

    def __post_init__(self) -> None:
        # Guard against admin-data slips: negative values propagate as silent
        # zero-divides and weird allocations downstream. ``None`` or ``0``
        # are the standard "no SUB" sentinels (see ``is_sub_earnable``);
        # only strict negatives are rejected.
        if self.sub_min_spend is not None and self.sub_min_spend < 0:
            raise ValueError(
                f"CardData(id={self.id}): sub_min_spend must be >= 0 or None, "
                f"got {self.sub_min_spend}"
            )
        if self.sub_months is not None and self.sub_months < 0:
            raise ValueError(
                f"CardData(id={self.id}): sub_months must be >= 0 or None, "
                f"got {self.sub_months}"
            )


# ---------------------------------------------------------------------------
# Calculator outputs
# ---------------------------------------------------------------------------


@dataclass
class CardResult:
    """Per-card outputs from the calculator, zeroed when card is not selected."""

    card_id: int
    card_name: str
    selected: bool
    # Net annual cost after credits, amortised SUB/fees, and wallet-allocated category earn (at CPP).
    effective_annual_fee: float = 0.0
    # Per-card EAF using the card's own active duration (wallet_added_date to
    # wallet_closed_date) instead of the wallet window. For per-card display only;
    # wallet/currency totals use effective_annual_fee (wallet years).
    card_effective_annual_fee: float = 0.0
    # The card's own active duration in years within the wallet window
    # (from wallet_added_date to wallet_closed_date). Used by the frontend
    # for per-card income display; wallet/currency totals use wallet years.
    card_active_years: float = 0.0
    total_points: float = 0.0
    # Per-card per-active-year earn rate (for per-card display). Excludes SUBs.
    annual_point_earn: float = 0.0
    # Window-basis earn rate (total_card_earn / wallet_window_years), excluding
    # SUBs. Use this for wallet/currency-group aggregation so summing per-card
    # values stays on the wallet window and doesn't inflate.
    annual_point_earn_window: float = 0.0
    credit_valuation: float = 0.0
    annual_fee: float = 0.0
    first_year_fee: Optional[float] = None
    sub_points: int = 0
    annual_bonus: int = 0
    annual_bonus_percent: float = 0.0
    annual_bonus_first_year_only: bool = False
    sub_extra_spend: float = 0.0
    sub_spend_earn: int = 0
    # Opportunity cost: net dollar value foregone on the rest of the wallet
    # to cover the SUB extra spend (gross opp cost minus sub_spend_earn value)
    sub_opp_cost_dollars: float = 0.0
    # Gross dollar opportunity cost (best alternative earn on the extra spend,
    # before crediting back the sub_spend_earn earned on the target card)
    sub_opp_cost_gross_dollars: float = 0.0
    # Dollars-per-wallet-year that SUB-related terms contributed to
    # effective_annual_fee. Adding this to effective_annual_fee yields the
    # value that would have been produced if SUBs were excluded from EAF.
    # The calculator always includes SUBs; the wallet-level "Include SUBs"
    # toggle is applied as a pure display switch on the frontend.
    sub_eaf_contribution: float = 0.0
    # Card-year basis variant, paired with card_effective_annual_fee.
    card_sub_eaf_contribution: float = 0.0
    avg_spend_multiplier: float = 0.0
    cents_per_point: float = 0.0
    # Effective currency name (may differ from default when upgrade is active)
    effective_currency_name: str = ""
    effective_currency_id: int = 0
    effective_reward_kind: str = "points"
    effective_currency_photo_slug: Optional[str] = None
    # Per-category earn breakdown: (category_name, annual_points), sorted desc by points
    category_earn: list[tuple[str, float]] = field(default_factory=list)
    # Effective multiplier per spend-category for this card (top-N applied,
    # foreign variants stripped). Includes the "All Other" entry; categories
    # without an explicit entry fall back to "All Other" when looked up.
    category_multipliers: dict[str, float] = field(default_factory=dict)

    # Secondary currency earn
    secondary_currency_earn: float = 0.0        # gross secondary pts over projection window
    secondary_currency_name: str = ""
    secondary_currency_id: int = 0
    accelerator_activations: int = 0            # how many accelerator activations used
    accelerator_bonus_points: float = 0.0       # extra primary currency pts earned
    accelerator_cost_points: float = 0.0        # secondary currency pts spent on accelerator
    secondary_currency_net_earn: float = 0.0    # gross secondary pts minus accelerator cost
    secondary_currency_value_dollars: float = 0.0  # annualized dollar value of net secondary earn

    # Annual housing processing fee: 3% × allocated housing spend on cards
    # without ``housing_fee_waived``. Already deducted from
    # ``effective_annual_fee``; surfaced here as a separate dollar line so
    # the UI can show the cost without having to re-derive it.
    housing_fee_dollars: float = 0.0

    # The projected SUB earn date used for this card's allocation (post-LP /
    # plan_sub_targeting). The calculator does not write this field —
    # ``compute_wallet`` only reads ``CardData.sub_projected_earn_date`` for
    # segment boundaries. The scenario-results endpoint mirrors the
    # pre-compute projection it built into ``CardData`` here so the
    # snapshot carries it forward to the roadmap.
    sub_projected_earn_date: Optional[date] = None


@dataclass
class WalletResult:
    """Aggregated wallet outputs."""

    years_counted: int
    total_effective_annual_fee: float
    total_points_earned: float
    # Wallet-level annual points income — total points earned across the wallet
    # window divided by the window's years. Not a sum of per-card annual rates.
    point_income: float
    # Sum of CardResult.sub_eaf_contribution across selected cards; frontend
    # adds this to total_effective_annual_fee when the wallet-level "Include
    # SUBs" toggle is off, so toggling is a display-only switch.
    total_sub_eaf_contribution: float = 0.0
    # Sum of projection-period reward units for cash-kind cards only (× cpp/100 = dollars).
    total_cash_reward_dollars: float = 0.0
    # Σ (total_points × cents_per_point / 100) over selected cards — comparable across currencies.
    total_reward_value_usd: float = 0.0
    # currency_name -> total points over the projection period (spend + SUB/bonuses, net of SUB opp cost).
    currency_pts: dict[str, float] = field(default_factory=dict)
    currency_pts_by_id: dict[int, float] = field(default_factory=dict)
    # Wallet calc window in years (end - start, fractional).
    wallet_window_years: float = 0.0
    # Per-currency active window in years, keyed by effective currency id.
    # Spans from the earliest open to the latest close (or window end) among
    # selected cards earning the currency, clamped to the wallet window. Used
    # by the frontend to annualize per-currency income over the currency's
    # own window rather than the full wallet window.
    currency_window_years: dict[int, float] = field(default_factory=dict)
    # Secondary currency totals (e.g. Bilt Cash earned across all cards)
    secondary_currency_pts: dict[str, float] = field(default_factory=dict)
    secondary_currency_pts_by_id: dict[int, float] = field(default_factory=dict)
    card_results: list["CardResult"] = field(default_factory=list)


# ---------------------------------------------------------------------------
# SUB spend planning outputs
# ---------------------------------------------------------------------------


@dataclass
class SubCardSchedule:
    """Planned SUB targeting for one card."""

    card_id: int
    start_date: date          # when spend begins targeting this card
    projected_earn_date: date  # when the SUB minimum is projected to be met
    daily_spend_allocated: float  # $/day directed to this card
    # Categories assigned to this card for SUB spend (category_name -> annual $).
    # Empty when the card gets the full wallet spend (sequential exclusive phase).
    category_allocation: dict[str, float] = field(default_factory=dict)


@dataclass
class SubSpendPlan:
    """Result of SUB spend feasibility analysis."""

    feasible: bool
    # True when all cards can be satisfied simultaneously (no sequencing needed)
    parallel: bool = False
    schedules: list[SubCardSchedule] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Secondary currency intermediate result (internal)
# ---------------------------------------------------------------------------


@dataclass
class _SecondaryResult:
    """Output from secondary currency + accelerator computation."""
    gross_annual_pts: float = 0.0       # gross secondary currency pts earned per year
    net_annual_pts: float = 0.0         # after subtracting accelerator cost per year
    dollar_value_annual: float = 0.0    # annualized dollar contribution
    activations: int = 0                # accelerator activations per year
    bonus_pts_annual: float = 0.0       # extra primary currency pts per year from accelerator
    cost_pts_annual: float = 0.0        # secondary currency pts spent on accelerator per year
