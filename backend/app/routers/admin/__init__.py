"""Admin CRUD routers for reference data.

All routes mounted under this router require ``is_admin=True`` on the
authenticated user. The gate is attached here as a router-level
dependency so individual handlers cannot accidentally ship without it.
"""

from fastapi import APIRouter, Depends

from ...auth import require_admin_user
from .reference import router as reference_router
from .cards import router as cards_router
from .multiplier_groups import router as multiplier_groups_router
from .rotating import router as rotating_router

router = APIRouter(
    tags=["admin"],
    dependencies=[Depends(require_admin_user)],
)

router.include_router(reference_router)
router.include_router(cards_router)
router.include_router(multiplier_groups_router)
router.include_router(rotating_router)
