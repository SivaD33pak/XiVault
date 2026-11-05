"""Unit tests verifying security hardening, leak prevention, and failsafe behavior."""

import pytest
from pydantic import ValidationError

from xivault.config import Settings
from xivault.exceptions import (
    ConflictException,
    QuotaExceededException,
    RateLimitedException,
)
from xivault.services.rate_limiter import SlidingWindowRateLimiter


def test_production_jwt_secret_validation() -> None:
    """Production mode must reject default or insecure JWT secret."""
    with pytest.raises(ValidationError) as excinfo:
        Settings(
            xivault_env="production",
            xivault_jwt_secret="DEV_INSECURE_SECRET_CHANGE_ME_IN_PRODUCTION_MIN_32_BYTES",
        )
    assert "CRITICAL SECURITY CONFIGURATION ERROR" in str(excinfo.value)

    # Short secret must also be rejected in production
    with pytest.raises(ValidationError):
        Settings(
            xivault_env="production",
            xivault_jwt_secret="too_short_secret",
        )

    # Valid secret in production must succeed
    valid = Settings(
        xivault_env="production",
        xivault_jwt_secret="a_very_secure_and_sufficiently_long_production_secret_32_chars!",
    )
    assert valid.xivault_env == "production"

    # Development mode allows dev secret
    dev = Settings(
        xivault_env="development",
        xivault_jwt_secret="DEV_INSECURE_SECRET_CHANGE_ME_IN_PRODUCTION_MIN_32_BYTES",
    )
    assert dev.xivault_env == "development"


def test_rate_limiter_prunes_stale_keys_and_prevents_memory_leak() -> None:
    """Rate limiter must purge inactive keys to prevent unbounded memory growth."""
    limiter = SlidingWindowRateLimiter(max_tracked_keys=5)

    # Insert timestamps for 10 distinct keys with older timestamps
    old_time = 1000.0
    for i in range(10):
        limiter.windows[f"key_{i}"] = [old_time]

    assert len(limiter.windows) == 10

    # Prune stale entries at current time = 10000.0 (past 1 hour cutoff)
    limiter.prune_stale(now=10000.0)
    assert len(limiter.windows) == 0

    # Test limit enforcement
    limiter.reset()
    for _ in range(5):
        limiter.check("user_1", max_requests=5, window_seconds=60)

    with pytest.raises(RateLimitedException):
        limiter.check("user_1", max_requests=5, window_seconds=60)


@pytest.mark.asyncio
async def test_repository_atomic_duplicate_and_quota_enforcement() -> None:
    """Repository commit_uploaded_file must reject duplicates and over-quota atomically."""
    from xivault.db.repository import InMemoryRepository

    repo = InMemoryRepository()
    user, quota = await repo.create_user_with_quota("alice", "dummy_hash")
    user_id = user["id"]

    # Upload first file
    await repo.commit_uploaded_file(
        user_id=user_id,
        display_path="src/main.py",
        storage_key=f"{user_id}/file1",
        language="python",
        content_type="text/x-python",
        byte_size=100,
        sha256="abc123hash",
        indexed_content="print('hello')",
        file_content="print('hello')",
    )

    # Duplicate upload must raise ConflictException
    with pytest.raises(ConflictException) as excinfo:
        await repo.commit_uploaded_file(
            user_id=user_id,
            display_path="src/main.py",
            storage_key=f"{user_id}/file2",
            language="python",
            content_type="text/x-python",
            byte_size=100,
            sha256="abc123hash",
            indexed_content="print('hello')",
            file_content="print('hello')",
        )
    assert excinfo.value.code == "duplicate_file"

    # Quota exhaustion must raise QuotaExceededException
    with pytest.raises(QuotaExceededException):
        await repo.commit_uploaded_file(
            user_id=user_id,
            display_path="src/huge.bin",
            storage_key=f"{user_id}/file3",
            language="text",
            content_type="text/plain",
            byte_size=6 * 1024 * 1024,  # 6 MiB > 5 MiB quota
            sha256="hugehash",
            indexed_content="",
            file_content="",
        )


@pytest.mark.asyncio
async def test_repository_keyset_cursor_pagination() -> None:
    """Repository list_files must paginate correctly using composite cursor."""
    from xivault.db.repository import InMemoryRepository

    repo = InMemoryRepository()
    user, _ = await repo.create_user_with_quota("bob", "dummy_hash")
    user_id = user["id"]

    for i in range(5):
        await repo.commit_uploaded_file(
            user_id=user_id,
            display_path=f"file_{i}.txt",
            storage_key=f"{user_id}/file_{i}.txt",
            language="plaintext",
            content_type="text/plain",
            byte_size=10,
            sha256=f"hash_{i}",
            indexed_content=f"content {i}",
            file_content=f"content {i}",
        )

    # First page of 2 items
    p1_items, next_cursor = await repo.list_files(user_id=user_id, limit=2)
    assert len(p1_items) == 2
    assert next_cursor is not None

    # Second page of 2 items using next_cursor
    p2_items, next_cursor2 = await repo.list_files(user_id=user_id, limit=2, cursor=next_cursor)
    assert len(p2_items) == 2
    assert p1_items[0]["id"] != p2_items[0]["id"]
    assert next_cursor2 is not None

    # Third page (remaining 1 item)
    p3_items, next_cursor3 = await repo.list_files(user_id=user_id, limit=2, cursor=next_cursor2)
    assert len(p3_items) == 1
    assert next_cursor3 is None
