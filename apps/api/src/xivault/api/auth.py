"""Authentication API routes."""

import datetime
from typing import Any

from fastapi import APIRouter, Depends, Request, Response

from xivault.api.deps import get_client_ip, get_current_user
from xivault.db.repository import BaseRepository
from xivault.db.session import get_repository
from xivault.exceptions import (
    ConflictException,
    ForbiddenException,
    InvalidCredentialsException,
    InvalidRefreshTokenException,
    RefreshTokenReuseException,
)
from xivault.schemas import (
    LoginRequest,
    LogoutRequest,
    QuotaPublic,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserPublic,
)
from xivault.services.rate_limiter import rate_limiter
from xivault.services.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201, response_model=RegisterResponse)
async def register(
    payload: RegisterRequest,
    request: Request,
    repo: BaseRepository = Depends(get_repository),
) -> Any:
    """Register a new developer account and initialize 15 MiB storage quota."""
    client_ip = get_client_ip(request)
    rate_limiter.check(f"register:{client_ip}", max_requests=10, window_seconds=900)

    # Check for existing user
    existing = await repo.get_user_by_username(payload.username)
    if existing:
        raise ConflictException(code="username_taken", message="Username is already taken.")

    password_hash = hash_password(payload.password)
    user, quota = await repo.create_user_with_quota(payload.username, password_hash)

    return {
        "user": UserPublic(id=user["id"], username=user["username"], created_at=user["created_at"]),
        "quota": QuotaPublic(
            used_bytes=quota["used_bytes"],
            quota_bytes=quota["quota_bytes"],
            remaining_bytes=quota["remaining_bytes"],
        ),
    }


@router.post("/login", status_code=200, response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    repo: BaseRepository = Depends(get_repository),
) -> Any:
    """Authenticate credentials and issue 15-minute access JWT + rotating refresh token."""
    rate_limiter.check(f"login:user:{payload.username.lower()}", max_requests=5, window_seconds=900)

    user = await repo.get_user_by_username(payload.username)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise InvalidCredentialsException()

    if user.get("disabled_at"):
        raise ForbiddenException("Account is disabled.")

    # Create rotating refresh session (30 days)
    refresh_token = generate_refresh_token()
    token_hash = hash_token(refresh_token)
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)
    session_id = await repo.create_refresh_session(user["id"], token_hash, expires_at)

    access_token = create_access_token(user_id=str(user["id"]), session_id=str(session_id))

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": 900,
        "refresh_token": refresh_token,
        "user": UserPublic(id=user["id"], username=user["username"]),
    }


@router.post("/refresh", status_code=200, response_model=TokenResponse)
async def refresh_tokens(
    payload: RefreshRequest,
    request: Request,
    repo: BaseRepository = Depends(get_repository),
) -> Any:
    """Rotate refresh token and issue new 15-minute access token."""
    client_ip = get_client_ip(request)
    rate_limiter.check(f"refresh:{client_ip}", max_requests=20, window_seconds=900)

    token_hash = hash_token(payload.refresh_token)
    session = await repo.get_refresh_session_by_hash(token_hash)
    if not session:
        raise InvalidRefreshTokenException()

    # Replay attack detection: token was already revoked
    if session.get("revoked_at") is not None:
        await repo.revoke_all_user_sessions(session["user_id"])
        raise RefreshTokenReuseException()

    now = datetime.datetime.now(datetime.timezone.utc)
    if session["expires_at"] < now:
        raise InvalidRefreshTokenException("Refresh token expired.")

    user = await repo.get_user_by_id(session["user_id"])
    if not user or user.get("disabled_at"):
        raise ForbiddenException("User account is inactive or disabled.")

    new_refresh_token = generate_refresh_token()
    new_token_hash = hash_token(new_refresh_token)
    new_expires_at = now + datetime.timedelta(days=30)

    new_session_id = await repo.rotate_refresh_session(
        old_session_id=session["id"],
        user_id=user["id"],
        new_token_hash=new_token_hash,
        new_expires_at=new_expires_at,
    )

    new_access_token = create_access_token(user_id=str(user["id"]), session_id=str(new_session_id))

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": 900,
        "refresh_token": new_refresh_token,
        "user": UserPublic(id=user["id"], username=user["username"]),
    }


@router.post("/logout", status_code=204)
async def logout(
    payload: LogoutRequest,
    _current_user: dict[str, Any] = Depends(get_current_user),
    repo: BaseRepository = Depends(get_repository),
) -> Response:
    """Revoke the presented refresh token."""
    token_hash = hash_token(payload.refresh_token)
    await repo.revoke_refresh_session(token_hash)
    return Response(status_code=204)
