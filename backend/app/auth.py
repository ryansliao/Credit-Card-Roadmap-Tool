"""Authentication: Google Sign-In, local credentials, JWT sessions, and FastAPI dependencies."""

from __future__ import annotations

import importlib
import os
import re
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from pydantic import BaseModel, EmailStr
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .models import User

router = APIRouter(tags=["auth"])

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 30

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,30}$")


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------


def _hash_password(password: str) -> str:
    bcrypt_mod = importlib.import_module("bcrypt")
    return bcrypt_mod.hashpw(password.encode(), bcrypt_mod.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    bcrypt_mod = importlib.import_module("bcrypt")
    return bcrypt_mod.checkpw(password.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class GoogleSignInRequest(BaseModel):
    credential: str


class LocalRegisterRequest(BaseModel):
    username: str
    # Email is optional. The frontend sends ``null`` (or omits the field) when
    # the user leaves it blank; we coerce empty strings to ``None`` in the
    # endpoint so an EmailStr validation error doesn't fire on "".
    email: EmailStr | None = None
    password: str


class LocalLoginRequest(BaseModel):
    # Username or email — the login endpoint matches against either column.
    identifier: str
    password: str


class SetUsernameRequest(BaseModel):
    username: str


class AuthUserResponse(BaseModel):
    id: int
    username: str | None = None
    name: str
    email: str | None = None
    picture: str | None = None
    token: str | None = None
    needs_username: bool = False


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


def _create_jwt(user_id: int, email: str | None) -> str:
    payload: dict = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    if email:
        payload["email"] = email
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

    # 1. Find existing user by google_id
    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()

    if not user:
        # 2. Check if a user with this email already exists (local account) — link it
        email_result = await db.execute(select(User).where(User.email == email))
        existing_by_email = email_result.scalar_one_or_none()

        if existing_by_email:
            existing_by_email.google_id = google_id
            existing_by_email.name = name
            existing_by_email.picture = picture
            user = existing_by_email
        else:
            # 3. Adopt legacy user if exactly one exists with a placeholder google_id
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
                # 4. Create brand-new user
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
        username=user.username,
        name=user.name,
        email=user.email,
        picture=user.picture,
        token=token,
        needs_username=user.username is None,
    )


@router.post("/auth/register", response_model=AuthUserResponse)
async def local_register(body: LocalRegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user with a username, optional email, and password."""
    if not JWT_SECRET:
        raise HTTPException(status_code=500, detail="JWT_SECRET not configured")

    if not USERNAME_RE.match(body.username):
        raise HTTPException(
            status_code=400,
            detail="Username must be 3-30 characters: letters, numbers, underscores only",
        )
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    # Email-only uniqueness check when one was provided. NULL is allowed for
    # any number of users so we skip the check entirely when omitted.
    if body.email is not None:
        existing = await db.execute(select(User).where(User.email == body.email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Email already in use")

    # Check username uniqueness
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already taken")

    user = User(
        username=body.username,
        name=body.username,
        email=body.email,
        password_hash=_hash_password(body.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = _create_jwt(user.id, user.email)
    return AuthUserResponse(
        id=user.id,
        username=user.username,
        name=user.name,
        email=user.email,
        picture=user.picture,
        token=token,
    )


@router.post("/auth/login", response_model=AuthUserResponse)
async def local_login(body: LocalLoginRequest, db: AsyncSession = Depends(get_db)):
    """Sign in with username-or-email and password."""
    if not JWT_SECRET:
        raise HTTPException(status_code=500, detail="JWT_SECRET not configured")

    identifier = body.identifier.strip()
    if not identifier:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Match against either column. ``email`` is unique per non-NULL value and
    # ``username`` is globally unique, so at most one row can match.
    result = await db.execute(
        select(User).where(or_(User.username == identifier, User.email == identifier))
    )
    user = result.scalar_one_or_none()

    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not _verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = _create_jwt(user.id, user.email)
    return AuthUserResponse(
        id=user.id,
        username=user.username,
        name=user.name,
        email=user.email,
        picture=user.picture,
        token=token,
    )


@router.patch("/auth/username", response_model=AuthUserResponse)
async def set_username(
    body: SetUsernameRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set or update the username for the current user."""
    if not USERNAME_RE.match(body.username):
        raise HTTPException(
            status_code=400,
            detail="Username must be 3-30 characters: letters, numbers, underscores only",
        )

    existing = await db.execute(
        select(User).where(User.username == body.username, User.id != user.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already taken")

    user.username = body.username
    await db.commit()
    await db.refresh(user)

    return AuthUserResponse(
        id=user.id,
        username=user.username,
        name=user.name,
        email=user.email,
        picture=user.picture,
    )


@router.get("/auth/me", response_model=AuthUserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Return the currently authenticated user (validates the JWT)."""
    return AuthUserResponse(
        id=user.id,
        username=user.username,
        name=user.name,
        email=user.email,
        picture=user.picture,
        needs_username=user.username is None,
    )
