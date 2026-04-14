# Credit Card Wallet Evaluator

## Agent Instructions
- Prefer correct, complete implementations over minimal ones.
- Use appropriate data structures and algorithms.
- Don't brute force what has a known better solution.
- When fixing a bug, fix the root cause, not the system.
- Before shipping any calculator change, run
  `cd backend && ../.venv/bin/python -m pytest tests/test_calculator_snapshot.py`.
  If the snapshot intentionally needs to change, rerun with `--snapshot-update`
  and commit the fixture update as its own commit.

> High-level product description, tech stack, and local-dev setup live in the
> repo `README.md`. This file is the agent-facing reference for *how the
> system actually works* — things you can't derive from reading the code
> quickly.

## Core Concepts

**Spend Categories**
`SpendCategory` is a hierarchical table (`parent_id`, `is_system`,
`is_housing`, `is_foreign_eligible`). These are the card-level multiplier
categories (e.g., "Travel", "Dining", "Hotels"). A locked "All Other" system
category is auto-created and cannot be renamed or deleted (pinned to ID 1;
"Travel" is pinned to ID 2). Reference data is managed via `/admin/*`
endpoints — there is no startup seeding.

**Wallet Spend**
Each wallet has `WalletSpendItem` rows — one per `SpendCategory` — with an
annual dollar amount.

**Wallet**
A named collection of cards to evaluate together. Each `WalletCard` has
`added_date`, optional `closed_date`, `acquisition_type`
(opened/product_change), optional SUB overrides, `sub_earned_date` (UI
toggle), and `sub_projected_earn_date` (auto-calculated). Cards must be
active (added ≤ reference date, not closed) to count in calculations.
Wallet stores its own calc config: `calc_start_date`, `calc_end_date`,
`calc_duration_years`, `calc_duration_months`, `calc_window_mode`.

**EV Calculation**
`app.calculator` is a pure subpackage (no DB access) split into topical
modules. It uses two calculation paths depending on whether the wallet has
explicit date bounds (`calc_start_date` / `calc_end_date`) and any card has
a `wallet_added_date`:

- **Simple path** (`secondary._average_annual_net_dollars`): used when no
  window dates are set or no card has date context. Treats all selected
  cards as active for the full `years` period.
- **Segmented path** (`segmented_ev._segmented_card_net_per_year`): used when
  window dates are provided and at least one card has `wallet_added_date`.
  Splits the window into contiguous segments at every card
  open/close/SUB-earn boundary and at every capped-group period boundary;
  each segment uses its own active-card set and SUB ROS boosts, prorated by
  days. Per-segment allocation is solved optimally by
  `segment_lp._solve_segment_allocation_lp` (scipy linprog), with a
  per-card greedy fallback in the same module.

**`effective_annual_fee` semantics**: this field is `-(net_annual_value)` —
the negative of the average annual net dollar benefit
(points + credits − fees). A negative value means the card returns more
value than it costs. It is **not** simply `annual_fee − credits`.

**Simple-path formula** (average annual net dollars over `years`):
```
( effective_earn * cpp/100 * years        # recurring annual earn (in effective currency)
  + sub_spend_earn * cpp/100              # one-time SUB-spend earn (amortised by ÷years)
  + sub_pts * cpp/100                     # one-time SUB bonus (amortised by ÷years)
  + fy_bonus * cpp/100                    # one-time first-year pct bonus (amortised by ÷years)
  + annual_credits * years
  + one_time_credits                      # one-time credits (amortised by ÷years)
  - first_year_fee - (years-1)*annual_fee
) / years
```
Where:
- `effective_earn` = `calc_annual_point_earn_allocated * _conversion_rate` (effective currency pts/yr)
- `cpp` = effective currency's cents-per-point (after upgrade if applicable)
- `sub_spend_earn` / `sub_pts` are zero when `sub_earnable = False`
- `fy_bonus` = first-year-only percentage bonus points (zero when recurring or no pct set)
- `first_year_fee` defaults to `annual_fee` when not explicitly set

**Category allocation**: each spend category is awarded to the card(s) with
the highest `multiplier × effective_CPP × earn_bonus_factor +
secondary_bonus` score. Tied cards split the category spend evenly and
each earns on their allocated share. Cash currencies compete at 1¢/pt
regardless of actual CPP.

**Top-N group logic**: `CardMultiplierGroup` rows can restrict a group of
categories to the top-N by spend; categories outside the top-N fall back to
the "All Other" multiplier.

**Currency upgrade**: if a card's currency has `converts_to_currency_id`
pointing to a currency earned directly by another selected card, the card's
earn is converted at `converts_at_rate` and valued at the target currency's
CPP. This affects both category allocation scores and earn dollar valuation
(e.g., UR Cash → Chase UR).

**Percentage-based annual bonus**: `annual_bonus_percent` earns a percentage
of the card's own category earn as bonus points. Two modes controlled by
`annual_bonus_first_year_only`:
- **Recurring** (False): e.g. CSP's 10% anniversary bonus. Added to
  `annual_point_earn` every year via `_pct_bonus()`. Shown as "Annual Bonus
  (10%)" in category breakdown.
- **First-year-only** (True): e.g. Discover IT's 100% cashback match. Treated
  as a one-time earn (like SUB), amortised over the projection years.
  Computed from annualized category earn via `_first_year_pct_bonus()`.
  Shown as "First Year Match (100%)" in category breakdown.

Both are overridable at the wallet level (WalletCard fields). The fixed
`annual_bonus` (integer points) still works alongside and is independent of
the percentage bonus.

**Foreign spend split**: `compute._split_spend_for_foreign` takes the
wallet-level `foreign_spend_percent` and splits each *foreign-eligible*
spend category into a domestic (97%) and `__foreign__` (3%) bucket. Only
categories with `SpendCategory.is_foreign_eligible = True` are split — US-
only recurring categories (Phone, Internet, Streaming, Amazon, …) stay
100% domestic. The foreign bucket is then restricted to no-FTF Visa/MC
cards at allocation time.

**Display note**: `CardResult.category_earn` (the per-category breakdown) is
in **raw** currency units (conversion rate not applied), while
`annual_point_earn` is in **effective** currency units (conversion rate
applied). For wallets with currency upgrades, the two are in different
units — the category breakdown will sum to more than `annual_point_earn`.

**Bilt 2.0 housing** (`housing_tiered_enabled` on Card,
`app.calculator.housing_tiered`): when set, the card offers two mutually
exclusive earning modes and `compute_wallet` picks whichever yields more
per-card dollar value. The two paths are evaluated as fully isolated
candidate card states — each candidate gets its own non-housing allocation
estimate so neither path's parameters leak into the other's comparison.

**Tiered housing mode**: points directly on Rent/Mortgage scaled by the
non-housing/housing ratio of spend allocated to the card. Tier table:
`<25% → 0x + 3000 pt/yr floor`, `25–50% → 0.5x`, `50–75% → 0.75x`,
`75–100% → 1.0x`, `≥100% → 1.25x`. Floor is applied as an `annual_bonus`
addition sized to make total housing earn at least 3,000 pts. Secondary
currency (Bilt Cash) earn and the Point Accelerator are fully disabled.

**Bilt Cash mode**: non-housing spend earns the card's base category
multiplier plus a three-tier Bilt Cash → Bilt Points bonus (housing
earns 0 direct points — the 1x base is "locked" and its value is already
baked into the Tier 1 effective rate):

- **Tier 1** — first `0.75 × housing_spend` dollars of non-housing.
  Earns `secondary_currency_rate × 100 × (1000/3000)` BP per dollar
  (Palladium: 2x base + 1.333x Bilt Cash bonus = **3.33x effective**).
  Models the Bilt Cash → Bilt Points conversion redeemed at housing
  payment time; 3,000 Bilt Cash pts (= $30) unlock 1,000 Bilt Points.
- **Tier 2** — next `accelerator_max_activations × accelerator_spend_limit`
  dollars of non-housing when the Point Accelerator is configured on the
  card. Earns `accelerator_bonus_multiplier` BP per dollar (Palladium:
  2x base + 1x accelerator = **3x effective**). Activations are
  self-funded: each $5,000 of Tier 2 spend earns $200 in Bilt Cash which
  exactly covers the cost of one activation.
- **Tier 3** — remaining non-housing. Base category multiplier only
  (Palladium: **2x**). Extra Bilt Cash earned here has no redemption path
  under the current model and is valued at 0.

In Bilt Cash mode the card is patched with the three-tier bonus as a
single lump-sum `annual_bonus` in Bilt Points; the legacy
`secondary_currency` / `accelerator_*` fields are zeroed so the flat-rate
secondary-currency pipeline doesn't double-count on top of the lump sum.

`apply_bilt_2_housing_mode` runs once per compute before `_scoring_factor`,
the LP, and the simple-path earn, so both code paths see the resolved
mode. See `backend/app/calculator/housing_tiered.py`.

**SUB tracking**: Two separate concepts control SUB handling:

- `sub_earned_date` (DB/UI only): a toggle on owned cards in the cards panel.
  Purely for user tracking — indicates the user has confirmed the SUB was
  earned. When set, the backend clears `sub_projected_earn_date` (no
  projection needed). Does **not** flow into the calculator's `CardData`.
- `sub_projected_earn_date` (DB + calculator): auto-calculated from the
  wallet's daily spend rate and the card's SUB minimum/window. Used by the
  segmented calculation path for segment boundaries and SUB ROS boost
  timing. Cleared when `sub_earned_date` is set.
- `sub_already_earned` (calculator only, `CardData`): set True when
  `sub_earned_date` is present. Tells the calculator to skip SUB ROS boost
  and segment boundaries for this card while still including the SUB bonus
  in the total.
- `sub_earnable`: set false when the user's annual spend rate cannot hit
  `sub_min_spend` within `sub_months`. When false, the SUB bonus,
  sub_spend_earn, and their opportunity cost are all excluded. Forced true
  when `sub_already_earned` is true.

Future cards (added_date > today) show projected SUB status via roadmap
badges. Owned cards show a manual "SUB earned" toggle instead. The
projected earn date is displayed on both Future and Owned cards (hidden
when the toggle is on for Owned cards).

**SUB opportunity cost** (`credits.calc_sub_opportunity_cost`): models the
value lost on competing wallet cards by diverting extra spend to hit the
SUB minimum. Deducted from `total_points` and surfaced as
`sub_opp_cost_dollars` / `sub_opp_cost_gross_dollars` on `CardResult`.

**Roadmap Tracking**
`/wallets/{id}/roadmap` returns:
- 5/24 status (personal cards opened in last 24 months)
- Per-card SUB status (Pending / Earned / Expired / No SUB)
- Days remaining and next eligibility date per card
- Issuer rule violations (Chase 5/24, Amex 1/90, Citi 1/8, Citi 2/65)

## Data Model (Key Entities)

**Reference (managed via admin endpoints):**
- `Issuer`, `CoBrand`, `Network`, `NetworkTier`
- `Currency` — reward currency with default CPP, optional `converts_to_currency_id`
- `Card` — annual fee, SUB value/spend/days, issuer, currency, network
- `SpendCategory` — hierarchical card categories (`parent_id`, `is_system`,
  `is_housing`, `is_foreign_eligible`); "All Other"=ID 1, "Travel"=ID 2
- `CardCategoryMultiplier` — earn rate per card/category
- `CardMultiplierGroup` — top-N grouped category logic
- `CardCredit` — annual credits with type and dollar value
- `IssuerApplicationRule` — velocity rules (cooldowns, 5/24, etc.)

**Wallet-owned:**
- `Wallet` — calc config fields + metadata
- `WalletCard` — card in wallet with dates, acquisition_type, SUB overrides
- `WalletSpendItem` — annual spend amount per SpendCategory (current model)
- `WalletCurrencyCpp` — per-wallet CPP override per currency
- `WalletCurrencyBalance` — tracked point balances
- `WalletCardCredit` — per-wallet statement credit valuation overrides
- `WalletCardMultiplier` — per-wallet multiplier overrides per card/category

**Legacy (still in DB, no longer used in code):**
- `WalletSpendCategory` / `WalletSpendCategoryMapping` — replaced by
  `WalletSpendItem`. ORM models remain for schema generation; all endpoints
  and helper functions have been removed.

## Backend Structure

```
backend/
  app/
    main.py            # FastAPI app creation, lifespan, middleware, router includes, SPA serving
    constants.py       # DEFAULT_USER_ID, ALL_OTHER_CATEGORY, ALLOCATION_SUM_TOLERANCE, PREFERRED_FOREIGN_NETWORKS
    models.py          # SQLAlchemy ORM models
    schemas.py         # Pydantic v2 request/response schemas
    calculator/        # Pure calculation engine subpackage (no DB dependency)
      __init__.py      #   Public re-exports: compute_wallet, CardData, …
      types.py         #   Dataclasses (CardData, CardResult, WalletResult, SubSpendPlan, …)
      multipliers.py   #   Category multiplier lookup + % bonus factors
      currency.py      #   CPP, transfer enablement, effective currency selection
      allocation.py    #   Simple-path winner-takes-category allocation
      credits.py       #   Credits, SUB opp cost, total points
      secondary.py     #   Bilt-style secondary currency + simple-path EV formula
      sub_planner.py   #   EDF SUB spend scheduler (plan_sub_targeting)
      segments.py      #   Segment builder + per-card per-segment earn
      segment_lp.py    #   scipy LP solver + greedy fallback
      segmented_ev.py  #   Time-weighted per-card net value orchestrator
      compute.py       #   compute_wallet orchestrator + foreign-spend split
    db_helpers.py      # DB → calculator bridge: load_card_data, load_spend, …
    database.py        # Engine setup, session factory, idempotent migrations
    helpers.py         # Shared endpoint helpers (404 factories, selectinload builders, SUB date math, schema conversion)
    date_utils.py      # Pure date utility functions
    routers/
      __init__.py
      issuers.py         # GET /issuers, GET /issuers/application-rules
      currencies.py      # GET /currencies
      cards.py           # GET /cards, PATCH /cards/{id}
      credits.py         # GET /credits, POST/PATCH/DELETE /admin/credits
      spend.py           # GET /spend, GET /app-spend-categories
      travel_portals.py  # GET /travel-portals, POST/PUT/DELETE /admin/travel-portals
      wallets.py         # Wallet CRUD, add/update/remove wallet cards
      wallet_spend.py    # Wallet spend items CRUD
      wallet_currencies.py # Currency balances and CPP overrides
      wallet_credits.py  # Wallet card credit overrides
      wallet_multipliers.py # Wallet card multiplier overrides
      wallet_groups.py   # Wallet card group category selections
      wallet_rotations.py # Wallet card rotation overrides
      wallet_portals.py  # Wallet portal shares
      wallet_results.py  # GET /wallets/{id}/results, GET /wallets/{id}/roadmap
      admin.py           # Admin CRUD: issuers, currencies, spend categories, cards, multipliers, groups, rotating history
  migrations/          # Idempotent SQL migrations; filenames like 001_*.sql, ordered by name
  tests/               # pytest: snapshot regression against compute_wallet
  docs/                # Backend design docs (calculator-refactor.md, …)
```

External code imports the calculator via `from app.calculator import X` —
the submodule layout is opaque and can be reshuffled without breaking
callers.

## Frontend Structure

```
frontend/src/
  App.tsx                            # Root: ErrorBoundary, QueryClient, Router, Nav, SignInDropdown, AuthGate
  main.tsx                           # Entry point
  api/client.ts                      # Typed API client (all endpoints)
  auth/
    AuthContext.tsx                   # Google OAuth provider, useAuth() hook
  components/
    ModalBackdrop.tsx                # Shared modal backdrop (Escape key, backdrop click)
  utils/
    format.ts                        # formatMoney(), formatMoneyExact(), formatPoints(), formatPointsExact(), today()
  pages/
    Home.tsx                         # Landing page (public)
    Profile.tsx                      # Profile settings page (authenticated)
    WalletTool/
      index.tsx                      # Main page (wallet selector, layout, tabs)
      constants.ts                   # DEFAULT_USER_ID, LOCKED_USER_SPEND_CATEGORY_NAME
      hooks/
        useCardLibrary.ts            # Card library query
        useAppSpendCategories.ts     # Hierarchical spend category tree query
        useWalletSpendCategoriesTable.ts # Wallet spend items table state
      lib/
        queryKeys.ts                 # Centralised React Query key arrays
        walletCardForm.ts            # Form validation and payload building
      components/
        cards/                       # CardsListPanel, WalletCardModal, CardLibraryInfoModal, StatementCreditsModal
        spend/                       # AnnualSpendPanel, AddSpendCategoryPicker, SpendCategoryMappingModal, SpendTabContent
        summary/                     # WalletResultsAndCurrenciesPanel, CurrencySettingsModal
        wallet/                      # CreateWalletModal
        roadmap/                     # ApplicationRuleWarningModal
```

## Frontend Routing

- `/` — Public landing page (`Home.tsx`)
- `/profile` — Profile settings, redirects to `/` if unauthenticated (`Profile.tsx`)
- `/roadmap-tool` — Wallet tool, auto-selects most recent wallet (`WalletTool/index.tsx`)
- `/roadmap-tool/wallets/:walletId` — Wallet tool with specific wallet selected
- `*` — Catch-all redirects to `/`

Protected routes use `AuthGate` which redirects unauthenticated users to `/`.
Sign-in is handled via a navbar dropdown (`SignInDropdown` in `App.tsx`),
not a dedicated page.

## Known Pitfalls

**SQL migrations are T-SQL and use GO as a batch separator** — the migration
runner (`database._execute_migration_file`) splits each `.sql` file on `GO`
(its own line, case-insensitive) and submits each batch separately via
`conn.execute(text(batch))`. `CREATE TRIGGER` / `CREATE PROCEDURE` / `CREATE
VIEW` must be the first statement in a batch; wrap them in `EXEC(N'...')` if
they need to be conditional (i.e. inside an `IF NOT EXISTS` block). Guard
all DDL with `IF NOT EXISTS (SELECT 1 FROM sys.columns / sys.objects WHERE
…)` so migrations are idempotent and can be re-applied safely.  Use
`sys.columns`, `sys.objects`, `sys.indexes`, `sys.triggers`, and
`sys.key_constraints` — not `pg_*` catalog tables.

**No startup seed code** — all reference data (cards, issuers, currencies,
spend categories, multipliers, credits, rotating history, travel portals,
application rules) lives exclusively in the database and is managed via
admin endpoints. Do NOT create seed files, startup seed functions, or
hardcoded reference data in Python code.

**Calculator snapshot test** — `backend/tests/test_calculator_snapshot.py`
pins `compute_wallet` output for Wallet 1 (from the dev DB) against a
committed fixture. Any calculator edit must keep the snapshot green; if a
change is intentional, rerun with `--snapshot-update` and commit the
fixture as a separate commit so reviewers can see the delta. The test
assumes wallet 1 exists in the dev DB — don't delete it.

## Known Conventions

**React Query keys** — always use `queryKeys.*` from `lib/queryKeys.ts`:
- `['wallets', userId]`, `['cards']`, `['app-spend-categories']`
- `['wallet-currency-balances', walletId]`, `['wallet-currencies', walletId]`
- `['wallet-spend-items', walletId]`, `['wallet-card-credits', walletId, cardId]`
- `['roadmap', walletId]`

**Shared hooks** — avoid inline `useQuery` for data that multiple components
need: use `useCardLibrary()`, `useAppSpendCategories()` from `hooks/`.

**Format utilities** — use `formatMoney`, `formatMoneyExact`, `formatPoints`,
`formatPointsExact`, `today()` from `utils/format.ts`; do not re-define them
per component.

**Modal pattern** — wrap all modal dialogs with `<ModalBackdrop>` from
`components/ModalBackdrop.tsx` for consistent Escape-key handling and
backdrop dismiss.

**Constants** — shared backend constants live in `backend/app/constants.py`;
import from there rather than re-defining in `main.py`, `schemas.py`, etc.

**Calculator imports** — always `from app.calculator import X` (or the
relative form `from .calculator import X` / `from ..calculator import X`
inside the backend). Never import from specific calculator submodules
(`app.calculator.compute`, `app.calculator.segments`, …) outside the
subpackage itself — the layout is internal and may be reshuffled.

## What Does NOT Exist
- No Library/card-editing UI — card and reference data is managed via admin endpoints
- No xlsx import — data.xlsx and xlsx_loader.py have been removed
- No side-by-side wallet comparison view
- No optimization/recommendation engine (best card for each category)
- No export (CSV/PDF)

## What This Project Is NOT
- Not a live card database — reference data is manually maintained via admin endpoints
- Not a credit score tool
- Not connected to any bank or financial institution
