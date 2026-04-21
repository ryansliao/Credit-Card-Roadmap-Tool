"""Spend category endpoints (reference data)."""

from fastapi import APIRouter, Depends

from ...schemas import SpendCategoryRead, UserSpendCategoryRead
from ...services import (
    SpendCategoryService,
    UserSpendCategoryService,
    get_spend_category_service,
    get_user_spend_category_service,
)

router = APIRouter(tags=["spend"])


@router.get("/app-spend-categories", response_model=list[SpendCategoryRead])
async def list_app_spend_categories(
    spend_service: SpendCategoryService = Depends(get_spend_category_service),
):
    """Return top-level earn categories with their children nested (excludes system catch-all)."""
    return await spend_service.list_app_categories()


@router.get("/user-spend-categories", response_model=list[UserSpendCategoryRead])
async def list_user_spend_categories(
    user_spend_service: UserSpendCategoryService = Depends(get_user_spend_category_service),
):
    """List all user spend categories (simplified 16 categories for user input)."""
    return await user_spend_service.list_all()


@router.get("/user-spend-categories/input", response_model=list[UserSpendCategoryRead])
async def list_user_spend_categories_for_input(
    user_spend_service: UserSpendCategoryService = Depends(get_user_spend_category_service),
):
    """List user spend categories for input (excludes system 'All Other')."""
    return await user_spend_service.list_for_input()
