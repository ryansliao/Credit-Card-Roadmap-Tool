# Per-Wallet Spend Category Weight Overrides — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let each user customize the per-`UserSpendCategory` fan-out weights into granular `SpendCategory` rows, edited inline in the spending tab via an accordion, stored as a sparse per-wallet override layer.

**Architecture:** New table `wallet_user_spend_category_weights` holds `(wallet_id, user_category_id, earn_category_id) → weight` rows. Sparse: a row exists only when the user has customized that mapping; absence means inherit `UserSpendCategoryMapping.default_weight`. New `WalletCategoryWeightService` + three endpoints (GET/PUT/DELETE per user category). `CalculatorDataService` left-joins overrides into the existing mapping expansion before normalization. Frontend adds a chevron toggle to `SpendingTab` rows that opens an inline editor component.

**Tech Stack:** SQLAlchemy 2 async ORM, FastAPI, Pydantic v2, T-SQL migrations (sys.* catalogs, `GO` separator), React 18 + TypeScript, React Query, Tailwind.

**Spec:** [docs/superpowers/specs/2026-04-29-spend-category-weight-overrides-design.md](../specs/2026-04-29-spend-category-weight-overrides-design.md)

---

## Deviations from spec

These are deliberate, called out so reviewers can catch them.

1. **Test scope is reduced.** The spec asked for two new test files: an API-endpoint test and a `CalculatorDataService` integration test. The repo has no FastAPI/`TestClient` + DB fixture infrastructure; building it is its own feature. Replaced with a single pure-function unit test (`test_wallet_category_weight_merge.py`) covering the override-merge logic, plus a manual UI walkthrough (Task 14). The snapshot test stays as the regression backstop.
2. **Housing detection is by name, not flag.** The spec says housing rejection triggers on `is_housing=True`, but `UserSpendCategory` has no `is_housing` column (the flag exists on `SpendCategory`, the granular table). The implementation matches the calculator's existing approach (`name.strip().lower() == "housing"` — see `calculator_data_service.py:199`).
3. **Router filename.** Spec listed `backend/app/routers/wallet/category_weights.py`; plan uses `wallet_category_weights.py` to match the existing `wallet_*` naming convention (`wallet_card_instances.py`, `wallet_spend.py`, `wallets.py`).
4. **Save UX flow.** Spec said "Save → re-render with normalized values → collapse." Plan implements "Save → invalidate query cache → collapse." The user sees the normalized result on next open. The brief flash of normalized values before collapse adds complexity without informational value, since the collapse hides them within ~1 frame.

---

## File Structure

**Backend (new files):**
- `backend/app/dal/wallet_spend.py` — append the `WalletUserSpendCategoryWeight` model (lives next to `WalletSpendItem` per spec).
- `backend/migrations/024_wallet_user_spend_category_weights.sql` — table + unique index, idempotent.
- `backend/app/services/wallet_category_weight_service.py` — service for the three endpoints + a pure helper for the calculator override merge.
- `backend/app/routers/wallet/wallet_category_weights.py` — three endpoints under `/wallet/category-weights/...`.
- `backend/tests/test_wallet_category_weight_merge.py` — pure-function unit test for the override merge helper (no DB).

**Backend (modified):**
- `backend/app/dal/__init__.py` — export the new model.
- `backend/app/models.py` — re-export the new model.
- `backend/app/schemas/spend.py` — add three schemas: `WalletCategoryWeightRowRead`, `WalletCategoryWeightsRead`, `WalletCategoryWeightsWrite`.
- `backend/app/schemas/__init__.py` — export the new schemas.
- `backend/app/services/__init__.py` — export `WalletCategoryWeightService` and `get_wallet_category_weight_service`.
- `backend/app/services/calculator_data_service.py` — load override rows in the wallet expansion path; apply via the pure merge helper before the existing normalization.
- `backend/app/routers/wallet/__init__.py` — re-export pattern (currently empty; check before editing).
- `backend/app/main.py` — `include_router` for the new wallet router.

**Frontend (new files):**
- `frontend/src/pages/Profile/components/CategoryWeightEditor.tsx` — the accordion editor (fetch + draft state + save/cancel/reset).

**Frontend (modified):**
- `frontend/src/api/client.ts` — add `WalletCategoryWeightRow`, `WalletCategoryWeights`, `SaveWalletCategoryWeightsPayload` types and `walletCategoryWeightsApi`.
- `frontend/src/lib/queryKeys.ts` — add `walletCategoryWeights(userCategoryId)` factory.
- `frontend/src/pages/Profile/components/SpendingTab.tsx` — replace the read-only ⓘ icon with a chevron toggle for editable categories; render the accordion as a second `<tr>` below; manage `expandedCategoryId` state. Keep the existing read-only ⓘ popover unchanged for Housing and All Other.

**Docs:**
- `CLAUDE.md` — add `WalletUserSpendCategoryWeight` to the "Wallet-owned" list with sparse-storage note; update calculator section to mention wallet-level weight overrides feed into mapping expansion.

---

## Task 1: Add the DAL model

**Files:**
- Modify: `backend/app/dal/wallet_spend.py` (append new class)

- [ ] **Step 1: Append the new SQLAlchemy model**

Open `backend/app/dal/wallet_spend.py` and add (after the existing `WalletSpendItem` class):

```python
class WalletUserSpendCategoryWeight(Base):
    """
    Per-wallet override of UserSpendCategoryMapping.default_weight.

    Sparse: a row exists only when the user has customized the weight for
    a specific (user_category, earn_category) pair. Absence means
    "inherit the global default_weight". Resetting a user category to
    defaults = deleting all rows for (wallet_id, user_category_id).

    The weight stored here is raw (not normalized); the calculator
    normalizes the full mapping list (overrides + remaining defaults)
    before using it.
    """

    __tablename__ = "wallet_user_spend_category_weights"
    __table_args__ = (
        UniqueConstraint(
            "wallet_id", "user_category_id", "earn_category_id",
            name="UX_wallet_user_spend_category_weights",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_id: Mapped[int] = mapped_column(
        ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False
    )
    user_category_id: Mapped[int] = mapped_column(
        ForeignKey("user_spend_categories.id", ondelete="CASCADE"), nullable=False
    )
    earn_category_id: Mapped[int] = mapped_column(
        ForeignKey("spend_categories.id", ondelete="NO ACTION"), nullable=False
    )
    weight: Mapped[float] = mapped_column(Float, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<WalletUserSpendCategoryWeight wallet={self.wallet_id} "
            f"usc={self.user_category_id} ec={self.earn_category_id} "
            f"w={self.weight}>"
        )
```

The existing imports at the top of the file (`DateTime`, `Float`, `ForeignKey`, `Integer`, `UniqueConstraint`, `func`, `Mapped`, `mapped_column`, `Base`) are already present — no import changes needed.

- [ ] **Step 2: Verify the file imports cleanly**

Run: `cd backend && ../.venv/bin/python -c "from app.dal.wallet_spend import WalletUserSpendCategoryWeight; print(WalletUserSpendCategoryWeight.__tablename__)"`

Expected: `wallet_user_spend_category_weights`

- [ ] **Step 3: Commit**

```bash
git add backend/app/dal/wallet_spend.py
git commit -m "Add WalletUserSpendCategoryWeight ORM model

Sparse per-wallet override of UserSpendCategoryMapping.default_weight.
Absence of a row means inherit the global default."
```

---

## Task 2: Create the migration

**Files:**
- Create: `backend/migrations/024_wallet_user_spend_category_weights.sql`

- [ ] **Step 1: Write the migration**

Create `backend/migrations/024_wallet_user_spend_category_weights.sql`:

```sql
-- Migration 024: add wallet_user_spend_category_weights table.
--
-- Sparse per-wallet override of UserSpendCategoryMapping.default_weight,
-- one row per (wallet, user_category, earn_category) the user has
-- customized. Absence means inherit the global default. Lets users tune
-- the fan-out from a UserSpendCategory (e.g. "Travel") into its
-- underlying earn categories (Flights/Hotels/Travel-other) without
-- affecting other users or the seeded YAML defaults.
--
-- Idempotent. Re-runnable.

------------------------------------------------------------------------------
-- 1. Create wallet_user_spend_category_weights.
------------------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'wallet_user_spend_category_weights') AND type = 'U'
)
    CREATE TABLE wallet_user_spend_category_weights (
        id                INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        wallet_id         INT NOT NULL,
        user_category_id  INT NOT NULL,
        earn_category_id  INT NOT NULL,
        weight            FLOAT NOT NULL,
        created_at        DATETIMEOFFSET NOT NULL
                              CONSTRAINT DF_wallet_user_spend_category_weights_created_at
                              DEFAULT SYSUTCDATETIME(),
        updated_at        DATETIMEOFFSET NOT NULL
                              CONSTRAINT DF_wallet_user_spend_category_weights_updated_at
                              DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_wallet_user_spend_category_weights_wallet
            FOREIGN KEY (wallet_id)
            REFERENCES wallets(id)
            ON DELETE CASCADE,
        CONSTRAINT FK_wallet_user_spend_category_weights_user_category
            FOREIGN KEY (user_category_id)
            REFERENCES user_spend_categories(id)
            ON DELETE CASCADE,
        CONSTRAINT FK_wallet_user_spend_category_weights_earn_category
            FOREIGN KEY (earn_category_id)
            REFERENCES spend_categories(id),
        CONSTRAINT UX_wallet_user_spend_category_weights
            UNIQUE (wallet_id, user_category_id, earn_category_id)
    );
GO
```

- [ ] **Step 2: Apply the migration by starting the backend**

The migration runner runs at app startup. Start the backend dev server and watch the log for `Applying migration 024…`:

```bash
cd backend && ../.venv/bin/uvicorn app.main:app --reload --port 8000
```

Expected: log line indicating migration 024 applied successfully (or "already applied" on a re-run). Stop the server with Ctrl+C once verified.

If the migration fails, fix the SQL (most likely T-SQL syntax around `IF NOT EXISTS` / `GO` — see `CLAUDE.md` Known Pitfalls) and re-run.

- [ ] **Step 3: Verify the table exists**

Run a quick query against the dev DB to confirm the table is present. From `backend/`:

```bash
cd backend && ../.venv/bin/python -c "
import asyncio
from sqlalchemy import text
from app.database import async_session_maker

async def main():
    async with async_session_maker() as s:
        r = await s.execute(text(
            \"SELECT COUNT(*) FROM sys.objects WHERE name='wallet_user_spend_category_weights' AND type='U'\"
        ))
        print('exists:', r.scalar() == 1)

asyncio.run(main())
"
```

Expected: `exists: True`

- [ ] **Step 4: Commit**

```bash
git add backend/migrations/024_wallet_user_spend_category_weights.sql
git commit -m "Migration 024: wallet_user_spend_category_weights

Sparse per-wallet override table for UserSpendCategoryMapping weights.
Idempotent. Cascades on wallet/user-category delete."
```

---

## Task 3: Wire the model through the import surface

**Files:**
- Modify: `backend/app/dal/__init__.py`
- Modify: `backend/app/models.py`

- [ ] **Step 1: Export from `dal/__init__.py`**

In `backend/app/dal/__init__.py`, change the existing `wallet_spend` import line:

```python
from .wallet_spend import WalletSpendItem
```

to:

```python
from .wallet_spend import WalletSpendItem, WalletUserSpendCategoryWeight
```

And in the `__all__` list (after the existing `"WalletSpendItem"` entry), add:

```python
    "WalletUserSpendCategoryWeight",
```

- [ ] **Step 2: Re-export from `models.py`**

In `backend/app/models.py`, in the `from .dal import (...)` block, add `WalletUserSpendCategoryWeight,` after `WalletSpendItem,`. In the `__all__` list, add `"WalletUserSpendCategoryWeight",` after `"WalletSpendItem",`.

- [ ] **Step 3: Verify importable from both surfaces**

Run: `cd backend && ../.venv/bin/python -c "from app.models import WalletUserSpendCategoryWeight; from app.dal import WalletUserSpendCategoryWeight as W2; print(WalletUserSpendCategoryWeight is W2)"`

Expected: `True`

- [ ] **Step 4: Commit**

```bash
git add backend/app/dal/__init__.py backend/app/models.py
git commit -m "Export WalletUserSpendCategoryWeight from DAL/models"
```

---

## Task 4: Add Pydantic schemas

**Files:**
- Modify: `backend/app/schemas/spend.py`
- Modify: `backend/app/schemas/__init__.py`

- [ ] **Step 1: Append schemas to `schemas/spend.py`**

At the bottom of `backend/app/schemas/spend.py`, append:

```python
class WalletCategoryWeightRowRead(BaseModel):
    """One row in the per-user-category weight editor response."""
    model_config = ConfigDict(from_attributes=True)

    earn_category_id: int
    earn_category_name: str
    default_weight: float
    override_weight: Optional[float] = None
    effective_weight: float


class WalletCategoryWeightsRead(BaseModel):
    """Per-user-category weight editor response."""
    user_category_id: int
    user_category_name: str
    mappings: list[WalletCategoryWeightRowRead]


class WalletCategoryWeightRowWrite(BaseModel):
    """One row in the PUT body."""
    earn_category_id: int
    weight: float = Field(..., ge=0.0)


class WalletCategoryWeightsWrite(BaseModel):
    """PUT body: a list of (earn_category_id, weight) pairs to persist.

    Server normalizes weights to sum to 1.0 before persisting. Each
    earn_category_id must be in the user category's default mapping set.
    """
    weights: list[WalletCategoryWeightRowWrite]
```

The imports at the top of the file (`BaseModel`, `ConfigDict`, `Field`, `Optional`) are already present.

- [ ] **Step 2: Re-export from `schemas/__init__.py`**

In `backend/app/schemas/__init__.py`, change the existing `from .spend import (...)` block to add the four new schemas:

```python
from .spend import (
    SpendCategoryRead,
    UserSpendCategoryMappingRead,
    UserSpendCategoryRead,
    WalletCategoryWeightRowRead,
    WalletCategoryWeightRowWrite,
    WalletCategoryWeightsRead,
    WalletCategoryWeightsWrite,
    WalletSpendItemCreate,
    WalletSpendItemRead,
    WalletSpendItemUpdate,
)
```

In the `__all__` list, in the "Spend" section, add the four new names alphabetically:

```python
    "SpendCategoryRead",
    "UserSpendCategoryMappingRead",
    "UserSpendCategoryRead",
    "WalletCategoryWeightRowRead",
    "WalletCategoryWeightRowWrite",
    "WalletCategoryWeightsRead",
    "WalletCategoryWeightsWrite",
    "WalletSpendItemCreate",
    "WalletSpendItemRead",
    "WalletSpendItemUpdate",
```

- [ ] **Step 3: Verify schemas import cleanly**

Run: `cd backend && ../.venv/bin/python -c "from app.schemas import WalletCategoryWeightsRead, WalletCategoryWeightsWrite, WalletCategoryWeightRowRead; print('ok')"`

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/spend.py backend/app/schemas/__init__.py
git commit -m "Add Pydantic schemas for wallet category weight editor"
```

---

## Task 5: Add the override merge helper + unit test (TDD)

This is the pure-function core of the calculator-side change. Build it test-first because the merge logic has subtle behavior (partial overrides + normalization) and is the easiest thing in the feature to break silently.

**Files:**
- Create: `backend/app/services/wallet_category_weight_service.py` (will hold both the helper and the service in Task 6 — start with the helper)
- Create: `backend/tests/test_wallet_category_weight_merge.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_wallet_category_weight_merge.py`:

```python
"""Unit tests for the per-wallet weight override merge helper.

Pure function, no DB. Verifies the override layer + normalization
behavior the calculator relies on.
"""
from __future__ import annotations

from app.services.wallet_category_weight_service import apply_weight_overrides


def test_no_overrides_returns_defaults():
    # Travel (id=10) -> Flights (12, 0.5), Hotels (13, 0.3), Travel-other (14, 0.2)
    defaults = {
        10: [(12, "Flights", 0.5), (13, "Hotels", 0.3), (14, "Travel-other", 0.2)],
    }
    overrides: dict[tuple[int, int], float] = {}
    result = apply_weight_overrides(defaults, overrides)
    assert result == {
        10: [("Flights", 0.5), ("Hotels", 0.3), ("Travel-other", 0.2)],
    }


def test_full_override_replaces_all_weights():
    defaults = {
        10: [(12, "Flights", 0.5), (13, "Hotels", 0.3), (14, "Travel-other", 0.2)],
    }
    overrides = {
        (10, 12): 0.8,
        (10, 13): 0.1,
        (10, 14): 0.1,
    }
    result = apply_weight_overrides(defaults, overrides)
    assert result == {
        10: [("Flights", 0.8), ("Hotels", 0.1), ("Travel-other", 0.1)],
    }


def test_partial_override_mixes_with_defaults():
    # Override only Flights; Hotels and Travel-other keep their defaults.
    defaults = {
        10: [(12, "Flights", 0.5), (13, "Hotels", 0.3), (14, "Travel-other", 0.2)],
    }
    overrides = {(10, 12): 0.9}
    result = apply_weight_overrides(defaults, overrides)
    assert result == {
        10: [("Flights", 0.9), ("Hotels", 0.3), ("Travel-other", 0.2)],
    }


def test_orphan_overrides_for_missing_earn_categories_are_ignored():
    # Override row for an earn category not in the current default mapping
    # set (e.g. category was removed from YAML after override was saved).
    # Should be silently ignored — calculator only iterates the live
    # default mapping set.
    defaults = {
        10: [(12, "Flights", 0.5), (13, "Hotels", 0.5)],
    }
    overrides = {
        (10, 12): 0.7,
        (10, 99): 0.3,  # orphan — earn_category 99 not in defaults
    }
    result = apply_weight_overrides(defaults, overrides)
    assert result == {
        10: [("Flights", 0.7), ("Hotels", 0.5)],
    }


def test_overrides_for_other_user_categories_dont_leak():
    defaults = {
        10: [(12, "Flights", 0.5), (13, "Hotels", 0.5)],
        20: [(15, "Groceries", 1.0)],
    }
    overrides = {(10, 12): 0.9}  # only Travel
    result = apply_weight_overrides(defaults, overrides)
    assert result == {
        10: [("Flights", 0.9), ("Hotels", 0.5)],
        20: [("Groceries", 1.0)],
    }


def test_zero_override_is_respected():
    # Setting a weight to 0 in the editor should set it to 0 (not be
    # treated as "absence"). The calculator's later normalization
    # excludes the row by giving it 0 share.
    defaults = {
        10: [(12, "Flights", 0.5), (13, "Hotels", 0.5)],
    }
    overrides = {(10, 13): 0.0}
    result = apply_weight_overrides(defaults, overrides)
    assert result == {
        10: [("Flights", 0.5), ("Hotels", 0.0)],
    }
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_wallet_category_weight_merge.py -v`

Expected: FAIL with `ModuleNotFoundError` or `ImportError` for `app.services.wallet_category_weight_service` (file doesn't exist yet).

- [ ] **Step 3: Create the service file with the helper**

Create `backend/app/services/wallet_category_weight_service.py`:

```python
"""Per-wallet override of UserSpendCategoryMapping.default_weight.

The service exposes CRUD for the editor in the Spending tab. The
``apply_weight_overrides`` helper is pure (no DB) and is also used by
CalculatorDataService to merge override rows into the mapping
expansion before normalization.
"""
from __future__ import annotations

from typing import Iterable


def apply_weight_overrides(
    defaults_by_user_cat: dict[int, list[tuple[int, str, float]]],
    overrides: dict[tuple[int, int], float],
) -> dict[int, list[tuple[str, float]]]:
    """Merge per-wallet weight overrides into the default mapping set.

    Args:
        defaults_by_user_cat: Maps user_category_id -> list of
            (earn_category_id, earn_category_name, default_weight).
            This is the live default mapping set as loaded from
            UserSpendCategoryMapping.
        overrides: Maps (user_category_id, earn_category_id) -> weight
            from the wallet_user_spend_category_weights table.

    Returns:
        Maps user_category_id -> list of (earn_category_name, weight)
        with overrides applied. Iteration order matches the input
        defaults so the calculator's downstream normalization is stable.
        Override rows for earn_category_ids not in the current default
        set are silently ignored (they're orphans from a since-changed
        seed).
    """
    out: dict[int, list[tuple[str, float]]] = {}
    for user_cat_id, rows in defaults_by_user_cat.items():
        merged: list[tuple[str, float]] = []
        for earn_cat_id, earn_cat_name, default_weight in rows:
            weight = overrides.get((user_cat_id, earn_cat_id), default_weight)
            merged.append((earn_cat_name, weight))
        out[user_cat_id] = merged
    return out
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_wallet_category_weight_merge.py -v`

Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/wallet_category_weight_service.py backend/tests/test_wallet_category_weight_merge.py
git commit -m "Add apply_weight_overrides helper + unit tests

Pure-function merge of per-wallet weight overrides into the default
mapping set. Orphan overrides (earn_category not in current defaults)
are silently ignored. Zero is a valid override value."
```

---

## Task 6: Build the WalletCategoryWeightService (DB methods)

Append the service class to the file we just created.

**Files:**
- Modify: `backend/app/services/wallet_category_weight_service.py`
- Modify: `backend/app/services/__init__.py`

- [ ] **Step 1: Append the service class to `wallet_category_weight_service.py`**

Add the following imports at the top of the file (below the `from typing import Iterable` line):

```python
from fastapi import Depends, HTTPException
from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..constants import ALL_OTHER_CATEGORY
from ..database import get_db
from ..models import (
    UserSpendCategory,
    UserSpendCategoryMapping,
    WalletUserSpendCategoryWeight,
)
from ..schemas import (
    WalletCategoryWeightRowRead,
    WalletCategoryWeightsRead,
)
from .base import BaseService
```

Append after `apply_weight_overrides`:

```python
class WalletCategoryWeightService(BaseService[WalletUserSpendCategoryWeight]):
    """CRUD for per-wallet weight overrides + read-with-defaults helper."""

    model = WalletUserSpendCategoryWeight

    async def _get_user_category_or_404(self, user_category_id: int) -> UserSpendCategory:
        result = await self.db.execute(
            select(UserSpendCategory)
            .options(
                selectinload(UserSpendCategory.mappings)
                .selectinload(UserSpendCategoryMapping.earn_category),
            )
            .where(UserSpendCategory.id == user_category_id)
        )
        usc = result.scalar_one_or_none()
        if usc is None:
            raise HTTPException(
                status_code=404,
                detail=f"UserSpendCategory {user_category_id} not found",
            )
        return usc

    @staticmethod
    def _ensure_editable(usc: UserSpendCategory) -> None:
        """Reject housing + All Other (non-editable per UI decision)."""
        # Housing: detect by name (CalculatorDataService uses the same
        # check at line 199; there is no is_housing flag on
        # UserSpendCategory).
        if usc.name.strip().lower() == "housing":
            raise HTTPException(
                status_code=400,
                detail="Housing weights are driven by the wallet's housing_type "
                       "and cannot be edited directly.",
            )
        if usc.is_system and usc.name == ALL_OTHER_CATEGORY:
            raise HTTPException(
                status_code=400,
                detail="'All Other' has a single mapping and cannot be edited.",
            )

    async def list_overrides_for_wallet_user_category(
        self, wallet_id: int, user_category_id: int,
    ) -> list[WalletUserSpendCategoryWeight]:
        result = await self.db.execute(
            select(WalletUserSpendCategoryWeight).where(
                WalletUserSpendCategoryWeight.wallet_id == wallet_id,
                WalletUserSpendCategoryWeight.user_category_id == user_category_id,
            )
        )
        return list(result.scalars().all())

    async def list_overrides_for_wallet(
        self, wallet_id: int,
    ) -> list[WalletUserSpendCategoryWeight]:
        """Bulk fetch — used by CalculatorDataService once per compute."""
        result = await self.db.execute(
            select(WalletUserSpendCategoryWeight).where(
                WalletUserSpendCategoryWeight.wallet_id == wallet_id,
            )
        )
        return list(result.scalars().all())

    async def get_for_editor(
        self, wallet_id: int, user_category_id: int,
    ) -> WalletCategoryWeightsRead:
        """Build the editor read shape: defaults + override + effective."""
        usc = await self._get_user_category_or_404(user_category_id)
        overrides = {
            o.earn_category_id: o.weight
            for o in await self.list_overrides_for_wallet_user_category(
                wallet_id, user_category_id
            )
        }
        rows: list[WalletCategoryWeightRowRead] = []
        for mapping in usc.mappings:
            override_weight = overrides.get(mapping.earn_category_id)
            effective = (
                override_weight if override_weight is not None else mapping.default_weight
            )
            rows.append(
                WalletCategoryWeightRowRead(
                    earn_category_id=mapping.earn_category_id,
                    earn_category_name=mapping.earn_category.category,
                    default_weight=mapping.default_weight,
                    override_weight=override_weight,
                    effective_weight=effective,
                )
            )
        return WalletCategoryWeightsRead(
            user_category_id=usc.id,
            user_category_name=usc.name,
            mappings=rows,
        )

    async def save(
        self,
        wallet_id: int,
        user_category_id: int,
        weights: list[tuple[int, float]],
    ) -> WalletCategoryWeightsRead:
        """Validate, normalize, and upsert override rows.

        ``weights`` is a list of (earn_category_id, raw_weight). The
        method:
          1. Rejects 400 if user category is housing or All Other.
          2. Rejects 422 if any earn_category_id isn't in the user
             category's default mapping set.
          3. Rejects 422 if total weight <= 0 or any weight < 0.
          4. Normalizes weights to sum to 1.0.
          5. Replaces all override rows for (wallet_id, user_category_id)
             with the new set (delete-then-insert; safer than upsert
             with sparse missing rows).
        """
        usc = await self._get_user_category_or_404(user_category_id)
        self._ensure_editable(usc)

        valid_earn_ids = {m.earn_category_id for m in usc.mappings}
        seen: set[int] = set()
        for earn_id, w in weights:
            if earn_id not in valid_earn_ids:
                raise HTTPException(
                    status_code=422,
                    detail=f"earn_category_id {earn_id} is not a default "
                           f"mapping for user category {user_category_id}",
                )
            if earn_id in seen:
                raise HTTPException(
                    status_code=422,
                    detail=f"Duplicate earn_category_id {earn_id} in body",
                )
            seen.add(earn_id)
            if w < 0:
                raise HTTPException(
                    status_code=422,
                    detail="Negative weights are not allowed.",
                )

        total = sum(w for _, w in weights)
        if total <= 0:
            raise HTTPException(
                status_code=422,
                detail="Total weight must be greater than zero.",
            )

        # Delete-then-insert so we don't leave stale override rows.
        await self.db.execute(
            sa_delete(WalletUserSpendCategoryWeight).where(
                WalletUserSpendCategoryWeight.wallet_id == wallet_id,
                WalletUserSpendCategoryWeight.user_category_id == user_category_id,
            )
        )
        for earn_id, w in weights:
            self.db.add(
                WalletUserSpendCategoryWeight(
                    wallet_id=wallet_id,
                    user_category_id=user_category_id,
                    earn_category_id=earn_id,
                    weight=w / total,
                )
            )
        await self.db.flush()
        return await self.get_for_editor(wallet_id, user_category_id)

    async def reset(
        self, wallet_id: int, user_category_id: int,
    ) -> WalletCategoryWeightsRead:
        """Delete all override rows for (wallet, user_category)."""
        usc = await self._get_user_category_or_404(user_category_id)
        self._ensure_editable(usc)
        await self.db.execute(
            sa_delete(WalletUserSpendCategoryWeight).where(
                WalletUserSpendCategoryWeight.wallet_id == wallet_id,
                WalletUserSpendCategoryWeight.user_category_id == user_category_id,
            )
        )
        await self.db.flush()
        return await self.get_for_editor(wallet_id, user_category_id)


def get_wallet_category_weight_service(
    db: AsyncSession = Depends(get_db),
) -> WalletCategoryWeightService:
    """FastAPI dependency for WalletCategoryWeightService."""
    return WalletCategoryWeightService(db)
```

- [ ] **Step 2: Export from services/__init__.py**

In `backend/app/services/__init__.py`, after the existing `from .calculator_data_service import (...)` block (or anywhere alphabetically reasonable), add:

```python
from .wallet_category_weight_service import (
    WalletCategoryWeightService,
    apply_weight_overrides,
    get_wallet_category_weight_service,
)
```

In the `__all__` list, add:

```python
    "WalletCategoryWeightService",
    "apply_weight_overrides",
    "get_wallet_category_weight_service",
```

- [ ] **Step 3: Verify the service imports cleanly**

Run: `cd backend && ../.venv/bin/python -c "from app.services import WalletCategoryWeightService, apply_weight_overrides, get_wallet_category_weight_service; print('ok')"`

Expected: `ok`

- [ ] **Step 4: Re-run the helper unit tests to confirm nothing regressed**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_wallet_category_weight_merge.py -v`

Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/wallet_category_weight_service.py backend/app/services/__init__.py
git commit -m "Add WalletCategoryWeightService with editor + save + reset

Wraps the apply_weight_overrides helper for the editor endpoints.
Rejects housing and 'All Other' as non-editable. Save normalizes
weights to sum to 1.0 and replaces the override row set."
```

---

## Task 7: Add the router

**Files:**
- Create: `backend/app/routers/wallet/wallet_category_weights.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create the router**

Create `backend/app/routers/wallet/wallet_category_weights.py`:

```python
"""Per-wallet UserSpendCategoryMapping weight overrides.

Three endpoints under /wallet/category-weights/{user_category_id}:
  - GET    : current effective weights (defaults + overrides + effective)
  - PUT    : save new weights (server normalizes to sum=1)
  - DELETE : reset to defaults (delete all override rows for the pair)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth import get_current_user
from ...database import get_db
from ...models import User
from ...schemas import (
    WalletCategoryWeightsRead,
    WalletCategoryWeightsWrite,
)
from ...services import (
    WalletCategoryWeightService,
    WalletService,
    get_wallet_category_weight_service,
    get_wallet_service,
)

router = APIRouter(tags=["wallet-category-weights"])


async def _resolve_wallet_id(
    user: User,
    wallet_service: WalletService,
) -> int:
    wallet = await wallet_service.get_for_user(user.id)
    if wallet is None:
        raise HTTPException(
            status_code=404,
            detail="No wallet exists yet — fetch /wallet first to auto-create",
        )
    return wallet.id


@router.get(
    "/wallet/category-weights/{user_category_id}",
    response_model=WalletCategoryWeightsRead,
)
async def get_my_category_weights(
    user_category_id: int,
    user: User = Depends(get_current_user),
    wallet_service: WalletService = Depends(get_wallet_service),
    weight_service: WalletCategoryWeightService = Depends(
        get_wallet_category_weight_service
    ),
):
    wallet_id = await _resolve_wallet_id(user, wallet_service)
    return await weight_service.get_for_editor(wallet_id, user_category_id)


@router.put(
    "/wallet/category-weights/{user_category_id}",
    response_model=WalletCategoryWeightsRead,
)
async def save_my_category_weights(
    user_category_id: int,
    payload: WalletCategoryWeightsWrite,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    weight_service: WalletCategoryWeightService = Depends(
        get_wallet_category_weight_service
    ),
):
    wallet_id = await _resolve_wallet_id(user, wallet_service)
    weights = [(row.earn_category_id, row.weight) for row in payload.weights]
    result = await weight_service.save(wallet_id, user_category_id, weights)
    await db.commit()
    return result


@router.delete(
    "/wallet/category-weights/{user_category_id}",
    response_model=WalletCategoryWeightsRead,
)
async def reset_my_category_weights(
    user_category_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    weight_service: WalletCategoryWeightService = Depends(
        get_wallet_category_weight_service
    ),
):
    wallet_id = await _resolve_wallet_id(user, wallet_service)
    result = await weight_service.reset(wallet_id, user_category_id)
    await db.commit()
    return result
```

- [ ] **Step 2: Register in main.py**

In `backend/app/main.py`, in the `from .routers.wallet import (...)` block (around line 31), add `wallet_category_weights,` to the import list:

```python
from .routers.wallet import (
    wallet_card_instances,
    wallet_category_weights,
    wallet_spend,
    wallets,
)
```

Then add the include_router line in the wallet section (after `wallet_spend.router`):

```python
app.include_router(wallet_category_weights.router, prefix="/api")
```

- [ ] **Step 3: Verify endpoints are registered**

Start the backend dev server:

```bash
cd backend && ../.venv/bin/uvicorn app.main:app --reload --port 8000
```

In a second terminal, list the routes:

```bash
curl -s http://localhost:8000/openapi.json | ../.venv/bin/python -c "
import json, sys
spec = json.load(sys.stdin)
for path in sorted(spec['paths']):
    if 'category-weights' in path:
        print(path, list(spec['paths'][path].keys()))
"
```

Expected output:
```
/api/wallet/category-weights/{user_category_id} ['get', 'put', 'delete']
```

Stop the server (Ctrl+C).

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/wallet/wallet_category_weights.py backend/app/main.py
git commit -m "Add /wallet/category-weights/{id} GET/PUT/DELETE endpoints"
```

---

## Task 8: Wire override merge into CalculatorDataService

**Files:**
- Modify: `backend/app/services/calculator_data_service.py`

- [ ] **Step 1: Update the imports**

At the top of `backend/app/services/calculator_data_service.py`, in the `from ..models import (...)` block, add `WalletUserSpendCategoryWeight` after `UserSpendCategoryMapping`. The existing import looks like:

```python
from ..models import (
    ...
    UserSpendCategoryMapping,
    ...
)
```

After modification:

```python
from ..models import (
    ...
    UserSpendCategoryMapping,
    WalletUserSpendCategoryWeight,
    ...
)
```

Add a new import for the helper near the top of the file (with the other relative imports):

```python
from .wallet_category_weight_service import apply_weight_overrides
```

- [ ] **Step 2: Modify the mapping expansion**

The current expansion at lines 180–215 builds `mappings_by_user_cat: dict[int, list[tuple[str, float]]]` directly. We need to:
1. Build an intermediate `defaults_by_user_cat: dict[int, list[tuple[earn_cat_id, earn_cat_name, default_weight]]]` instead.
2. Load all `WalletUserSpendCategoryWeight` rows for the wallet.
3. Run `apply_weight_overrides` to produce the final `mappings_by_user_cat` shape.

Replace the block starting `# Load mappings for all user categories in one query` (around line 180) through the housing override (around line 205) with:

```python
        # Load mappings for all user categories in one query, plus the
        # wallet's per-(user_cat, earn_cat) weight overrides.
        defaults_by_user_cat: dict[int, list[tuple[int, str, float]]] = {}
        housing_user_cat_ids: set[int] = set()
        if user_cat_ids:
            mapping_result = await self.db.execute(
                select(UserSpendCategoryMapping)
                .options(
                    selectinload(UserSpendCategoryMapping.earn_category),
                    selectinload(UserSpendCategoryMapping.user_category),
                )
                .where(UserSpendCategoryMapping.user_category_id.in_(user_cat_ids))
            )
            for mapping in mapping_result.scalars().all():
                defaults_by_user_cat.setdefault(mapping.user_category_id, []).append(
                    (
                        mapping.earn_category_id,
                        mapping.earn_category.category,
                        mapping.default_weight,
                    )
                )
                if (
                    mapping.user_category is not None
                    and mapping.user_category.name.strip().lower() == "housing"
                ):
                    housing_user_cat_ids.add(mapping.user_category_id)

        override_result = await self.db.execute(
            select(WalletUserSpendCategoryWeight).where(
                WalletUserSpendCategoryWeight.wallet_id == wallet_id,
                WalletUserSpendCategoryWeight.user_category_id.in_(
                    user_cat_ids or {-1}
                ),
            )
        )
        overrides_by_pair: dict[tuple[int, int], float] = {
            (o.user_category_id, o.earn_category_id): o.weight
            for o in override_result.scalars().all()
        }

        mappings_by_user_cat = apply_weight_overrides(
            defaults_by_user_cat, overrides_by_pair
        )

        # Override the Housing USC's mappings with a 100% weight on the
        # user's chosen earn category. Other USCs are unchanged. Housing
        # is non-editable in the UI, but we still clobber here as a
        # defensive measure in case any stale override rows exist.
        for housing_uc_id in housing_user_cat_ids:
            mappings_by_user_cat[housing_uc_id] = [(housing_target, 1.0)]
```

The downstream `for item in items:` block (starting around line 207) uses `mappings_by_user_cat` which now has the same shape as before (`dict[int, list[tuple[str, float]]]`), so no further changes are needed.

The `if user_cat_ids:` guard wraps the *defaults* query but not the *overrides* query — when there are no spend items, both `defaults_by_user_cat` and `overrides_by_pair` are empty and `apply_weight_overrides` returns `{}`. The `user_cat_ids or {-1}` fallback in the override query avoids `IN ()` (some DBs reject empty IN-lists).

- [ ] **Step 3: Run the snapshot test to confirm no regression**

Per CLAUDE.md, every calculator change must keep the snapshot green:

```bash
cd backend && ../.venv/bin/python -m pytest tests/test_calculator_snapshot.py -v
```

Expected: all snapshot tests PASS. The snapshot test bypasses `CalculatorDataService` (it builds `CardData` directly), so this is really a "did I break imports / cause a crash via a side path" check. All scenarios should pass unchanged.

If any snapshot fails: investigate the diff. If a fixture genuinely needs to change (it shouldn't — this change adds a no-op default path), rerun with `--snapshot-update` and commit the fixture update as a separate commit per the project convention.

- [ ] **Step 4: Re-run the helper tests too**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_wallet_category_weight_merge.py -v`

Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/calculator_data_service.py
git commit -m "Apply wallet weight overrides in mapping expansion

CalculatorDataService now loads wallet_user_spend_category_weights
rows for the wallet being computed and merges them into the default
mapping set via apply_weight_overrides before the existing
normalization. Housing override (100% rent/mortgage) still wins as a
defensive measure — housing is non-editable in the UI but stale rows
get clobbered here."
```

---

## Task 9: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md` at `.claude/CLAUDE.md`

- [ ] **Step 1: Add the new table to the Wallet-owned section**

In `.claude/CLAUDE.md`, find the "Wallet-owned (one wallet per user):" section. After the `WalletCardCredit` bullet (and before `Scenario`), add:

```markdown
- `WalletUserSpendCategoryWeight` — per-wallet override of
  `UserSpendCategoryMapping.default_weight`, sparse: a row exists only
  when the user has customized a `(user_category, earn_category)` pair.
  Absence inherits the global default. Edited inline via the spending
  tab's per-category accordion. Housing and "All Other" are non-editable
  (server rejects with 400). The calculator merges these in via
  `apply_weight_overrides` before the existing weight normalization.
```

- [ ] **Step 2: Add a brief note in the EV Calculation section**

Find the "**Foreign spend split**:" paragraph in the "EV Calculation" section. Just *before* it, add:

```markdown
**Wallet weight overrides**: `WalletUserSpendCategoryWeight` rows let a
user customize per-`UserSpendCategory` fan-out weights into the
underlying earn categories. They're applied during mapping expansion in
`CalculatorDataService.load_spend_for_wallet` via the pure helper
`app.services.wallet_category_weight_service.apply_weight_overrides`,
which merges overrides on top of the live default mapping set. The
existing normalization then makes the merged weights sum to 1.0 per
user category. Override rows for earn categories that no longer exist
in the seeded defaults are silently ignored (the calculator only
iterates the live default set).

```

- [ ] **Step 3: Commit**

```bash
git add .claude/CLAUDE.md
git commit -m "Document WalletUserSpendCategoryWeight in CLAUDE.md"
```

---

## Task 10: Add frontend types and API client

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add types**

In `frontend/src/api/client.ts`, immediately after the `WalletSpendItem` / `UpdateWalletSpendItemPayload` types (around line 298), add:

```typescript
export interface WalletCategoryWeightRow {
  earn_category_id: number
  earn_category_name: string
  default_weight: number
  override_weight: number | null
  effective_weight: number
}

export interface WalletCategoryWeights {
  user_category_id: number
  user_category_name: string
  mappings: WalletCategoryWeightRow[]
}

export interface SaveWalletCategoryWeightsPayload {
  weights: { earn_category_id: number; weight: number }[]
}
```

- [ ] **Step 2: Add the API client block**

After the existing `walletSpendApi` block (around line 860), add:

```typescript
// ─── Wallet category weight overrides (Spending tab editor) ──────────────────

export const walletCategoryWeightsApi = {
  get: (userCategoryId: number) =>
    request<WalletCategoryWeights>(
      `/wallet/category-weights/${userCategoryId}`,
    ),
  save: (userCategoryId: number, payload: SaveWalletCategoryWeightsPayload) =>
    request<WalletCategoryWeights>(
      `/wallet/category-weights/${userCategoryId}`,
      {
        method: 'PUT',
        body: JSON.stringify(payload),
      },
    ),
  reset: (userCategoryId: number) =>
    request<WalletCategoryWeights>(
      `/wallet/category-weights/${userCategoryId}`,
      { method: 'DELETE' },
    ),
}
```

- [ ] **Step 3: Verify the file typechecks**

Run: `cd frontend && npx tsc --noEmit`

Expected: no new TypeScript errors related to `walletCategoryWeightsApi` or the new types.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "Add walletCategoryWeightsApi typed client"
```

---

## Task 11: Add the React Query key factory

**Files:**
- Modify: `frontend/src/lib/queryKeys.ts`

- [ ] **Step 1: Add the factory**

In `frontend/src/lib/queryKeys.ts`, in the "Wallet (singular)" section (just after `walletSpendItemsSingular`), add:

```typescript
  walletCategoryWeights: (userCategoryId: number) =>
    ['wallet-category-weights', userCategoryId] as const,
```

- [ ] **Step 2: Verify it typechecks**

Run: `cd frontend && npx tsc --noEmit`

Expected: no new TypeScript errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/queryKeys.ts
git commit -m "Add queryKeys.walletCategoryWeights(id) factory"
```

---

## Task 12: Build the CategoryWeightEditor component

**Files:**
- Create: `frontend/src/pages/Profile/components/CategoryWeightEditor.tsx`

- [ ] **Step 1: Write the component**

Create `frontend/src/pages/Profile/components/CategoryWeightEditor.tsx`:

```typescript
import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  walletCategoryWeightsApi,
  type WalletCategoryWeightRow,
} from '../../../api/client'
import { queryKeys } from '../../../lib/queryKeys'

interface Props {
  userCategoryId: number
  onClose: () => void
}

/**
 * Inline accordion editor for a single UserSpendCategory's per-wallet
 * weight overrides. Lazy-fetches on mount; manages a local draft;
 * Save → normalize+persist+invalidate+collapse, Cancel → discard,
 * Reset → DELETE override rows + show defaults.
 */
export function CategoryWeightEditor({ userCategoryId, onClose }: Props) {
  const queryClient = useQueryClient()

  const { data, isLoading, isError } = useQuery({
    queryKey: queryKeys.walletCategoryWeights(userCategoryId),
    queryFn: () => walletCategoryWeightsApi.get(userCategoryId),
  })

  // Draft state: earn_category_id -> typed string (percentage as integer-ish).
  const [draft, setDraft] = useState<Record<number, string>>({})
  const [submitError, setSubmitError] = useState<string | null>(null)

  // Initialize draft when data first arrives (effective_weight * 100, rounded).
  useEffect(() => {
    if (!data) return
    const init: Record<number, string> = {}
    for (const row of data.mappings) {
      init[row.earn_category_id] = String(Math.round(row.effective_weight * 100))
    }
    setDraft(init)
    setSubmitError(null)
  }, [data])

  const totalPct = useMemo(
    () =>
      Object.values(draft).reduce((sum, s) => {
        const n = parseInt(s, 10)
        return sum + (Number.isFinite(n) ? n : 0)
      }, 0),
    [draft],
  )

  const invalidateDownstream = () => {
    queryClient.invalidateQueries({
      queryKey: queryKeys.walletCategoryWeights(userCategoryId),
    })
    queryClient.invalidateQueries({ queryKey: queryKeys.walletSpendItemsSingular() })
    queryClient.invalidateQueries({ queryKey: queryKeys.myWalletWithScenarios() })
  }

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload = {
        weights: Object.entries(draft).map(([id, val]) => ({
          earn_category_id: Number(id),
          weight: Math.max(0, parseInt(val, 10) || 0),
        })),
      }
      return walletCategoryWeightsApi.save(userCategoryId, payload)
    },
    onSuccess: () => {
      invalidateDownstream()
      onClose()
    },
    onError: (err: Error) => setSubmitError(err.message),
  })

  const resetMutation = useMutation({
    mutationFn: () => walletCategoryWeightsApi.reset(userCategoryId),
    onSuccess: () => {
      invalidateDownstream()
      // Stay open so the user sees the defaults snap back.
    },
    onError: (err: Error) => setSubmitError(err.message),
  })

  const handleSave = () => {
    setSubmitError(null)
    if (totalPct <= 0) {
      setSubmitError('Total cannot be 0%.')
      return
    }
    saveMutation.mutate()
  }

  const handleReset = () => {
    if (!window.confirm(`Reset ${data?.user_category_name ?? 'category'} weights to defaults?`)) return
    setSubmitError(null)
    resetMutation.mutate()
  }

  if (isLoading) {
    return (
      <div className="px-3 py-3 text-xs text-ink-faint">Loading defaults…</div>
    )
  }
  if (isError || !data) {
    return (
      <div className="px-3 py-3 text-xs text-neg">
        Failed to load category weights.
      </div>
    )
  }

  const totalIs100 = totalPct === 100

  return (
    <div className="px-3 py-3 bg-page/40">
      <div className="flex items-center justify-between mb-2">
        <p className="text-[11px] text-ink-faint uppercase tracking-wider">
          Mix for {data.user_category_name} spend
        </p>
        <button
          type="button"
          onClick={handleReset}
          disabled={resetMutation.isPending}
          className="text-xs text-ink-muted hover:text-accent disabled:opacity-50"
        >
          Reset to defaults
        </button>
      </div>

      <div className="space-y-1.5">
        {data.mappings.map((row: WalletCategoryWeightRow) => (
          <div key={row.earn_category_id} className="flex items-center gap-3">
            <span className="text-sm text-ink-muted flex-1 min-w-0 truncate">
              {row.earn_category_name}
            </span>
            <div className="relative w-20 shrink-0">
              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                value={draft[row.earn_category_id] ?? ''}
                onChange={(e) =>
                  setDraft((prev) => ({
                    ...prev,
                    [row.earn_category_id]: e.target.value.replace(/[^0-9]/g, ''),
                  }))
                }
                className="w-full bg-surface-2 border border-divider text-ink text-sm tabular-nums text-right pr-5 pl-1.5 py-0.5 rounded outline-none focus:border-accent placeholder:text-ink-faint"
              />
              <span className="absolute right-1.5 top-1/2 -translate-y-1/2 text-xs text-ink-faint pointer-events-none">
                %
              </span>
            </div>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between mt-3">
        <span
          className={`text-xs tabular-nums ${
            totalIs100 ? 'text-ink-muted' : 'text-warn'
          }`}
        >
          Total: {totalPct}%
          {!totalIs100 && (
            <span className="ml-2 text-ink-faint">
              (will be normalized to 100% on save)
            </span>
          )}
        </span>
        <div className="flex items-center gap-2">
          {submitError && (
            <span className="text-xs text-neg">{submitError}</span>
          )}
          <button
            type="button"
            onClick={onClose}
            disabled={saveMutation.isPending}
            className="text-xs text-ink-muted hover:text-ink px-2 py-1 rounded disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saveMutation.isPending}
            className="text-xs font-medium bg-accent text-page hover:opacity-90 px-3 py-1 rounded disabled:opacity-50"
          >
            {saveMutation.isPending ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
```

The Tailwind tokens used (`bg-page`, `bg-surface-2`, `border-divider`, `text-ink`, `text-ink-muted`, `text-ink-faint`, `text-warn`, `text-neg`, `bg-accent`, `text-accent`, `text-page`) match the palette already in use across `SpendingTab.tsx` — verify by grepping the existing file if any token doesn't render correctly.

- [ ] **Step 2: Verify the component typechecks**

Run: `cd frontend && npx tsc --noEmit`

Expected: no new TypeScript errors related to `CategoryWeightEditor`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Profile/components/CategoryWeightEditor.tsx
git commit -m "Add CategoryWeightEditor accordion component

Lazy-fetches per-user-category weight defaults + overrides, manages
local draft state with live total readout, saves via normalize-on-write
PUT or resets via DELETE."
```

---

## Task 13: Wire the chevron toggle into SpendingTab

**Files:**
- Modify: `frontend/src/pages/Profile/components/SpendingTab.tsx`

- [ ] **Step 1: Add the import + state**

At the top of `SpendingTab.tsx`, add the import:

```typescript
import { CategoryWeightEditor } from './CategoryWeightEditor'
```

Inside the `SpendingTab` function, near the existing `useState` hooks (around line 15), add:

```typescript
const [expandedCategoryId, setExpandedCategoryId] = useState<number | null>(null)
```

- [ ] **Step 2: Replace the trigger inside the category cell**

Locate the existing `Popover` for the info icon (the IIFE starting around line 258). The current code shows the ⓘ for *every* category that has mappings — including Housing and All Other. We need to:
- Keep the ⓘ for Housing and All Other.
- Replace the ⓘ with a chevron toggle for everything else.

Replace the entire IIFE block in the Category cell:

```typescript
{item.user_spend_category && item.user_spend_category.mappings.length > 0 && (() => {
  const cat = item.user_spend_category
  const isHousing = cat.name.trim().toLowerCase() === 'housing'
  const isAllOther = cat.is_system && cat.name === 'All Other'
  const editable = !isHousing && !isAllOther

  if (editable) {
    const isOpen = expandedCategoryId === cat.id
    return (
      <button
        type="button"
        onClick={() =>
          setExpandedCategoryId(isOpen ? null : cat.id)
        }
        className="shrink-0 p-0.5 rounded transition-colors text-ink-faint hover:text-ink-muted hover:bg-surface-2/50"
        title={isOpen ? 'Close mix editor' : 'Edit category mix'}
        aria-expanded={isOpen}
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={`transition-transform ${isOpen ? 'rotate-90' : ''}`}
        >
          <polyline points="9 18 15 12 9 6" />
        </svg>
      </button>
    )
  }

  // Housing / All Other — keep the existing read-only info popover.
  const housingTarget = housingType === 'mortgage' ? 'Mortgage' : 'Rent'
  const displayMappings = isHousing
    ? cat.mappings.map((m) => ({
        ...m,
        default_weight:
          m.earn_category.category.trim().toLowerCase() === housingTarget.toLowerCase()
            ? 1
            : 0,
      }))
    : cat.mappings
  return (
    <Popover
      side="bottom"
      portal
      trigger={({ onClick, ref }) => (
        <button
          ref={ref as React.RefObject<HTMLButtonElement>}
          type="button"
          onClick={onClick}
          className="shrink-0 p-0.5 rounded transition-colors text-ink-faint hover:text-ink-muted hover:bg-surface-2/50"
          title="View category details"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 16v-4" />
            <path d="M12 8h.01" />
          </svg>
        </button>
      )}
    >
      <div className="space-y-3 text-xs text-ink-muted leading-relaxed">
        <h3 className="text-sm font-semibold text-ink">{cat.name}</h3>
        {cat.description && <p>{cat.description}</p>}
        <div>
          <p className="text-[10px] text-ink-faint uppercase tracking-wider mb-1.5">Includes spend on</p>
          <ul className="space-y-1">
            {displayMappings
              .sort((a, b) => b.default_weight - a.default_weight)
              .map((mapping) => (
                <li key={mapping.id} className="flex items-center justify-between">
                  <span className="text-ink-muted">{mapping.earn_category.category}</span>
                  <span className="text-ink-faint tabular-nums">
                    {Math.round(mapping.default_weight * 100)}%
                  </span>
                </li>
              ))}
          </ul>
          {isHousing && (
            <p className="text-xs text-ink-faint mt-2">
              Set by your Housing Type above. Switch to {housingTarget === 'Rent' ? 'Mortgage' : 'Rent'} to flip.
            </p>
          )}
        </div>
      </div>
    </Popover>
  )
})()}
```

- [ ] **Step 3: Render the accordion row below the category row**

The existing `spendItems.map((item) => { ... return (<tr ...>...) })` returns a single `<tr>`. We need to return a fragment with two rows: the existing row, and (when expanded) a second `<tr>` containing the editor that spans all columns.

Wrap the existing return with a fragment. Find:

```typescript
return (
  <tr key={item.id} className="border-b border-surface-2/60 last:border-b-0">
    ... existing row ...
  </tr>
)
```

Replace with:

```typescript
const isExpanded =
  item.user_spend_category != null &&
  expandedCategoryId === item.user_spend_category.id
return (
  <Fragment key={item.id}>
    <tr className="border-b border-surface-2/60 last:border-b-0">
      ... existing row contents (no key prop) ...
    </tr>
    {isExpanded && item.user_spend_category && (
      <tr className="border-b border-surface-2/60">
        <td colSpan={3} className="p-0">
          <CategoryWeightEditor
            userCategoryId={item.user_spend_category.id}
            onClose={() => setExpandedCategoryId(null)}
          />
        </td>
      </tr>
    )}
  </Fragment>
)
```

Add `Fragment` to the React import at the top of the file:

```typescript
import { Fragment, useState } from 'react'
```

(Replace the existing `import { useState } from 'react'` line.)

The existing inner `<tr>` already had `key={item.id}` — remove that key from the inner `<tr>` because the key now lives on the outer `Fragment`.

- [ ] **Step 4: Sanity-check the typecheck**

Run: `cd frontend && npx tsc --noEmit`

Expected: no new TypeScript errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Profile/components/SpendingTab.tsx
git commit -m "Replace info icon with chevron + accordion in spending tab

Editable user categories now expand to show CategoryWeightEditor.
Housing and 'All Other' keep the existing read-only info popover."
```

---

## Task 14: Manual verification (UI walkthrough)

**Files:** none — this is a manual verification step.

This feature is a UI flow against a real database; there is no API/E2E test infrastructure in the repo to extend automatically. Manual verification is the "did it work" check.

- [ ] **Step 1: Start the backend and frontend**

In two separate terminals:

```bash
# Terminal 1
cd backend && ../.venv/bin/uvicorn app.main:app --reload --port 8000

# Terminal 2
cd frontend && npm run dev
```

- [ ] **Step 2: Open the Spending tab and verify defaults**

Navigate to `http://localhost:5173/profile?tab=spending`, sign in, and:
1. Confirm a chevron (▶) appears next to most categories.
2. Confirm Housing and All Other still show the ⓘ icon (no chevron).
3. Click the chevron on a category like "Travel". The accordion expands below.
4. Verify the rows show the same percentages as the (read-only) ⓘ popover did before.
5. The "Total: 100%" readout should match.

- [ ] **Step 3: Verify Save (happy path with auto-normalize)**

Inside the Travel accordion:
1. Change the values to e.g. Flights=80, Hotels=20, Travel-other=10. Total should read "Total: 110% (will be normalized to 100% on save)".
2. Click Save. The accordion collapses.
3. Re-open the same accordion. Verify the values are now normalized — Flights should be ~73%, Hotels ~18%, Travel-other ~9% (rounded display from 80/110, 20/110, 10/110).

- [ ] **Step 4: Verify Cancel discards**

1. Open Groceries (or any other editable category).
2. Change a value.
3. Click Cancel.
4. Re-open. Values should match the last saved state (or defaults if never saved).

- [ ] **Step 5: Verify Reset to defaults**

1. With a category that has saved overrides (Travel from step 3).
2. Click "Reset to defaults".
3. Confirm the dialog.
4. The accordion stays open and the values snap back to whatever the seed file says.
5. Close and re-open — defaults are still shown.

- [ ] **Step 6: Verify all-zero rejection**

1. Open a category. Set every input to 0.
2. Click Save.
3. Inline error "Total cannot be 0%." appears; the panel does not collapse; no API request is made (check network tab if necessary).

- [ ] **Step 7: Verify Housing rejection (server-side)**

This is a defensive check — the UI should never let you reach this. From the browser console:

```javascript
fetch('/api/wallet/category-weights/<HOUSING_CATEGORY_ID>', {
  method: 'PUT',
  headers: {'Content-Type': 'application/json', Authorization: 'Bearer ' + localStorage.auth_token},
  body: JSON.stringify({weights: [{earn_category_id: 1, weight: 1}]})
}).then(r => r.json()).then(console.log)
```

(Look up the housing user_spend_category id from the categories list — query the spending tab data or run a quick DB query.)

Expected: 400 with `Housing weights are driven by the wallet's housing_type ...`.

- [ ] **Step 8: Verify the calculator picks up overrides**

1. Note the current scenario's results for a card that earns on Travel categories (e.g. Chase Sapphire Preferred earns on Flights/Hotels).
2. Save an extreme override on Travel (Flights=100, others=0).
3. Re-run the calculation in the Roadmap Tool.
4. The card's earn breakdown should shift — more points attributed to Flights, fewer to Hotels/Travel-other (assuming the card's Flights and Hotels rates differ).
5. Reset to defaults; re-run; verify earn returns to baseline.

- [ ] **Step 9: Run snapshot test once more**

Belt-and-suspenders, per CLAUDE.md:

```bash
cd backend && ../.venv/bin/python -m pytest tests/test_calculator_snapshot.py -v
```

Expected: all PASS.

- [ ] **Step 10: Commit a verification note (optional)**

If anything in steps 2–8 surfaced a bug requiring code changes, commit the fix. If everything passed, no commit needed for this task.

---

## Task 15: Final cleanup pass

- [ ] **Step 1: Search for stray TODOs introduced**

Run: `git diff main -- backend/ frontend/ | grep -i "TODO\|FIXME\|XXX"`

Expected: empty output. Fix anything that appears.

- [ ] **Step 2: Verify the full backend test suite**

```bash
cd backend && ../.venv/bin/python -m pytest -v
```

Expected: all tests PASS (including the 6 new merge tests + 14 snapshot scenarios).

- [ ] **Step 3: Verify the frontend builds**

```bash
cd frontend && npm run build
```

Expected: build succeeds, no type errors.

- [ ] **Step 4: Squash review**

Review the commit graph with `git log --oneline main..HEAD`. There should be ~12 small, well-scoped commits — one per task. No need to squash; the granularity helps reviewers.

---

## Final notes

**Test posture:** The repo's only existing automated test is the calculator snapshot test plus this PR's pure-function unit tests. There's no FastAPI test infrastructure (no httpx/TestClient + DB fixtures). Building that out is its own feature — for this PR we rely on the snapshot test for regression coverage and the manual UI walkthrough (Task 14) for happy/error path verification. If the project later grows API integration tests, the three endpoints in this PR are clean candidates to backfill (the service is small and pure-DB).

**Snapshot test contract:** Per `CLAUDE.md`, every calculator change must keep the snapshot green. This change is a no-op when no overrides exist, so the snapshot should pass unchanged in Task 8 step 3. If it doesn't, the diff is a real bug — investigate before considering `--snapshot-update`.

**Spec freshness:** The spec doc this plan implements is committed at [docs/superpowers/specs/2026-04-29-spend-category-weight-overrides-design.md](../specs/2026-04-29-spend-category-weight-overrides-design.md). If you find a place where the plan diverges from the spec (e.g. the spec said "save then re-render then collapse" — the implemented flow is "save → invalidate → collapse and rely on next-open re-render" because it's simpler), the plan is the authoritative implementation reference.
