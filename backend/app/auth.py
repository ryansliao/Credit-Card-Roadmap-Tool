"""Google Sign-In authentication: token verification, JWT sessions, and FastAPI dependencies."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .models import User

router = APIRouter(tags=["auth"])

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 30


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class GoogleSignInRequest(BaseModel):
    credential: str


class AuthUserResponse(BaseModel):
    id: int
    name: str
    email: str
    picture: str | None = None
    token: str | None = None


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


def _create_jwt(user_id: int, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ---------------------------------------------------------------------------
# FastAPI dependency: get current user from Bearer token
# ---------------------------------------------------------------------------


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = auth_header[7:]
    claims = _decode_jwt(token)
    user_id = int(claims["sub"])

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/auth/google", response_model=AuthUserResponse)
async def google_sign_in(body: GoogleSignInRequest, db: AsyncSession = Depends(get_db)):
    """Exchange a Google Sign-In credential (ID token) for a JWT session token."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID not configured")
    if not JWT_SECRET:
        raise HTTPException(status_code=500, detail="JWT_SECRET not configured")

    try:
        idinfo = google_id_token.verify_oauth2_token(
            body.credential,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google credential")

    google_id = idinfo["sub"]
    email = idinfo.get("email", "")
    name = idinfo.get("name", email)
    picture = idinfo.get("picture")

    # Find existing user by google_id
    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()

    if not user:
        # Adopt legacy user if exactly one exists with a placeholder google_id
        legacy_result = await db.execute(
            select(User).where(User.google_id.like("legacy_%"))
        )
        legacy_user = legacy_result.scalar_one_or_none()
        if legacy_user:
            legacy_user.google_id = google_id
            legacy_user.email = email
            legacy_user.name = name
            legacy_user.picture = picture
            user = legacy_user
        else:
            user = User(
                google_id=google_id,
                email=email,
                name=name,
                picture=picture,
            )
            db.add(user)
            await db.flush()

    else:
        # Update profile fields on each sign-in
        user.email = email
        user.name = name
        user.picture = picture

    await db.commit()
    await db.refresh(user)

    token = _create_jwt(user.id, user.email)
    return AuthUserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        picture=user.picture,
        token=token,
    )


@router.get("/auth/me", response_model=AuthUserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Return the currently authenticated user (validates the JWT)."""
    return AuthUserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        picture=user.picture,
    )
