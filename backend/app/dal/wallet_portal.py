from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .travel_portal import TravelPortal
    from .wallet import Wallet


class WalletPortalShare(Base):
    """
    Per-wallet per-travel-portal share. Determines what fraction of the
    wallet's spend in portal-eligible categories (e.g., Travel, Hotels) is
    treated as booked through that portal — and thus eligible for the
    portal-only multipliers on the cards belonging to that TravelPortal.

    A wallet has at most one row per portal. share is in [0, 1]. The default
    behavior when no row exists is share=0, which means portal-only
    multipliers contribute nothing until the user explicitly opts in.

    Cards belong to a portal via the travel_portal_cards association table —
    issuer is no longer the linking concept.
    """

    __tablename__ = "wallet_portal_shares"
    __table_args__ = (UniqueConstraint("wallet_id", "travel_portal_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_id: Mapped[int] = mapped_column(
        ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False
    )
    travel_portal_id: Mapped[int] = mapped_column(
        ForeignKey("travel_portals.id", ondelete="CASCADE"), nullable=False
    )
    share: Mapped[float] = mapped_column(Float, nullable=False)

    wallet: Mapped["Wallet"] = relationship()
    travel_portal: Mapped["TravelPortal"] = relationship()

    def __repr__(self) -> str:
        return f"<WalletPortalShare w={self.wallet_id} portal={self.travel_portal_id} share={self.share}>"
