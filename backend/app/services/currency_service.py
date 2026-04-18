"""Currency data access service."""

from fastapi import Depends, HTTPException
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

    async def get_by_name(self, name: str) -> Currency | None:
        result = await self.db.execute(select(Currency).where(Currency.name == name))
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        name: str,
        reward_kind: str,
        cents_per_point: float,
        partner_transfer_rate: float | None,
        cash_transfer_rate: float,
        converts_to_currency_id: int | None,
        converts_at_rate: float,
        no_transfer_cpp: float | None,
        no_transfer_rate: float | None,
    ) -> Currency:
        """Create a Currency, validating name uniqueness and conversion target.

        Does not commit — the router commits after successful creation.
        """
        name = name.strip()
        if await self.get_by_name(name):
            raise HTTPException(
                status_code=409, detail=f"Currency '{name}' already exists"
            )
        if converts_to_currency_id is not None:
            target = await self.get_by_id(converts_to_currency_id)
            if not target:
                raise HTTPException(
                    status_code=404,
                    detail=f"Target currency id={converts_to_currency_id} not found",
                )
        currency = Currency(
            name=name,
            reward_kind=reward_kind,
            cents_per_point=cents_per_point,
            partner_transfer_rate=partner_transfer_rate,
            cash_transfer_rate=cash_transfer_rate,
            converts_to_currency_id=converts_to_currency_id,
            converts_at_rate=converts_at_rate,
            no_transfer_cpp=no_transfer_cpp,
            no_transfer_rate=no_transfer_rate,
        )
        self.db.add(currency)
        return currency


def get_currency_service(db: AsyncSession = Depends(get_db)) -> CurrencyService:
    """FastAPI dependency for CurrencyService."""
    return CurrencyService(db)
