"""Base service class with common CRUD patterns."""

from typing import Generic, TypeVar, Type, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class BaseService(Generic[T]):
    """Base service providing common database operations.

    Subclasses must set the `model` class attribute to the ORM model class.
    Services receive an AsyncSession via constructor and do NOT commit -
    the router is responsible for committing the transaction.
    """

    model: Type[T]

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, id: int, options: list | None = None) -> Optional[T]:
        """Fetch a single entity by primary key.

        Args:
            id: The primary key value.
            options: Optional list of SQLAlchemy loader options (e.g., selectinload).

        Returns:
            The entity if found, None otherwise.
        """
        stmt = select(self.model).where(self.model.id == id)
        if options:
            stmt = stmt.options(*options)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_404(self, id: int, options: list | None = None) -> T:
        """Fetch a single entity by primary key, raising 404 if not found.

        Args:
            id: The primary key value.
            options: Optional list of SQLAlchemy loader options.

        Returns:
            The entity.

        Raises:
            HTTPException: 404 if the entity is not found.
        """
        entity = await self.get_by_id(id, options)
        if not entity:
            raise HTTPException(
                status_code=404,
                detail=f"{self.model.__name__} {id} not found",
            )
        return entity

    async def list_all(self, options: list | None = None) -> list[T]:
        """Fetch all entities of this type.

        Args:
            options: Optional list of SQLAlchemy loader options.

        Returns:
            List of all entities.
        """
        stmt = select(self.model)
        if options:
            stmt = stmt.options(*options)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, entity: T) -> None:
        """Mark an entity for deletion.

        Does not commit - the router must call db.commit().
        """
        await self.db.delete(entity)
