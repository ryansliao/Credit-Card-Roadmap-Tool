"""Spend category endpoints (reference data)."""

from fastapi import APIRouter, Depends

from ..schemas import SpendCategoryRead
from ..services import SpendCategoryService, get_spend_category_service

router = APIRouter(tags=["spend"])


@router.get("/spend", response_model=list[SpendCategoryRead])
async def list_spend(
    spend_service: SpendCategoryService = Depends(get_spend_category_service),
):
    return await spend_service.list_all()


@router.get("/app-spend-categories", response_model=list[SpendCategoryRead])
async def list_app_spend_categories(
    spend_service: SpendCategoryService = Depends(get_spend_category_service),
):
    """Return top-level spend categories with their children nested (excludes system catch-all)."""
    return await spend_service.list_app_categories()
