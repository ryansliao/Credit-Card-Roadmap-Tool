"""Issuer data access service."""

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models import Issuer, IssuerApplicationRule
from .base import BaseService


class IssuerService(BaseService[Issuer]):
    """Service for Issuer and IssuerApplicationRule operations."""

    model = Issuer

    async def list_all(self, options: list | None = None) -> list[Issuer]:
        """List all issuers ordered by name.

        Args:
            options: Optional eager-load options.

        Returns:
            List of issuers.
        """
        stmt = select(Issuer).order_by(Issuer.name)
        if options:
            stmt = stmt.options(*options)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create(self, name: str) -> Issuer:
        """Create a new Issuer with a conflict check on name.

        Does not commit — the router commits after successful creation.
        """
        name = name.strip()
        existing = await self.db.execute(select(Issuer).where(Issuer.name == name))
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=409, detail=f"Issuer '{name}' already exists"
            )
        issuer = Issuer(name=name)
        self.db.add(issuer)
        return issuer

    async def list_application_rules(self) -> list[IssuerApplicationRule]:
        """List all issuer application rules with issuer eager-loaded.

        Returns:
            List of application rules ordered by issuer and rule name.
        """
        result = await self.db.execute(
            select(IssuerApplicationRule)
            .options(selectinload(IssuerApplicationRule.issuer))
            .order_by(
                IssuerApplicationRule.issuer_id,
                IssuerApplicationRule.rule_name,
            )
        )
        return list(result.scalars().all())


def get_issuer_service(db: AsyncSession = Depends(get_db)) -> IssuerService:
    """FastAPI dependency for IssuerService."""
    return IssuerService(db)
