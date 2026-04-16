"""Admin CRUD routers for reference data."""

from fastapi import APIRouter

from .reference import router as reference_router
from .cards import router as cards_router
from .multiplier_groups import router as multiplier_groups_router
from .rotating import router as rotating_router

router = APIRouter(tags=["admin"])

router.include_router(reference_router)
router.include_router(cards_router)
router.include_router(multiplier_groups_router)
router.include_router(rotating_router)
