"""Per-wallet override of UserSpendCategoryMapping.default_weight.

The service exposes CRUD for the editor in the Spending tab. The
``apply_weight_overrides`` helper is pure (no DB) and is also used by
CalculatorDataService to merge override rows into the mapping
expansion before normalization.
"""
from __future__ import annotations

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
        """Unfiltered fetch of every override row for the wallet.

        Used by the wallet response so the frontend roadmap signature
        flips when any weight is edited. (The calculator inlines its own
        query filtered by the user_cat_ids actually present in spend
        items — it doesn't need to see overrides for unspent categories.)
        """
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
        for mapping in sorted(usc.mappings, key=lambda m: m.earn_category.category):
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
