"""Currency endpoints."""

from fastapi import APIRouter, Depends

from ..schemas import CurrencyRead
from ..services import CurrencyService, get_currency_service

router = APIRouter(tags=["currencies"])


@router.get("/currencies", response_model=list[CurrencyRead])
async def list_currencies(
    currency_service: CurrencyService = Depends(get_currency_service),
):
    """List all currencies."""
    return await currency_service.list_all_with_conversions()
