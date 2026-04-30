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
- Keep this `CLAUDE.md` up to date when a change invalidates something
  documented here: calculator semantics, data-model entities, routing
  behaviour, known pitfalls, or a stated convention. Renames and new files
  don't need an update — the structure sections are intentionally
  high-level. If a section becomes wrong, fix it in the same change rather
  than leaving it.

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
Each user has one wallet with `WalletSpendItem` rows keyed by
`UserSpendCategory`, each with an annual dollar amount. Spend lives on the
wallet (not the scenario) — there is no per-scenario spend variation.
`foreign_spend_percent` also lives on the wallet.

**Wallet**
Each user has exactly **one Wallet** (auto-created on first `GET /wallet`,
DB-enforced via `UQ_wallets_user_id`). The wallet owns:
- `WalletSpendItem` rows — annual spend per `UserSpendCategory`.
- `foreign_spend_percent` (0–100, % of spend that's foreign).
- `CardInstance` rows where `scenario_id IS NULL` — the user's actual
  cards (managed via Profile/WalletTab).
- `Scenario` rows — what-if iterations (managed via the Roadmap Tool).

Calc-config fields (`start_date`, `end_date`, `duration_*`,
`window_mode`, `include_subs`) and the cached `last_calc_snapshot` live on
`Scenario`, not on `Wallet`.

**Scenario**
A what-if iteration of the user's wallet. Each `Scenario` carries its own
calc window, future-card additions, per-card overlays, and override
tables. Every wallet has at least one `Scenario` with `is_default=1` (the
filtered unique index `UX_scenarios_default_per_wallet` enforces at most
one default per wallet; deleting the only scenario auto-spawns a fresh
empty default).

Scenarios own:
- Calc config: `start_date`, `end_date`, `duration_years`,
  `duration_months`, `window_mode`, `include_subs`.
- `last_calc_snapshot` + `last_calc_timestamp` — cached results payload.
- Future `CardInstance` rows (`scenario_id = self.id`).
- `ScenarioCardOverlay` rows — per-scenario hypothetical edits to OWNED
  card instances.
- `ScenarioCardMultiplier`, `ScenarioCardCredit`,
  `ScenarioCardCategoryPriority`, `ScenarioCardGroupSelection` — per-scenario
  per-instance overrides.
- `ScenarioCurrencyCpp`, `ScenarioCurrencyBalance`, `ScenarioPortalShare` —
  per-scenario currency / portal state.

**CardInstance**
Replaces the legacy `WalletCard`. A specific instance of a library `Card`
held in a wallet. `scenario_id IS NULL` means owned (managed via
Profile/WalletTab); `scenario_id` set means a future card scoped to that
scenario (managed via the Roadmap Tool).

Acquisition is encoded by **date columns** rather than an enum:
- `opening_date` (NOT NULL) — the original account-open date. **Preserved
  across product changes** (a PC keeps the same account number, so the
  destination instance reuses the source's `opening_date`).
- `product_change_date` (NULLABLE) — when this card became its current
  product via a PC. NULL = fresh open.
- `closed_date` (NULLABLE) — when this card stopped being its current
  product (closure or PC'd-out).
- `pc_from_instance_id` (NULLABLE FK to `card_instances.id`) — links
  instance-to-instance, so duplicates of the same library card don't
  conflict in PC chains.

**Duplicates of the same library card are allowed** in one wallet
(multi-application cards, post-PC chains). There is intentionally no
unique constraint on `(wallet_id, card_id)`.

**ScenarioCardOverlay** carries per-scenario hypothetical edits to OWNED
`CardInstance` rows. All overlay fields are nullable; NULL means "inherit
from underlying CardInstance". The Roadmap Tool can never mutate the base
fields of an owned card — those edits go on overlays.

**Three-tier resolution** (calculator + UI):

    overlay.<f> ?? card_instance.<f> ?? library_card.<f>

For owned instances in a scenario the overlay tier applies. For
scenario-scoped (future) instances the overlay tier doesn't apply (their
own values are already scenario-specific). The backend's
`ScenarioResolver._resolve_effective` and the frontend's
`resolveCardInstance` (`frontend/src/pages/RoadmapTool/lib/resolveScenarioCards.ts`)
implement this rule.

**Credit inheritance** has its own three-level chain (separate from the
overlay/instance/library chain because credits are a list, not a single
field):

    library CardCredit → WalletCardCredit → ScenarioCardCredit

The wallet view sums `library + wallet`. The calculator merges all three
in `ScenarioResolver._build_instance_card_data`, keyed by
`library_credit_id`: each later layer replaces matching entries from the
previous. Future cards skip the wallet tier (no owned-card context). The
WalletTab modal writes to `WalletCardCredit` via `OwnedCardCreate` /
`OwnedCardUpdate`'s `credit_overrides` field — only diffs vs library
defaults are persisted, so library updates flow through unchanged
credits, and credits the user removed are stored as `value=0` overrides
(not absent — absence means "inherit").

**EV Calculation**
`app.calculator` is a pure subpackage (no DB access) split into topical
modules. It uses two calculation paths depending on whether the scenario
has explicit date bounds (`start_date` / `end_date`) and any card has a
`wallet_added_date`:

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

**Rotating groups (Discover IT / Chase Freedom Flex)**: `is_rotating=True`
groups use frequency-weighted allocation. Each card captures `p_C` share of
each rotating category's spend at the full bonus rate; remaining share goes
to other cards via the normal scoring path. The per-period cap (e.g. $1,500
/ quarter) is **pooled across the whole rotating group** — at most
`cap_amt` of bonus-rate spend per period across every category in the
group on that card. When the pool binds, bonus dollars are split
proportionally to each category's allocated spend and the rest earns at the
category's overflow rate (the always-on rate when set, otherwise All
Other). The simple path applies an annualised pool blend in
`allocation._pooled_rotating_blends`; the segmented per-card greedy and the
LP both pool via a single `("rot", group_id, period_start)` cap entry.

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

Both are overridable per CardInstance (and per ScenarioCardOverlay for
owned cards in a scenario). The fixed `annual_bonus` (integer points)
still works alongside and is independent of the percentage bonus.

**Wallet weight overrides**: `WalletUserSpendCategoryWeight` rows let a
user customize per-`UserSpendCategory` fan-out weights into the
underlying earn categories. They're applied during mapping expansion in
`CalculatorDataService.load_wallet_spend_items` via the pure helper
`app.services.wallet_category_weight_service.apply_weight_overrides`,
which merges overrides on top of the live default mapping set. The
existing normalization then makes the merged weights sum to 1.0 per
user category. Override rows for earn categories that no longer exist
in the seeded defaults are silently ignored (the calculator only
iterates the live default set).

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

**Bilt Cash mode**: housing earns 1 BP per dollar (locked) and non-housing
earns the card's base multiplier plus 4% Bilt Cash. BC is then consumed
at the housing-payment redemption ($30 BC unlocks 1,000 locked BP) so
the previously-locked housing BP convert to redeemable. The locked →
unlocked conversion is **attributed back to housing**: the patched
housing multiplier is the per-dollar realized unlock rate, not 0. The
Point Accelerator bonus is the only piece kept as a lump-sum
`annual_bonus`. Housing categories are pinned to the Bilt card via
`priority_categories` so allocation routes housing spend here — the
unlock mechanic only fires when housing is paid through the Bilt portal.

Three conceptual tiers of non-housing spend:

- **Tier 1** — first `0.75 × housing_spend` non-housing dollars. The
  4% Bilt Cash earned here is fully consumed by the housing redemption.
  Each Tier 1 BC dollar unlocks `1000/30 = 33.33` locked housing BP.
  At the cap, Tier 1 BC = `housing × secondary_rate × cap_rate` unlocks
  exactly `housing × 1` BP — the entire locked pool. Below the cap
  (insufficient BC), only a fraction of the locked pool unlocks; the
  patched per-dollar housing multiplier is `tier1_bonus_bp /
  housing_spend_total` (between 0 and 1). Bilt Cash is stored as dollar
  units (1 Bilt Cash unit = $1, `cents_per_point: 100`).
- **Tier 2** — next `accelerator_max_activations × accelerator_spend_limit`
  non-housing dollars when the Point Accelerator is configured.
  `accelerator_spend_limit` is the spend **per activation** that earns
  the bonus (Palladium: $1,000/activation), so total Tier 2 capacity =
  `max_activations × spend_limit`. Earns `accelerator_bonus_multiplier`
  BP per dollar on that bonus spend (Palladium: 1x bonus on $1,000 =
  **1,000 extra BP per activation**, 5,000 max/yr). The $200 activation
  cost (`accelerator_cost: 200` Bilt Cash dollars) is funded by BC
  earned on Tier 2 + Tier 3 spend (Tier 1 BC is already consumed by the
  housing unlock). The Tier 2 bonus is folded into the patched card's
  `annual_bonus`.
- **Tier 3** — remaining non-housing. Base category multiplier only
  (Palladium: **2x**). Extra Bilt Cash earned here has no realized
  redemption path beyond housing/accelerator and is held as a tracked
  balance with zero modeled dollar value.

The patched card has its housing multiplier set to the realized unlock
rate, housing pinned via `priority_categories`, only Tier 2 added to
`annual_bonus`, and `secondary_consumption_pts` populated with Tier 1 BC
+ activation BC consumed (subtracted from the displayed Bilt Cash balance
so the UI reflects what's actually left). The Bilt Cash currency is
shadow-copied with `cents_per_point=0` so the flat-rate secondary pipeline
doesn't double-count on top of the housing-attributed unlock value.

`apply_bilt_2_housing_mode` runs once per compute before `_scoring_factor`,
the LP, and the simple-path earn, so both code paths see the resolved
mode. See `backend/app/calculator/housing_tiered.py`.

**SUB tracking**:

- `sub_projected_earn_date` (calculator-only, `CardData`): per-instance
  projected SUB earn date computed by the `/scenarios/{id}/results`
  endpoint as a pre-pass before `compute_wallet`. Three rate sources by
  precedence: sub-priority cards use the full wallet daily spend; cards in
  the `plan_sub_targeting` schedule use the planner's per-card daily rate;
  everything else uses `calc_annual_allocated_spend / 365`. Used by the
  segmented calculation path for segment boundaries and SUB ROS boost
  timing, and persisted on `CardResult.sub_projected_earn_date` so the
  roadmap can read the same date the calc used.
- `sub_earnable` (calculator-only, `CardData`): set False when the user's
  annual spend rate cannot hit `sub_min_spend` within `sub_months`. When
  False, the SUB bonus, sub_spend_earn, and their opportunity cost are
  all excluded.

Future card instances (`opening_date > today`) show projected SUB status
via roadmap badges.

**Calc-snapshot freshness for the roadmap**: the roadmap reads per-
instance projected SUB earn dates from `Scenario.last_calc_snapshot`
rather than recomputing live. The endpoint always reads the snapshot
when one exists — it does NOT gate by hash match. Stale projections
are dimmed by the frontend (matching the lifetime-bar's disabled
styling), not hidden, so the SUB segment stays visible after a
state-changing edit until the user re-runs Calculate. The
`Scenario.last_calc_input_hash` column is still populated on calc via
`compute_scenario_state_hash` (`backend/app/services/scenario_resolver.py`)
and is available for downstream consumers that want a backend-verified
freshness signal; the chart relies on the frontend-local `isStale`
boolean (signature comparison) which already covers the in-session
edit case. The hash is built from a **wide-window** `ComputeInputs`
(`ref_date=date.min`, `window_end=date.max`) so the resolved-instance
set doesn't drift as calendar time advances; only the underlying
scenario rows feed the hash. `ref_date` and `window_end` are
deliberately excluded from the hash payload — they're externalities,
not state.

**SUB opportunity cost** (`credits.calc_sub_opportunity_cost`): models the
value lost on competing wallet cards by diverting extra spend to hit the
SUB minimum. Deducted from `total_points` and surfaced as
`sub_opp_cost_dollars` / `sub_opp_cost_gross_dollars` on `CardResult`.

**Roadmap Tracking**
`GET /scenarios/{scenario_id}/roadmap` returns:
- 5/24 status (personal cards where `opening_date >= today - 24mo` AND
  `product_change_date IS NULL` — PCs naturally excluded since the
  account-open date sits with the originating instance)
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
- `Credit` (system rows, `owner_user_id IS NULL`) + `CardCredit` join —
  global statement-credit catalog. User-scoped credits live in the same
  table with `owner_user_id` set; see Wallet-owned below.
- `IssuerApplicationRule` — velocity rules (cooldowns, 5/24, etc.)

**Wallet-owned (one wallet per user):**
- `Wallet` — name, description, `foreign_spend_percent`. UNIQUE on `user_id`.
- `WalletSpendItem` — annual spend amount keyed by `UserSpendCategory`
  (simplified 15-ish user-facing categories). The calculator expands each
  row into granular earn categories via `UserSpendCategoryMapping` weights.
- `UserSpendCategory` + `UserSpendCategoryMapping` — user-facing spend
  categories and their weighted fan-out to underlying `SpendCategory` rows.
- `CardInstance` (with `scenario_id IS NULL`) — the user's owned cards.
- `WalletCardCredit` — per-owned-instance credit valuation override. The
  middle tier in the three-level credit chain
  `library CardCredit → WalletCardCredit → ScenarioCardCredit`. Absence
  of a row means "inherit the library default". Owned cards write here
  from the WalletTab modal; scenarios layer their own overrides on top
  via `ScenarioCardCredit`. Future cards skip this tier — their credit
  values live directly in `ScenarioCardCredit`.
- `WalletUserSpendCategoryWeight` — per-wallet override of
  `UserSpendCategoryMapping.default_weight`, sparse: a row exists only
  when the user has customized a `(user_category, earn_category)` pair.
  Absence inherits the global default. Edited inline via the spending
  tab's per-category accordion. Housing and "All Other" are non-editable
  (server rejects with 400). The calculator merges these in via
  `apply_weight_overrides` before the existing weight normalization.
- `Scenario` — what-if iterations (next bullet).
- `Credit` (with `owner_user_id` set) — user-created statement credits.
  Visible only to the creating user; created via `POST /credits` (auth
  required) when typing a name that isn't in the search dropdown.
  Uniqueness on `credit_name` is enforced per-owner via the composite
  index `UX_credits_owner_name` so user A's "Costco Cash" doesn't block
  user B from creating one. The `CardCredit` join still links these
  rows to library cards so the credit auto-suggests on whichever card
  the user created it on, while remaining searchable for any other
  card. Only the owner can `PATCH`/`DELETE` via `/credits/{id}`;
  system credits are admin-only via `/admin/credits/*`.
- `TravelPortal` — reference travel portal (e.g. Chase TPG, Amex Travel)
  with transfer partner metadata.

**Scenario-owned (many per wallet, ≥1 with `is_default=1`):**
- `Scenario` — calc config + last-calc snapshot.
- `CardInstance` (with `scenario_id` set) — future cards specific to the
  scenario.
- `ScenarioCardOverlay` — per-scenario hypothetical edits to OWNED card
  instances (overlay tier of three-tier resolution).
- `ScenarioCardMultiplier` — per-scenario per-instance multiplier override.
- `ScenarioCardCredit` — per-scenario per-instance credit valuation override.
- `ScenarioCardCategoryPriority` — manual category-priority pin (force a
  category to a specific card instance in this scenario).
- `ScenarioCardGroupSelection` — per-scenario top-N picks for a
  `CardMultiplierGroup` on a specific card instance.
- `ScenarioCurrencyCpp` — per-scenario CPP override per currency.
- `ScenarioCurrencyBalance` — per-scenario tracked point balances.
- `ScenarioPortalShare` — per-scenario travel portal share.

## Backend Structure

Top-level layout — drill into a directory to see the files. Only noting the
pieces that would be hard to find or whose purpose isn't self-evident.

```
backend/
  app/
    main.py                    # FastAPI app, middleware, router includes, SPA serving
    constants.py               # Shared constants (see "Constants" convention)
    auth.py                    # Google OAuth + email/password login/register, /me, username
    database.py                # Engine, session factory, idempotent T-SQL migration runner
    date_utils.py              # Pure date helpers + SUB-window math
    models.py                  # Re-export shim over dal/ — keeps `from .models import X` working
    dal/                       # SQLAlchemy ORM models, one file per domain
    schemas/                   # Pydantic v2 request/response schemas, mirrors dal/
                               # + schemas/builders.py: card_instance_read,
                               #   scenario_read, wallet_with_scenarios_read,
                               #   wallet_to_schema
    calculator/                # Pure EV engine, no DB access (see "Calculator imports")
    services/                  # Data access layer — routers must go through these
                               # ScenarioResolver.build_compute_inputs() is the
                               # single seam where three-tier resolution lives
    routers/
      admin/                   # Reference/card CRUD
      reference/               # Reference-data read endpoints
      wallet/                  # /wallet, /wallet/card-instances, /wallet/spend-items
      scenario/                # /scenarios/* (CRUD, results, roadmap, overlays,
                               # future-cards, currencies, portals, priorities,
                               # credits)
  migrations/                  # Idempotent T-SQL migrations (see "Known Pitfalls")
  tests/                       # pytest + snapshot regression against compute_wallet
  seed/                        # YAML source of truth for dev reference data
```

**Calculator submodules** are split by concern (allocation, credits, currency,
housing_tiered, multipliers, secondary, segment_lp, segmented_ev, segments,
sub_planner, types, compute). The Core Concepts section above references
specific functions by qualified path (e.g.
`allocation._pooled_rotating_blends`) — use those as entry points.

### Service conventions

- Routers never call `db.execute()`; they inject services via FastAPI deps
  and call service methods. Services own queries, eager loading, and
  relationship management.
- Services receive `AsyncSession` via constructor and do NOT commit —
  routers commit after all service calls complete.
- Services return ORM models; routers serialize to schemas.
- Services raise `HTTPException` for client-facing errors.
- Eager-load option builders live on services as static methods.

Example:
```python
from ..services import ScenarioService, get_scenario_service

@router.get("/scenarios/{scenario_id}/results")
async def scenario_results(
    scenario_id: int,
    user: User = Depends(get_current_user),
    scenario_service: ScenarioService = Depends(get_scenario_service),
):
    scenario = await scenario_service.get_user_scenario(scenario_id, user)
    ...
```

## Frontend Structure

```
frontend/src/
  App.tsx            # ErrorBoundary, QueryClient, Router, Nav, SignInDropdown,
                     #   UsernamePrompt, AuthGate, UsernameGate
  api/client.ts      # Typed API client (all endpoints)
  auth/              # AuthProvider + useAuth hook (Google OAuth + email/password)
  components/        # Shared components (ModalBackdrop, InfoPopover, cards/*)
  hooks/             # Cross-page shared hooks (e.g. useCreditLibrary)
  lib/queryKeys.ts   # App-wide React Query key factories — always use these
  utils/             # format.ts, cardIncome.ts
  pages/
    Home.tsx         # Public landing
    Profile/         # Tabbed settings page (wallet / spending / appearance / settings)
    RoadmapTool/     # Wallet/roadmap evaluator — the main app
```

## Frontend Routing

- `/` — Public landing page (`Home.tsx`)
- `/profile` — Profile settings, redirects to `/` if unauthenticated (`Profile/index.tsx`).
  The active tab is driven by the `?tab=` query param (`wallet` | `spending` | `appearance` | `settings`).
- `/roadmap-tool` — RoadmapTool; auto-resolves to the wallet's default
  scenario.
- `/roadmap-tool/scenarios/:scenarioId` — RoadmapTool focused on a
  specific scenario.
- `*` — Catch-all redirects to `/`

Protected routes use `AuthGate` which redirects unauthenticated users to `/`.
Sign-in is handled via a navbar dropdown (`SignInDropdown` in `App.tsx`),
not a dedicated page. After Google OAuth, new users without a username are
shown `UsernamePrompt` via `UsernameGate` before they can use the app.

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

**Reference data seed system** — reference data (networks, issuers,
co-brands, application rules, currencies, spend categories, user spend
categories + mappings, travel portals, cards + nested multipliers/groups/
rotating history/portal links, credits + card links) is round-tripped
between the dev DB and `backend/seed/*.yaml` via `python -m app.seed`.
`user_spend_categories.yaml` is the source of truth for the user-facing
spend category list: name, description, `display_order`, `is_system`,
and the earn-category mappings with weights. Edit the YAML and run
`python -m app.seed load` to apply changes — not a migration:

- `python -m app.seed export` — dumps current DB to YAML (one file per
  entity; cross-references use natural names, IDs never leak into YAML).
- `python -m app.seed load` — idempotent upsert by natural key. Currency
  `converts_to` and SpendCategory `parent` are resolved in a second pass so
  forward references work regardless of YAML order. Card nested children
  (multipliers, groups, rotating, portal links) are synced in place;
  `CardMultiplierGroup` rows are matched by their category-set signature
  so groups referenced by `WalletCardGroupSelection` survive re-loads.

Run from `backend/` with the project venv active (`../.venv/bin/python -m
app.seed …`). Seeding is explicitly CLI-invoked — **do not** call it from
app startup or create startup seed functions. Treat the YAML files as the
source of truth for dev reference data: export after DB edits, commit the
diff alongside the admin-endpoint change that produced it.

**Calculator snapshot test** — `backend/tests/test_calculator_snapshot.py`
pins `compute_wallet` output for a fixture set of hand-built scenarios
(see the `SCENARIOS` dict near the bottom of the test for the current
list) against committed JSON fixtures under `backend/tests/fixtures/`.
Coverage spans the simple and segmented paths, rotating groups
(including pool overflow), currency upgrades, top-N groups, foreign
spend split, both Bilt 2.0 housing modes, recurring + first-year
percentage bonuses, SUB opportunity cost, priority category pins, and
the no-transfer-enabler reduced-CPP fallback. The fixtures are pure
Python `CardData` — no DB, no dev-wallet dependency, CI-portable. Any
calculator edit must keep the snapshot green; if a change is
intentional, rerun with `--snapshot-update` and commit the fixture
update as a separate commit so reviewers can see the delta.

## Known Conventions

**React Query keys** — always use the `queryKeys.*` factories from
`frontend/src/lib/queryKeys.ts`. Don't hand-build key arrays at call sites;
don't duplicate factories per page.

**Shared hooks** — avoid inline `useQuery` for data multiple components
need. Cross-page hooks live in `frontend/src/hooks/`; page-scoped hooks
live under the page's `hooks/` directory.

**Format utilities** — use `formatMoney`, `formatMoneyExact`, `formatPoints`,
`formatPointsExact`, `today()` from `utils/format.ts`. Do not redefine.

**Modal pattern** — wrap every modal in `<ModalBackdrop>` from
`components/ModalBackdrop.tsx` for consistent Escape and backdrop dismiss.

**Constants** — shared backend constants live in `backend/app/constants.py`;
import from there rather than redefining in `main.py`, `schemas/`, etc.

**Calculator imports** — always `from app.calculator import X` (or
`.calculator` / `..calculator` inside the backend). Never import from
specific submodules outside the subpackage — the layout is internal and
may be reshuffled.

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
