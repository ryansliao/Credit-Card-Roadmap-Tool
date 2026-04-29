# Spending Tab — Per-Category Weight Allocation Editor

**Date:** 2026-04-29
**Status:** Draft (approved for implementation)
**Scope:** `frontend/src/pages/Profile/components/SpendingTab.tsx`, `backend/app/dal/wallet_spend.py`, `backend/app/services/calculator_data_service.py`, new wallet router + service.

## Problem

Each `UserSpendCategory` (e.g. "Travel") fans out into one or more granular `SpendCategory` rows (e.g. Flights, Hotels, Travel-other) through `UserSpendCategoryMapping.default_weight`. These weights are global reference data — every user shares the same fan-out, which is shown read-only in the existing info popover on the spending tab.

Users want to customize their personal mix without affecting other users or the seeded defaults. A user whose travel is 80% flights should be able to skew their Travel allocation accordingly.

## Goals

- Per-wallet override of `UserSpendCategoryMapping.default_weight`.
- Inline accordion editor in the spending tab (no separate modal/page).
- Sparse storage so seed updates flow through to non-customized rows.
- Clean integration with the existing calculator without touching the snapshot test.

## Non-goals

- Adding or removing earn categories from a user category's default set (weights-only — set to 0 to "remove").
- Per-scenario weight overrides. Weights are wallet-level, like `WalletSpendItem` and `foreign_spend_percent`.
- Editing Housing or "All Other" — both are special-cased non-editable.

## Data model

New table **`wallet_user_spend_category_weights`** in `backend/app/dal/wallet_spend.py`:

| Column              | Type    | Notes                                                |
|---------------------|---------|------------------------------------------------------|
| `id`                | INT PK  | autoincrement                                        |
| `wallet_id`         | INT FK  | `wallets.id`, ON DELETE CASCADE                      |
| `user_category_id`  | INT FK  | `user_spend_categories.id`, ON DELETE CASCADE        |
| `earn_category_id`  | INT FK  | `spend_categories.id`, ON DELETE NO ACTION (matches existing FK behavior) |
| `weight`            | FLOAT   | NOT NULL, raw user-entered weight (server normalizes on read/write) |
| `created_at`        | DATETIME| `server_default=func.now()`                          |
| `updated_at`        | DATETIME| `server_default=func.now()`, `onupdate=func.now()`   |

**Constraints:**
- `UNIQUE (wallet_id, user_category_id, earn_category_id)` — one override per (wallet × user category × earn category).

**Sparse semantics:** a row exists only when the user has explicitly customized that mapping. Absence of a row means "inherit `UserSpendCategoryMapping.default_weight`". Resetting a user category to defaults = deleting all rows for `(wallet_id, user_category_id)`.

**Migration:** `backend/migrations/024_wallet_user_spend_category_weights.sql`, idempotent guards on `sys.objects` / `sys.indexes` per project convention. The migration runner splits on `GO`; `CREATE TABLE` and the unique index can each be guarded `IF NOT EXISTS`.

## Backend API

Three endpoints added to `backend/app/routers/wallet/` (alongside `/wallet/spend-items`). All require `get_current_user` and operate on the caller's wallet.

### `GET /wallet/category-weights/{user_category_id}`

Response shape:
```json
{
  "user_category_id": 5,
  "user_category_name": "Travel",
  "mappings": [
    {
      "earn_category_id": 12,
      "earn_category_name": "Flights",
      "default_weight": 0.5,
      "override_weight": 0.8,
      "effective_weight": 0.8
    },
    ...
  ]
}
```

- `default_weight` is the global value from `UserSpendCategoryMapping`.
- `override_weight` is `null` if no override row exists.
- `effective_weight` is what the calculator will use (override if present, else default), pre-normalization.

### `PUT /wallet/category-weights/{user_category_id}`

Request body:
```json
{ "weights": [{ "earn_category_id": 12, "weight": 80 }, { "earn_category_id": 13, "weight": 20 }] }
```

Server behavior:
1. Reject (`400`) if the user category is `is_housing=True` or is the locked "All Other" system row (id=1).
2. Validate (`422`) every `earn_category_id` in the body is in the user category's default mapping set.
3. Validate (`422`) total weight > 0.
4. Normalize all submitted weights to sum to 1.0.
5. Upsert one `WalletUserSpendCategoryWeight` row per submitted earn category.
6. Delete any existing override rows for `(wallet_id, user_category_id)` not in the submitted body.
7. Return the same shape as `GET`.

Each `weight` is a non-negative number in any unit (the frontend sends the user-typed percentages directly — no client-side conversion). The server normalizes to sum-to-1 before persisting, and returns the normalized values for the frontend to display.

### `DELETE /wallet/category-weights/{user_category_id}`

Deletes all override rows for `(wallet_id, user_category_id)`. Returns the same shape as `GET` (now with `override_weight: null` for every row). Same `400` rejection for housing / All Other.

### Service layer

New `WalletCategoryWeightService` in `backend/app/services/`:
- Constructor takes `AsyncSession`; does not commit (router commits).
- Returns ORM models; router serializes via Pydantic schemas.
- Raises `HTTPException` for client-facing errors.
- Static `eager_load_options()` helper if needed for combined queries.

### Schemas

In `backend/app/schemas/spend.py`:
- `WalletCategoryWeightRowRead` — one mapping row in the response
- `WalletCategoryWeightsRead` — the wrapper (`user_category_id`, `user_category_name`, `mappings`)
- `WalletCategoryWeightsWrite` — `PUT` body (`weights: list[{earn_category_id, weight}]`)

## Frontend UI

### SpendingTab changes (`frontend/src/pages/Profile/components/SpendingTab.tsx`)

Replace the existing ⓘ button next to each editable category name with a **chevron toggle** (▶ collapsed / ▼ expanded). Housing and "All Other" continue to render the existing read-only ⓘ popover unchanged.

When expanded, the accordion renders as a full-width second `<tr>` immediately below the category row, spanning all columns of the spending table. Only one accordion may be open at a time — opening a new one collapses the previous (`expandedCategoryId: number | null` state in `SpendingTab`).

### Accordion content (new component `CategoryWeightEditor.tsx`)

A sibling of `SpendingTab.tsx`. Owns:
- Lazy fetch via React Query on first mount (key `queryKeys.walletCategoryWeights(userCategoryId)`).
- Local draft state (per-row `weight` strings) initialized from `effective_weight * 100`.
- Save / Cancel / Reset to defaults handlers.

Layout:
```
┌─ Default mix for Travel spend ──────── Reset to defaults ─┐
│  Flights              [  50 ] %   [progress bar]          │
│  Hotels               [  30 ] %   [progress bar]          │
│  Travel-other         [  20 ] %   [progress bar]          │
│                                                            │
│  Total: 100%                       [ Cancel ]  [ Save ]    │
└────────────────────────────────────────────────────────────┘
```

- **Inputs:** small numeric `<input type="text" inputMode="numeric">` per row, matching the pattern used for the amount input in `SpendingTab.tsx`. Strip non-digits on input.
- **Total readout:** sum of typed values. `text-ink-muted` if 100, `text-warn` (or equivalent palette token) otherwise. Purely informational — the server normalizes on submit, so non-100 totals are valid.
- **Save:** button is always enabled; client-side guard blocks submission and surfaces "Total cannot be 0%" if every input is zero. Otherwise `PUT /wallet/category-weights/{id}` with the typed weights. On success, re-render the inputs with the normalized values from the response, then collapse the panel.
- **Cancel:** discard local draft; collapse the panel.
- **Reset to defaults:** native `confirm()` dialog → `DELETE /wallet/category-weights/{id}` → re-render with default weights, panel stays open.

### Plumbing

- `frontend/src/lib/queryKeys.ts` — add `walletCategoryWeights(id: number)` factory.
- `frontend/src/api/client.ts` — add `walletCategoryWeightsApi.{get, save, reset}` typed against the new schemas.
- After a successful save or reset: invalidate `queryKeys.walletSpendItemsSingular()` and `queryKeys.myWalletWithScenarios()` so downstream views (and the roadmap stale-snapshot logic) pick up the change.

## Calculator integration

**File:** `backend/app/services/calculator_data_service.py` (existing mapping expansion at lines 180–215).

Steps:
1. After loading `UserSpendCategoryMapping` rows for the wallet's referenced user categories, also load all `WalletUserSpendCategoryWeight` rows where `wallet_id == wallet.id`.
2. Build lookup `override_by_pair: dict[tuple[int, int], float]` keyed on `(user_category_id, earn_category_id)`.
3. When populating `mappings_by_user_cat`, swap the weight:
   ```python
   weight = override_by_pair.get(
       (mapping.user_category_id, mapping.earn_category_id),
       mapping.default_weight,
   )
   mappings_by_user_cat.setdefault(mapping.user_category_id, []).append(
       (earn_cat_name, weight)
   )
   ```
4. The existing normalization at line 214 (`total_weight = sum(w for _, w in mappings)`) handles partial overrides cleanly — overridden + unoverridden weights normalize together as a unit.

The Housing override at lines 202–205 (forcing 100% Rent or Mortgage based on `housing_type`) executes *after* the mapping expansion, so housing weight overrides — even if one were somehow inserted (server rejects them, but defensive) — are clobbered before reaching the compute path.

**Snapshot freshness:** weight overrides feed into `ComputeInputs.spend_by_category` via the expansion above. `compute_scenario_state_hash` hashes the resolved `ComputeInputs`, so changes naturally invalidate the cached snapshot. No staleness logic needed beyond the existing flow.

## Testing

- **Unit test (new):** exercise `CalculatorDataService` with a small in-memory wallet that has a partial weight override; assert the resulting `spend_by_category` matches the expected fan-out (overridden rows + remaining default rows, normalized together).
- **Snapshot test:** `backend/tests/test_calculator_snapshot.py` builds `CardData` directly and bypasses `CalculatorDataService`, so no fixture update is required by this change. Per the `CLAUDE.md` rule, the snapshot will be re-run as a verification step before commit.
- **API tests:** the three endpoints with auth, validation paths (housing rejection, all-other rejection, unknown earn_category_id, all-zeros body), and basic CRUD round-trip.

## Edge cases & safety

- **Housing user category (`is_housing=True`):** no chevron in UI. Server rejects `PUT`/`DELETE` with `400`. The existing housing→100% override at calc time clobbers any stray data.
- **"All Other" user category (id=1):** no chevron. Server rejects `PUT`/`DELETE` with `400`. Single mapping with weight 1.0 — nothing to allocate.
- **`PUT` validation:** unknown `earn_category_id` → `422`. Weights summing to 0 → `422`. Negative weights → `422`.
- **Add/remove rows from the default set:** disallowed. UI hides controls; server rejects unknown ids. Setting weight to 0 effectively removes a row from the calc.
- **Concurrent writes:** wallet-scoped + per-user-category atomic; the unique constraint is the integrity backstop. No optimistic locking.
- **Library re-seed orphan:** if a re-seed removes an earn_category from a default mapping, override rows for it become orphaned. The UI validates renderable rows against the current default set (so they hide), and the calculator only iterates the live default mapping set then applies overrides on top (so orphans don't leak in). A targeted cleanup migration can be added later if this ever bites in practice.

## Files touched

**Backend (new):**
- `backend/app/dal/wallet_spend.py` — append `WalletUserSpendCategoryWeight` model.
- `backend/migrations/<NNN>_wallet_user_spend_category_weights.sql` — table + unique index.
- `backend/app/services/wallet_category_weight_service.py` — new service.
- `backend/app/services/__init__.py` — export.
- `backend/app/routers/wallet/category_weights.py` — new router.
- `backend/app/routers/wallet/__init__.py` — register router.
- `backend/app/schemas/spend.py` — three new schemas.
- `backend/app/schemas/__init__.py` — export.
- `backend/app/models.py` — re-export new model.

**Backend (modified):**
- `backend/app/services/calculator_data_service.py` — load + apply overrides in mapping expansion.

**Backend (tests):**
- `backend/tests/test_wallet_category_weights.py` — new (API + service).
- `backend/tests/test_calculator_data_service_overrides.py` — new (override path through expansion).

**Frontend (new):**
- `frontend/src/pages/Profile/components/CategoryWeightEditor.tsx` — accordion content.

**Frontend (modified):**
- `frontend/src/pages/Profile/components/SpendingTab.tsx` — chevron toggle, accordion row, expanded-id state.
- `frontend/src/lib/queryKeys.ts` — `walletCategoryWeights(id)` factory.
- `frontend/src/api/client.ts` — `walletCategoryWeightsApi` + types.

## Documentation

- Update `CLAUDE.md` "Wallet-owned" section to list the new `WalletUserSpendCategoryWeight` table and its sparse semantics.
- Update the calculator section if needed to mention that wallet-level weight overrides are applied during mapping expansion before normalization.
