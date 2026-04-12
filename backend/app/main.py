"""
FastAPI application entry point.

All endpoint handlers live in ``routers/``. This module wires them together
with the app instance, middleware, startup seeds, and SPA serving.
"""

from __future__ import annotations

import contextlib
import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .database import create_tables
from .auth import router as auth_router
from .routers import (
    admin,
    cards,
    credits,
    currencies,
    issuers,
    spend,
    travel_portals,
    wallet_category_priorities,
    wallet_credits,
    wallet_currencies,
    wallet_groups,
    wallet_multipliers,
    wallet_portals,
    wallet_results,
    wallet_spend,
    wallets,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield


app = FastAPI(
    title="CardSolver API",
    description="CardSolver — fees, points, credits, and SUB opportunity cost.",
    version="3.0.0",
    lifespan=lifespan,
)

_allowed_origins = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ---------------------------------------------------------------------------
# Register routers
# ---------------------------------------------------------------------------

app.include_router(auth_router)
app.include_router(issuers.router)
app.include_router(currencies.router)
app.include_router(cards.router)
app.include_router(credits.router)
app.include_router(spend.router)
app.include_router(travel_portals.router)
app.include_router(wallets.router)
app.include_router(wallet_spend.router)
app.include_router(wallet_currencies.router)
app.include_router(wallet_credits.router)
app.include_router(wallet_multipliers.router)
app.include_router(wallet_groups.router)
app.include_router(wallet_category_priorities.router)
app.include_router(wallet_portals.router)
app.include_router(wallet_results.router)
app.include_router(admin.router)


# ---------------------------------------------------------------------------
# Serve React SPA (must come last — catches all unmatched routes)
# ---------------------------------------------------------------------------

_FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"

if _FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str):
    index = _FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    raise HTTPException(
        status_code=404,
        detail="Frontend not built. Run: cd frontend && npm run build",
    )
