"""API dependencies for authentication and request lifecycle."""

from typing import Any
from uuid import UUID

from fastapi import Depends, Header, Request

from xivault.db.repository import BaseRepository
from xivault.db.session import get_repository
from xivault.exceptions import ForbiddenException, UnauthorizedException
from xivault.services.security import decode_access_token


async def get_current_user(
    authorization: str | None = Header(default=None),
    repo: BaseRepository = Depends(get_repository),
) -> dict[str, Any]:
    """Validate Bearer JWT and return active user object."""
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedException("Missing or malformed Authorization header.")

    token = authorization.split(" ", 1)[1]
    claims = decode_access_token(token)
    user_id_str = claims.get("sub")
    if not user_id_str:
        raise UnauthorizedException("Invalid token claims.")

    try:
        user_uuid = UUID(user_id_str)
    except (ValueError, TypeError):
        raise UnauthorizedException("Invalid user ID in token claims.") from None

    user = await repo.get_user_by_id(user_uuid)
    if not user:
        raise UnauthorizedException("User not found.")

    if user.get("disabled_at"):
        raise ForbiddenException("User account is disabled.")

    return user


def get_client_ip(request: Request) -> str:
    """Extract socket client IP for rate limiting without trusting spoofable headers."""
    return request.client.host if request.client else "127.0.0.1"
