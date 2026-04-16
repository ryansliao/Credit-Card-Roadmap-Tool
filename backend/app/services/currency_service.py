"""Currency data access service."""

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models import Currency
from .base import BaseService


class CurrencyService(BaseService[Currency]):
    """Service for Currency operations."""

    model = Currency

    async def list_all_with_conversions(self) -> list[Currency]:
        """List all currencies with conversion relationships loaded.

        Returns:
            List of currencies ordered by name.
        """
        result = await self.db.execute(
            select(Currency)
            .options(selectinload(Currency.converts_to_currency))
            .order_by(Currency.name)
        )
        return list(result.scalars().all())


def get_currency_service(db: AsyncSession = Depends(get_db)) -> CurrencyService:
    """FastAPI dependency for CurrencyService."""
    return CurrencyService(db)
