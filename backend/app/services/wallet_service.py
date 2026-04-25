"""Wallet and WalletCard data access service."""

from datetime import date, datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models import (
    Card,
    Credit,
    User,
    Wallet,
    WalletCard,
    WalletCardCredit,
)
from ..schemas import WalletCardCreate, InitialWalletCardCredit
from .base import BaseService


class WalletService(BaseService[Wallet]):
    """Service for Wallet and WalletCard operations."""

    model = Wallet

    @staticmethod
    def wallet_load_opts():
        """Eager-load options for wallet with cards."""
        wc_chain = selectinload(Wallet.wallet_cards)
        wc_card = wc_chain.selectinload(WalletCard.card)
        wc_credits = wc_chain.selectinload(WalletCard.credit_overrides_rows)
        return [
            wc_credits,
            wc_credits.selectinload(WalletCardCredit.library_credit).selectinload(
                Credit.credit_currency
            ),
            wc_card,
            wc_card.selectinload(Card.issuer),
            wc_card.selectinload(Card.network_tier),
        ]

    async def get_user_wallet(self, wallet_id: int, user: User) -> Wallet:
        """Load a wallet by ID and verify it belongs to the given user.

        Args:
            wallet_id: The wallet ID to load.
            user: The authenticated user.

        Returns:
            The wallet if found and owned by the user.

        Raises:
            HTTPException: 404 if wallet doesn't exist, 403 if owned by another user.
        """
        wallet = await self.get_by_id(wallet_id)
        if not wallet:
            raise HTTPException(
                status_code=404,
                detail=f"Wallet {wallet_id} not found",
            )
        if wallet.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not your wallet")
        return wallet

    async def list_for_user(self, user_id: int) -> list[Wallet]:
        """List all wallets for a user with eager-loaded relationships.

        Args:
            user_id: The user's ID.

        Returns:
            List of wallets with wallet_cards eager-loaded.
        """
        result = await self.db.execute(
            select(Wallet)
            .options(*self.wallet_load_opts())
            .where(Wallet.user_id == user_id)
            .order_by(Wallet.id)
        )
        return list(result.scalars().all())

    async def list_summaries_for_user(self, user_id: int) -> list[Wallet]:
        """List wallets for a user without eager-loading nested relationships.

        Returned rows are intended for the WalletSummary schema (id/name/
        description only) — used by the wallet picker dropdown.
        """
        result = await self.db.execute(
            select(Wallet)
            .where(Wallet.user_id == user_id)
            .order_by(Wallet.id)
        )
        return list(result.scalars().all())

    async def get_for_user(self, user_id: int) -> Optional[Wallet]:
        """Get the user's single wallet with eager-loaded relationships.

        Args:
            user_id: The user's ID.

        Returns:
            The user's wallet if it exists, None otherwise.
        """
        result = await self.db.execute(
            select(Wallet)
            .options(*self.wallet_load_opts())
            .where(Wallet.user_id == user_id)
            .order_by(Wallet.id)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def user_has_wallet(self, user_id: int) -> bool:
        """Check if user already has a wallet.

        Args:
            user_id: The user's ID.

        Returns:
            True if user has a wallet, False otherwise.
        """
        result = await self.db.execute(
            select(Wallet.id).where(Wallet.user_id == user_id).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def get_with_cards(self, wallet_id: int) -> Wallet:
        """Load a wallet with all card relationships eager-loaded.

        Args:
            wallet_id: The wallet ID.

        Returns:
            The wallet with relationships loaded.

        Raises:
            HTTPException: 404 if not found.
        """
        result = await self.db.execute(
            select(Wallet)
            .options(*self.wallet_load_opts())
            .where(Wallet.id == wallet_id)
        )
        wallet = result.scalar_one_or_none()
        if not wallet:
            raise HTTPException(
                status_code=404,
                detail=f"Wallet {wallet_id} not found",
            )
        return wallet

    async def create(
        self,
        user_id: int,
        name: str,
        description: Optional[str] = None,
        as_of_date: Optional[date] = None,
    ) -> Wallet:
        """Create a new wallet for the user.

        Args:
            user_id: The owner's user ID.
            name: Wallet name.
            description: Optional description.
            as_of_date: Optional reference date.

        Returns:
            The newly created wallet (not yet committed).
        """
        wallet = Wallet(
            user_id=user_id,
            name=name,
            description=description,
            as_of_date=as_of_date,
        )
        self.db.add(wallet)
        await self.db.flush()
        return wallet

    async def update(self, wallet: Wallet, **updates) -> Wallet:
        """Update wallet fields.

        Args:
            wallet: The wallet to update.
            **updates: Field names and values to update.

        Returns:
            The updated wallet.
        """
        for field, value in updates.items():
            if value is not None:
                setattr(wallet, field, value)
        return wallet

    async def get_wallet_card(
        self,
        wallet_id: int,
        card_id: int,
    ) -> Optional[WalletCard]:
        """Find a WalletCard by wallet and card ID.

        Args:
            wallet_id: The wallet ID.
            card_id: The card ID.

        Returns:
            The WalletCard if found, None otherwise.
        """
        result = await self.db.execute(
            select(WalletCard).where(
                WalletCard.wallet_id == wallet_id,
                WalletCard.card_id == card_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_wallet_card_or_404(
        self,
        wallet_id: int,
        card_id: int,
    ) -> WalletCard:
        """Find a WalletCard or raise 404.

        Args:
            wallet_id: The wallet ID.
            card_id: The card ID.

        Returns:
            The WalletCard.

        Raises:
            HTTPException: 404 if not found.
        """
        wc = await self.get_wallet_card(wallet_id, card_id)
        if not wc:
            raise HTTPException(
                status_code=404,
                detail=f"Card {card_id} not in wallet {wallet_id}",
            )
        return wc

    async def get_wallet_card_with_credits(
        self,
        wallet_card_id: int,
    ) -> WalletCard:
        """Reload a WalletCard with its credit overrides (and each override's
        library credit + currency) eager-loaded.

        Used by mutating endpoints that return ``WalletCardRead`` — the read
        schema needs ``credit_overrides_rows[].library_credit.credit_currency``
        to split credit totals by currency kind.
        """
        result = await self.db.execute(
            select(WalletCard)
            .options(
                selectinload(WalletCard.credit_overrides_rows)
                .selectinload(WalletCardCredit.library_credit)
                .selectinload(Credit.credit_currency)
            )
            .where(WalletCard.id == wallet_card_id)
        )
        wc = result.scalar_one_or_none()
        if not wc:
            raise HTTPException(
                status_code=404,
                detail=f"Wallet card {wallet_card_id} not found",
            )
        return wc

    async def get_card_or_404(self, card_id: int) -> Card:
        """Fetch a Card with issuer and network_tier eager-loaded.

        Args:
            card_id: The card ID.

        Returns:
            The card with relationships loaded.

        Raises:
            HTTPException: 404 if not found.
        """
        result = await self.db.execute(
            select(Card)
            .where(Card.id == card_id)
            .options(selectinload(Card.issuer), selectinload(Card.network_tier))
        )
        card = result.scalar_one_or_none()
        if not card:
            raise HTTPException(
                status_code=404,
                detail=f"Card {card_id} not found",
            )
        return card

    async def add_card_to_wallet(
        self,
        wallet_id: int,
        payload: WalletCardCreate,
    ) -> WalletCard:
        """Add a card to a wallet.

        Args:
            wallet_id: The wallet ID (must already be verified for ownership).
            payload: The card creation payload.

        Returns:
            The newly created WalletCard.

        Raises:
            HTTPException: 404 if card not found, 409 if card already in wallet.
        """
        # Validate card exists
        await self.get_card_or_404(payload.card_id)

        # Check for duplicates
        existing = await self.get_wallet_card(wallet_id, payload.card_id)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Card {payload.card_id} is already in wallet {wallet_id}",
            )

        # Create wallet card
        wc_obj = WalletCard(
            wallet_id=wallet_id,
            card_id=payload.card_id,
            added_date=payload.added_date,
            sub_points=payload.sub_points,
            sub_min_spend=payload.sub_min_spend,
            sub_months=payload.sub_months,
            sub_spend_earn=payload.sub_spend_earn,
            annual_bonus=payload.annual_bonus,
            annual_bonus_percent=payload.annual_bonus_percent,
            annual_bonus_first_year_only=payload.annual_bonus_first_year_only,
            years_counted=payload.years_counted,
            annual_fee=payload.annual_fee,
            first_year_fee=payload.first_year_fee,
            sub_earned_date=payload.sub_earned_date,
            closed_date=payload.closed_date,
            acquisition_type=payload.acquisition_type,
            pc_from_card_id=(
                payload.pc_from_card_id
                if payload.acquisition_type == "product_change"
                else None
            ),
            panel=payload.panel,
            is_enabled=payload.is_enabled,
        )
        self.db.add(wc_obj)
        await self.db.flush()

        # Add credits if provided
        if payload.credits:
            await self._add_wallet_card_credits(wc_obj.id, payload.credits)

        # Handle product change marking
        if payload.acquisition_type == "product_change" and payload.pc_from_card_id:
            await self._mark_product_changed(
                wallet_id, payload.pc_from_card_id, payload.added_date
            )

        return wc_obj

    async def _add_wallet_card_credits(
        self,
        wallet_card_id: int,
        credits: list[InitialWalletCardCredit],
    ) -> None:
        """Add credit overrides to a wallet card.

        Args:
            wallet_card_id: The WalletCard ID.
            credits: List of credit entries to add.

        Raises:
            HTTPException: 404 if any credit ID is invalid.
        """
        lib_ids = {c.library_credit_id for c in credits}
        lib_rows = await self.db.execute(select(Credit).where(Credit.id.in_(lib_ids)))
        valid_ids = {row.id for row in lib_rows.scalars()}

        for entry in credits:
            if entry.library_credit_id not in valid_ids:
                raise HTTPException(
                    status_code=404,
                    detail=f"Credit id={entry.library_credit_id} not found in library",
                )
            self.db.add(
                WalletCardCredit(
                    wallet_card_id=wallet_card_id,
                    library_credit_id=entry.library_credit_id,
                    value=entry.value,
                )
            )

    async def _mark_product_changed(
        self,
        wallet_id: int,
        from_card_id: int,
        changed_date: date,
    ) -> None:
        """Mark a card as product-changed on a given date.

        The from-card is also closed on that date — product-change means the
        original account no longer exists, so the calculator needs to stop
        counting its earn/fees from that point. Respects any earlier manual
        close_date the user may have set.

        Args:
            wallet_id: The wallet ID.
            from_card_id: The card that was product-changed.
            changed_date: The date of the product change.
        """
        from_wc = await self.get_wallet_card(wallet_id, from_card_id)
        if from_wc:
            from_wc.product_changed_date = changed_date
            if from_wc.closed_date is None or from_wc.closed_date > changed_date:
                from_wc.closed_date = changed_date

    async def update_wallet_card(
        self,
        wc: WalletCard,
        **updates,
    ) -> WalletCard:
        """Update wallet card fields.

        Args:
            wc: The WalletCard to update.
            **updates: Field names and values to update.

        Returns:
            The updated WalletCard.
        """
        for field, value in updates.items():
            setattr(wc, field, value)
        return wc

    async def remove_card_from_wallet(self, wc: WalletCard) -> None:
        """Remove a card from a wallet.

        Args:
            wc: The WalletCard to remove.
        """
        await self.db.delete(wc)
        await self.db.flush()

    async def save_calc_window(
        self,
        wallet: Wallet,
        start: date,
        end: Optional[date],
        duration_years: int,
        duration_months: int,
        window_mode: str,
    ) -> None:
        """Persist the calc-window config used for a results call."""
        wallet.calc_start_date = start
        wallet.calc_end_date = end
        wallet.calc_duration_years = duration_years
        wallet.calc_duration_months = duration_months
        wallet.calc_window_mode = window_mode

    async def save_last_calc_snapshot(
        self,
        wallet: Wallet,
        snapshot_json: str,
    ) -> None:
        """Cache the last results-payload JSON and stamp the time."""
        wallet.last_calc_snapshot = snapshot_json
        wallet.last_calc_timestamp = datetime.now(timezone.utc)

    async def set_projected_sub_earn_date(
        self,
        wc: WalletCard,
        projected: Optional[date],
    ) -> None:
        """Update a WalletCard's projected SUB earn date if it changed."""
        if wc.sub_projected_earn_date != projected:
            wc.sub_projected_earn_date = projected


def get_wallet_service(db: AsyncSession = Depends(get_db)) -> WalletService:
    """FastAPI dependency for WalletService."""
    return WalletService(db)
