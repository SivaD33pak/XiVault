"""Integration tests verifying PostgresRepository SQL queries against PostgreSQL."""

from uuid import uuid4

import asyncpg
import pytest

from xivault.config import settings
from xivault.db.postgres import PostgresRepository
from xivault.exceptions import ConflictException


def is_live_db_available() -> bool:
    """Check if a real PostgreSQL URL is configured and accessible."""
    return bool(settings.database_url and "localhost" not in settings.database_url)


@pytest.mark.skipif(not is_live_db_available(), reason="Live PostgreSQL database not configured")
@pytest.mark.asyncio
async def test_postgres_repository_live_lifecycle() -> None:
    """Verify live asyncpg SQL queries: user creation, upload, conflict, and search."""
    ssl_setting = "require" if "supabase.co" in settings.database_url else None
    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=2, ssl=ssl_setting)
    assert pool is not None

    repo = PostgresRepository(pool)
    random_suffix = uuid4().hex[:8]
    username = f"test_user_{random_suffix}"
    dummy_hash = "$argon2id$v=19$m=65536,t=3,p=4$dummyhash"

    created_user_id = None
    try:
        # 1. Test create_user_with_quota
        user, quota = await repo.create_user_with_quota(username, dummy_hash)
        created_user_id = user["id"]
        assert user["username"] == username
        assert quota["used_bytes"] == 0
        assert quota["quota_bytes"] == 5242880

        # 2. Test commit_uploaded_file
        file_record = await repo.commit_uploaded_file(
            user_id=created_user_id,
            display_path="src/calc.py",
            storage_key=f"{created_user_id}/calc.py",
            language="python",
            content_type="text/x-python",
            byte_size=128,
            sha256="testsha256sum123456789",
            indexed_content="def add_numbers(a, b): return a + b",
            file_content="def add_numbers(a, b): return a + b",
        )
        assert file_record["display_path"] == "src/calc.py"

        # 3. Test duplicate upload raises ConflictException (from Postgres UNIQUE constraint)
        with pytest.raises(ConflictException) as excinfo:
            await repo.commit_uploaded_file(
                user_id=created_user_id,
                display_path="src/calc.py",
                storage_key=f"{created_user_id}/calc2.py",
                language="python",
                content_type="text/x-python",
                byte_size=128,
                sha256="testsha256sum123456789",
                indexed_content="def add_numbers(a, b): return a + b",
                file_content="def add_numbers(a, b): return a + b",
            )
        assert excinfo.value.code == "duplicate_file"

        # 4. Test search_files using live websearch_to_tsquery and ts_headline
        search_results, _ = await repo.search_files(
            user_id=created_user_id,
            query="add_numbers",
            limit=5,
        )
        assert len(search_results) == 1
        assert search_results[0]["display_path"] == "src/calc.py"
        assert "<b>add</b>" in search_results[0]["excerpt"]

    finally:
        # Clean up test records
        if created_user_id:
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM public.files WHERE owner_id = $1", created_user_id)
                await conn.execute("DELETE FROM public.user_quotas WHERE user_id = $1", created_user_id)
                await conn.execute("DELETE FROM public.users WHERE id = $1", created_user_id)
        await pool.close()
