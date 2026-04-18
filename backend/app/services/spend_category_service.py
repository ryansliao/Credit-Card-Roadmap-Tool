"""Spend category data access service."""

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models import SpendCategory
from .base import BaseService


class SpendCategoryService(BaseService[SpendCategory]):
    """Service for SpendCategory operations."""

    model = SpendCategory

    async def create(
        self,
        *,
        category: str,
        is_housing: bool,
        is_foreign_eligible: bool,
    ) -> SpendCategory:
        """Create a SpendCategory, validating name uniqueness."""
        category = category.strip()
        existing = await self.db.execute(
            select(SpendCategory).where(SpendCategory.category == category)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail=f"SpendCategory '{category}' already exists",
            )
        sc = SpendCategory(
            category=category,
            is_housing=is_housing,
            is_foreign_eligible=is_foreign_eligible,
        )
        self.db.add(sc)
        return sc

    async def list_all(self, options: list | None = None) -> list[SpendCategory]:
        """List all spend categories ordered by name.

        Args:
            options: Optional eager-load options.

        Returns:
            List of spend categories.
        """
        stmt = select(SpendCategory).order_by(SpendCategory.category)
        if options:
            stmt = stmt.options(*options)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_app_categories(self) -> list[SpendCategory]:
        """List top-level spend categories with children nested.

        Excludes system categories (like "All Other").

        Returns:
            List of top-level categories with children eager-loaded.
        """
        result = await self.db.execute(
            select(SpendCategory)
            .options(
                selectinload(SpendCategory.children).selectinload(SpendCategory.children),
            )
            .where(
                SpendCategory.parent_id == None,  # noqa: E711
                SpendCategory.is_system == False,  # noqa: E712
            )
            .order_by(SpendCategory.category)
        )
        return list(result.scalars().all())


def get_spend_category_service(db: AsyncSession = Depends(get_db)) -> SpendCategoryService:
    """FastAPI dependency for SpendCategoryService."""
    return SpendCategoryService(db)
