"""Credit library data access service."""

from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models import CardCredit, Credit
from .base import BaseService
from .card_service import CardService


class CreditService(BaseService[Credit]):
    """Service for Credit and CardCredit operations."""

    model = Credit

    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self._card_service = CardService(db)

    async def list_all_with_links(self) -> list[Credit]:
        """List every credit (system + every user). Admin/seed use only."""
        result = await self.db.execute(
            select(Credit)
            .options(selectinload(Credit.card_links))
            .order_by(Credit.credit_name)
        )
        return list(result.scalars().all())

    async def list_visible_to_user(self, user_id: int) -> list[Credit]:
        """List credits this user can see: system credits + their own."""
        result = await self.db.execute(
            select(Credit)
            .options(selectinload(Credit.card_links))
            .where(or_(Credit.owner_user_id.is_(None), Credit.owner_user_id == user_id))
            .order_by(Credit.credit_name)
        )
        return list(result.scalars().all())

    async def get_with_links(self, credit_id: int) -> Optional[Credit]:
        """Fetch a credit with card links eager-loaded.

        Args:
            credit_id: The credit ID.

        Returns:
            The credit if found, None otherwise.
        """
        result = await self.db.execute(
            select(Credit)
            .options(selectinload(Credit.card_links))
            .where(Credit.id == credit_id)
        )
        return result.scalar_one_or_none()

    async def get_or_404(self, credit_id: int) -> Credit:
        """Fetch a credit by ID or raise 404.

        Args:
            credit_id: The credit ID.

        Returns:
            The credit.

        Raises:
            HTTPException: 404 if not found.
        """
        result = await self.db.execute(
            select(Credit)
            .options(selectinload(Credit.card_links))
            .where(Credit.id == credit_id)
        )
        credit = result.scalar_one_or_none()
        if not credit:
            raise HTTPException(
                status_code=404,
                detail=f"Credit {credit_id} not found",
            )
        return credit

    async def get_by_name(
        self, name: str, owner_user_id: Optional[int] = None
    ) -> Optional[Credit]:
        """Find a credit by (owner, name).

        ``owner_user_id`` of None scopes to the system library; passing a user
        id scopes to that user's credits. Names are unique within an owner via
        the composite index, so at most one row matches.
        """
        result = await self.db.execute(
            select(Credit).where(
                Credit.credit_name == name,
                Credit.owner_user_id.is_(None) if owner_user_id is None
                else Credit.owner_user_id == owner_user_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        credit_name: str,
        value: float,
        card_ids: list[int],
        excludes_first_year: bool = False,
        is_one_time: bool = False,
        credit_currency_id: Optional[int] = None,
        card_values: Optional[dict[int, float]] = None,
        owner_user_id: Optional[int] = None,
    ) -> Credit:
        """Create a new credit with card links.

        ``owner_user_id`` of None creates a system credit (admin path);
        passing a user id creates a user-scoped credit. Uniqueness on
        ``credit_name`` is enforced within the owning scope only.
        """
        name = credit_name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="credit_name cannot be empty")

        existing = await self.get_by_name(name, owner_user_id=owner_user_id)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Credit '{name}' already exists",
            )

        validated_ids = await self._card_service.validate_ids(card_ids)

        credit = Credit(
            credit_name=name,
            value=value,
            excludes_first_year=excludes_first_year,
            is_one_time=is_one_time,
            credit_currency_id=credit_currency_id,
            owner_user_id=owner_user_id,
        )
        self.db.add(credit)
        await self.db.flush()

        await self.set_card_links(credit, validated_ids, card_values)
        return credit

    async def update(
        self,
        credit: Credit,
        credit_name: Optional[str] = None,
        value: Optional[float] = None,
        excludes_first_year: Optional[bool] = None,
        is_one_time: Optional[bool] = None,
        credit_currency_id: Optional[int] = None,
        card_ids: Optional[list[int]] = None,
        card_values: Optional[dict[int, float]] = None,
        value_is_set: bool = False,
        credit_currency_id_is_set: bool = False,
    ) -> Credit:
        """Update a credit's fields and/or card links.

        Args:
            credit: The credit to update.
            credit_name: New name (optional).
            value: New default value (optional).
            excludes_first_year: New excludes_first_year flag (optional).
            is_one_time: New is_one_time flag (optional).
            credit_currency_id: New currency ID (optional).
            card_ids: New list of card IDs (optional, replaces existing).
            card_values: Per-card value overrides (optional).
            value_is_set: Whether value was explicitly set in payload.
            credit_currency_id_is_set: Whether credit_currency_id was explicitly set.

        Returns:
            The updated credit.

        Raises:
            HTTPException: 400 if name is empty, 409 if name conflicts.
        """
        if value_is_set:
            credit.value = value

        if excludes_first_year is not None:
            credit.excludes_first_year = excludes_first_year

        if is_one_time is not None:
            credit.is_one_time = is_one_time

        if credit_currency_id_is_set:
            credit.credit_currency_id = credit_currency_id

        if credit_name is not None:
            new_name = credit_name.strip()
            if not new_name:
                raise HTTPException(status_code=400, detail="credit_name cannot be empty")

            if new_name != credit.credit_name:
                # Uniqueness is per-owner; clash check stays within scope.
                owner_filter = (
                    Credit.owner_user_id.is_(None)
                    if credit.owner_user_id is None
                    else Credit.owner_user_id == credit.owner_user_id
                )
                clash = await self.db.execute(
                    select(Credit).where(
                        Credit.credit_name == new_name,
                        Credit.id != credit.id,
                        owner_filter,
                    )
                )
                if clash.scalar_one_or_none():
                    raise HTTPException(
                        status_code=409,
                        detail=f"Credit name {new_name!r} already exists",
                    )
            credit.credit_name = new_name

        if card_ids is not None:
            validated_ids = await self._card_service.validate_ids(card_ids)
            await self.set_card_links(credit, validated_ids, card_values)
        elif card_values is not None:
            # Update per-card values without changing the card list
            for link in credit.card_links:
                if link.card_id in card_values:
                    link.value = card_values[link.card_id]

        return credit

    async def set_card_links(
        self,
        credit: Credit,
        card_ids: list[int],
        card_values: Optional[dict[int, float]] = None,
    ) -> None:
        """Replace a credit's card links with the given card IDs.

        Preserves existing per-card values for cards that remain.

        Args:
            credit: The credit to update.
            card_ids: New list of card IDs.
            card_values: Optional per-card value overrides.
        """
        # Query existing links explicitly rather than touching
        # ``credit.card_links``. The relationship may not be loaded on a
        # freshly-flushed Credit, and lazy-loading it would do sync IO
        # outside the async greenlet (MissingGreenlet).
        existing_links = (
            await self.db.execute(
                select(CardCredit).where(CardCredit.credit_id == credit.id)
            )
        ).scalars().all()
        existing_values: dict[int, float | None] = {
            link.card_id: link.value for link in existing_links
        }

        await self.db.execute(
            delete(CardCredit).where(CardCredit.credit_id == credit.id)
        )

        merged_values = {**existing_values, **(card_values or {})}
        for cid in card_ids:
            self.db.add(
                CardCredit(
                    credit_id=credit.id,
                    card_id=cid,
                    value=merged_values.get(cid),
                )
            )


def get_credit_service(db: AsyncSession = Depends(get_db)) -> CreditService:
    """FastAPI dependency for CreditService."""
    return CreditService(db)
