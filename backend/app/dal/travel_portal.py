from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .card import Card


class TravelPortal(Base):
    """
    A travel booking portal (e.g. Chase Travel, Amex Travel, Capital One Travel).

    A portal owns the list of cards whose portal-only multipliers should be
    treated as earnable. The user's wallet sets a per-portal share to control
    what fraction of category spend is treated as booked through that portal.
    """

    __tablename__ = "travel_portals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)

    cards: Mapped[list["Card"]] = relationship(
        secondary="travel_portal_cards", back_populates="travel_portals"
    )

    def __repr__(self) -> str:
        return f"<TravelPortal id={self.id} name={self.name!r}>"
