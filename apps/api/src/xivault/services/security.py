"""Security, cryptography, and token handling."""

import hashlib
import secrets
import time
import uuid
from typing import Any

import jwt
from pwdlib import PasswordHash

from xivault.config import settings
from xivault.exceptions import UnauthorizedException

# Argon2id via recommended pwdlib configuration
pwd_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash password using Argon2id."""
    return pwd_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against Argon2id hash in constant time."""
    try:
        return pwd_hasher.verify(plain_password, hashed_password)
    except Exception:
        return False


def create_access_token(user_id: str, session_id: str, expires_in_seconds: int = 900) -> str:
    """Generate a signed JWT access token (15 minutes)."""
    now = int(time.time())
    payload = {
        "sub": user_id,
        "sid": session_id,
        "iat": now,
        "exp": now + expires_in_seconds,
        "iss": settings.xivault_jwt_issuer,
        "aud": settings.xivault_jwt_audience,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.xivault_jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    """Validate and decode a JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.xivault_jwt_secret,
            algorithms=["HS256"],
            issuer=settings.xivault_jwt_issuer,
            audience=settings.xivault_jwt_audience,
            options={"require": ["sub", "sid", "iat", "exp", "iss", "aud", "jti"]},
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise UnauthorizedException("Access token has expired.") from None
    except jwt.PyJWTError:
        raise UnauthorizedException("Invalid access token.") from None


def generate_refresh_token() -> str:
    """Generate cryptographically secure opaque refresh token (at least 32 bytes)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Generate SHA-256 hash for database storage of refresh tokens."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
