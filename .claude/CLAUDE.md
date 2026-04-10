# Credit Card Wallet Evaluator

## Agent Instructions
- Prefer correct, complete implementations over minimal ones.
- Use appropriate data structures and algorithms.
- Don't brute force what has a known better solution.
- When fixing a bug, fix the root cause, not the system.

## Project Overview
A personal finance tool for evaluating credit card wallet combinations. Users configure
their spending profile and a set of cards, then the tool calculates expected annual value
— across points/miles earned, statement credits, and sign-up bonuses — projected over a
user-defined time horizon (1–5 years).

## Architecture
- **Backend**: FastAPI + SQLAlchemy (async), PostgreSQL
- **Frontend**: React 18 + TypeScript + Tailwind CSS, React Query
- **Reference Data**: Cards, currencies, categories, multipliers, and credits are managed
  directly in the DB via admin endpoints (`/admin/*`). There is no startup seeding.
- **Single-tenant**: `DEFAULT_USER_ID = 1` defined in `backend/app/constants.py`; no authentication

## Core Concepts

**Reference Data**
Cards, issuers, currencies, spend categories, multipliers, credits, and issuer application
rules live in the DB. Reference data is created/edited via admin endpoints. There is no
xlsx or file-based import.

**Spend Categories**
`SpendCategory` is a hierarchical table (`parent_id`, `is_system`). These
are the card-level multiplier categories (e.g., "Travel", "Dining", "Hotels"). A locked
"All Other" system category is auto-created and cannot be renamed or deleted (pinned to ID 1;
"Travel" is pinned to ID 2). The hierarchy is seeded via `_seed_spend_category_hierarchy()`
in `main.py` on startup.

**Wallet Spend**
Each wallet has `WalletSpendItem` rows — one per `SpendCategory` — with an annual dollar
amount.

**Wallet**
A named collection of cards to evaluate together. Each `WalletCard` has `added_date`,
optional `closed_date`, `acquisition_type` (opened/product_change), optional SUB overrides,
`sub_earned_date` (UI toggle), and `sub_projected_earn_date` (auto-calculated). Cards must
be active (added ≤ reference date, not closed) to count in calculations. Wallet stores its
own calc config: `calc_start_date`, `calc_end_date`, `calc_duration_years`,
`calc_duration_months`, `calc_window_mode`.

**EV Calculation**
`calculator.py` is a pure engine (no DB access). It uses two calculation paths depending on
whether the wallet has explicit date bounds (`calc_start_date` / `calc_end_date`) and any
card has a `wallet_added_date`:

- **Simple path** (`_average_annual_net_dollars`): used when no window dates are set or no
  card has date context. Treats all selected cards as active for the full `years` period.
- **Segmented path** (`_segmented_card_net_per_year`): used when window dates are provided
  and at least one card has `wallet_added_date`. Splits the window into contiguous segments
  at every card open/close/SUB-earn boundary; each segment uses its own active-card set and
  SUB ROS boosts, prorated by days.

**`effective_annual_fee` semantics**: this field is `-(net_annual_value)` — the negative of
the average annual net dollar benefit (points + credits − fees). A negative value means the
card returns more value than it costs. It is **not** simply `annual_fee − credits`.

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

**Category allocation**: each spend category is awarded to the card(s) with the highest
`multiplier × effective_CPP` score. Tied cards split the category spend evenly and each
earns on their allocated share. Cash currencies compete at 1¢/pt regardless of actual CPP.

**Top-N group logic**: `CardMultiplierGroup` rows can restrict a group of categories to the
top-N by spend; categories outside the top-N fall back to the "All Other" multiplier.

**Currency upgrade**: if a card's currency has `converts_to_currency_id` pointing to a
currency earned directly by another selected card, the card's earn is converted at
`converts_at_rate` and valued at the target currency's CPP. This affects both category
allocation scores and earn dollar valuation (e.g., UR Cash → Chase UR).

**Percentage-based annual bonus**: `annual_bonus_percent` earns a percentage of the card's
own category earn as bonus points. Two modes controlled by `annual_bonus_first_year_only`:
- **Recurring** (False): e.g. CSP's 10% anniversary bonus. Added to `annual_point_earn`
  every year via `_pct_bonus()`. Shown as "Annual Bonus (10%)" in category breakdown.
- **First-year-only** (True): e.g. Discover IT's 100% cashback match. Treated as a one-time
  earn (like SUB), amortised over the projection years. Computed from annualized category
  earn via `_first_year_pct_bonus()`. Shown as "First Year Match (100%)" in category breakdown.
Both are overridable at the wallet level (WalletCard fields). The fixed `annual_bonus`
(integer points) still works alongside and is independent of the percentage bonus.

**Display note**: `CardResult.category_earn` (the per-category breakdown) is in **raw**
currency units (conversion rate not applied), while `annual_point_earn` is in **effective**
currency units (conversion rate applied). For wallets with currency upgrades, the two are
in different units — the category breakdown will sum to more than `annual_point_earn`.

**SUB tracking**: Two separate concepts control SUB handling:

- `sub_earned_date` (DB/UI only): a toggle on owned cards in the cards panel. Purely for
  user tracking — indicates the user has confirmed the SUB was earned. When set, the backend
  clears `sub_projected_earn_date` (no projection needed). Does **not** flow into the
  calculator's `CardData`.
- `sub_projected_earn_date` (DB + calculator): auto-calculated from the wallet's daily spend
  rate and the card's SUB minimum/window. Used by the segmented calculation path for segment
  boundaries and SUB ROS boost timing. Cleared when `sub_earned_date` is set.
- `sub_already_earned` (calculator only, `CardData`): set True when `sub_earned_date` is
  present. Tells the calculator to skip SUB ROS boost and segment boundaries for this card
  while still including the SUB bonus in the total.
- `sub_earnable`: set false when the user's annual spend rate cannot hit `sub_min_spend`
  within `sub_months`. When false, the SUB bonus, sub_spend_earn, and their opportunity cost
  are all excluded. Forced true when `sub_already_earned` is true.

Future cards (added_date > today) show projected SUB status via roadmap badges. Owned cards
show a manual "SUB earned" toggle instead. The projected earn date is displayed on both
Future and Owned cards (hidden when the toggle is on for Owned cards).

**SUB opportunity cost** (`calc_sub_opportunity_cost`): models the value lost on competing
wallet cards by diverting extra spend to hit the SUB minimum. Deducted from `total_points`
and surfaced as `sub_opp_cost_dollars` / `sub_opp_cost_gross_dollars` on `CardResult`.

**Roadmap Tracking**
`/wallets/{id}/roadmap` returns:
- 5/24 status (personal cards opened in last 24 months)
- Per-card SUB status (Pending / Earned / Expired / No SUB)
- Days remaining and next eligibility date per card
- Issuer rule violations (Chase 5/24, Amex 1/90, Citi 1/8, Citi 2/65)

## Key Features (Implemented)
- Create/manage wallets; add cards with open dates and optional SUB overrides
- Multi-year EV projection with optional reference date range
- Per-wallet spend items mapped directly to card categories
- Per-wallet CPP (cents per point) overrides per currency
- Point/mile balance tracking with total portfolio value estimate
- Roadmap tab: 5/24 status, SUB tracking, issuer rule violation alerts
- Per-wallet statement credit valuation overrides
- Per-wallet multiplier overrides per card/category

## Data Model (Key Entities)

**Reference (managed via admin endpoints, seeded on startup):**
- `Issuer`, `CoBrand`, `Network`, `NetworkTier`
- `Currency` — reward currency with default CPP, optional `converts_to_currency_id`
- `Card` — annual fee, SUB value/spend/days, issuer, currency, network
- `SpendCategory` — hierarchical card categories (parent_id, is_system); "All Other"=ID 1, "Travel"=ID 2
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
- `WalletSpendCategory` / `WalletSpendCategoryMapping` — replaced by `WalletSpendItem`.
  ORM models remain for schema generation; all endpoints and helper functions have been removed.

## Frontend Structure

```
frontend/src/
  App.tsx                            # Root: ErrorBoundary, QueryClient, Router
  main.tsx                           # Entry point
  api/client.ts                      # Typed API client (all endpoints)
  components/
    ModalBackdrop.tsx                # Shared modal backdrop (Escape key, backdrop click)
  utils/
    format.ts                        # formatMoney(), formatMoneyExact(), formatPoints(), formatPointsExact(), today()
  pages/WalletTool/
    index.tsx                        # Main page (wallet selector, layout, tabs)
    constants.ts                     # DEFAULT_USER_ID, LOCKED_USER_SPEND_CATEGORY_NAME
    hooks/
      useCardLibrary.ts              # Card library query
      useAppSpendCategories.ts       # Hierarchical spend category tree query
      useWalletSpendCategoriesTable.ts # Wallet spend items table state (mutations, editing, picker)
    lib/
      queryKeys.ts                   # Centralised React Query key arrays
      walletCardForm.ts              # Form validation and payload building utilities
    components/
      cards/
        CardsListPanel.tsx           # Cards list with SUB badges and quick actions
        WalletCardModal.tsx          # Add/edit wallet card (SUB, fees, dates)
        CardLibraryInfoModal.tsx     # Read-only card reference data
        StatementCreditsModal.tsx    # Edit statement credit valuations per wallet card
      spend/
        AnnualSpendPanel.tsx         # Spend items table with inline editing
        AddSpendCategoryPicker.tsx   # Picker for adding a spend category
        SpendCategoryMappingModal.tsx # Create/edit spend category with allocations
      summary/
        WalletResultsAndCurrenciesPanel.tsx  # Annual EV, fees, currency balances
        CurrencySettingsModal.tsx    # CPP overrides, initial balances, currency tracking
      wallet/
        CreateWalletModal.tsx        # Create new wallet
      roadmap/
        ApplicationRuleWarningModal.tsx  # Issuer rule violation alerts
```

## Backend Structure

```
backend/app/
  main.py            # FastAPI app creation, lifespan, middleware, router includes, SPA serving
  constants.py       # DEFAULT_USER_ID, ALL_OTHER_CATEGORY, ALLOCATION_SUM_TOLERANCE
  models.py          # SQLAlchemy ORM models
  schemas.py         # Pydantic v2 request/response schemas
  calculator.py      # Pure calculation engine (no DB dependency)
  db_helpers.py      # DB → calculator bridge: load_card_data, load_spend, etc.
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
```

## Known Pitfalls

**SQL migrations must be a single statement** — the migration runner uses
`conn.execute(text(sql_file.read_text()))` with asyncpg, which cannot execute multiple
statements in one prepared statement call. Always wrap multi-statement migrations in a
`DO $$ BEGIN ... END $$;` block so asyncpg sees a single statement.

**No startup seed code** — all reference data (cards, issuers, currencies, spend categories,
multipliers, credits, rotating history, travel portals, application rules) lives exclusively
in the database and is managed via admin endpoints. Do NOT create seed files, startup seed
functions, or hardcoded reference data in Python code. The `seed.py` file has been removed.

## Known Conventions

**React Query keys** — always use `queryKeys.*` from `lib/queryKeys.ts`:
- `['wallets', userId]`, `['cards']`, `['app-spend-categories']`
- `['wallet-currency-balances', walletId]`, `['wallet-currencies', walletId]`
- `['wallet-spend-items', walletId]`, `['wallet-card-credits', walletId, cardId]`
- `['roadmap', walletId]`

**Shared hooks** — avoid inline `useQuery` for data that multiple components need:
- Use `useCardLibrary()`, `useAppSpendCategories()` from `hooks/`

**Format utilities** — use `formatMoney`, `formatMoneyExact`, `formatPoints`,
`formatPointsExact`, `today()` from `utils/format.ts`; do not re-define them per component.

**Modal pattern** — wrap all modal dialogs with `<ModalBackdrop>` from
`components/ModalBackdrop.tsx` for consistent Escape-key handling and backdrop dismiss.

**Constants** — shared backend constants live in `backend/app/constants.py`; import from
there rather than re-defining in `main.py`, `schemas.py`, etc.

## What Does NOT Exist
- No Library/card-editing UI — card and reference data is managed via admin endpoints
- No xlsx import — data.xlsx and xlsx_loader.py have been removed
- No side-by-side wallet comparison view
- No optimization/recommendation engine (best card for each category)
- No multi-user support or authentication
- No export (CSV/PDF)

## What This Project Is NOT
- Not a live card database — reference data is manually maintained via admin endpoints
- Not a credit score tool
- Not connected to any bank or financial institution
