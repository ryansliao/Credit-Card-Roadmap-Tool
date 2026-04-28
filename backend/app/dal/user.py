from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .wallet import Wallet


class User(Base):
    """User model — authenticated via Google Sign-In or local credentials."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[Optional[str]] = mapped_column(String(40), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="Default User")
    google_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    # Email is optional — users can register with just a username + password.
    # Uniqueness across non-NULL values is enforced by the filtered index
    # ``UX_users_email_notnull`` (see migration 007). We deliberately don't set
    # ``unique=True`` here because that would emit a plain UNIQUE constraint,
    # which in SQL Server treats NULL as a single value and would reject more
    # than one email-less user.
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    picture: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Gates the /admin/* reference-data routers. Flip via DB only.
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    wallets: Mapped[list["Wallet"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} name={self.name!r} email={self.email!r}>"
