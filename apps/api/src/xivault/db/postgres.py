"""PostgreSQL asyncpg implementation of XiVault repository."""

import datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg

from xivault.db.repository import BaseRepository
from xivault.exceptions import ConflictException, QuotaExceededException


class PostgresRepository(BaseRepository):
    """PostgreSQL repository using asyncpg connection pool."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, username, password_hash, created_at, disabled_at "
                "FROM public.users WHERE lower(username) = lower($1)",
                username,
            )
            return dict(row) if row else None

    async def get_user_by_id(self, user_id: UUID) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, username, password_hash, created_at, disabled_at "
                "FROM public.users WHERE id = $1",
                user_id,
            )
            return dict(row) if row else None

    async def create_user_with_quota(
        self, username: str, password_hash: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_row = await conn.fetchrow(
                    "INSERT INTO public.users (username, password_hash) "
                    "VALUES ($1, $2) RETURNING id, username, created_at",
                    username,
                    password_hash,
                )
                user_id = user_row["id"]
                quota_row = await conn.fetchrow(
                    "INSERT INTO public.user_quotas (user_id, used_bytes, quota_bytes) "
                    "VALUES ($1, 0, 5242880) RETURNING used_bytes, quota_bytes",
                    user_id,
                )
                user = dict(user_row)
                quota = {
                    "used_bytes": quota_row["used_bytes"],
                    "quota_bytes": quota_row["quota_bytes"],
                    "remaining_bytes": quota_row["quota_bytes"] - quota_row["used_bytes"],
                }
                return user, quota

    async def get_user_quota(self, user_id: UUID) -> dict[str, int]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT used_bytes, quota_bytes FROM public.user_quotas WHERE user_id = $1",
                user_id,
            )
            if not row:
                return {"used_bytes": 0, "quota_bytes": 5242880, "remaining_bytes": 5242880}
            return {
                "used_bytes": row["used_bytes"],
                "quota_bytes": row["quota_bytes"],
                "remaining_bytes": row["quota_bytes"] - row["used_bytes"],
            }

    async def create_refresh_session(
        self, user_id: UUID, token_hash: str, expires_at: datetime.datetime
    ) -> UUID:
        async with self.pool.acquire() as conn:
            session_id = await conn.fetchval(
                "INSERT INTO public.refresh_sessions (user_id, token_hash, expires_at) "
                "VALUES ($1, $2, $3) RETURNING id",
                user_id,
                token_hash,
                expires_at,
            )
            return UUID(str(session_id))

    async def get_refresh_session_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, user_id, token_hash, expires_at, revoked_at, replaced_by, created_at "
                "FROM public.refresh_sessions WHERE token_hash = $1",
                token_hash,
            )
            return dict(row) if row else None

    async def rotate_refresh_session(
        self,
        old_session_id: UUID,
        user_id: UUID,
        new_token_hash: str,
        new_expires_at: datetime.datetime,
    ) -> UUID:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                new_session_id = uuid4()
                now = datetime.datetime.now(datetime.timezone.utc)
                await conn.execute(
                    "UPDATE public.refresh_sessions "
                    "SET revoked_at = $1, replaced_by = $2, last_used_at = $1 "
                    "WHERE id = $3",
                    now,
                    new_session_id,
                    old_session_id,
                )
                await conn.execute(
                    "INSERT INTO public.refresh_sessions (id, user_id, token_hash, expires_at) "
                    "VALUES ($1, $2, $3, $4)",
                    new_session_id,
                    user_id,
                    new_token_hash,
                    new_expires_at,
                )
                return new_session_id

    async def revoke_all_user_sessions(self, user_id: UUID) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE public.refresh_sessions SET revoked_at = now() "
                "WHERE user_id = $1 AND revoked_at IS NULL",
                user_id,
            )

    async def revoke_refresh_session(self, token_hash: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE public.refresh_sessions SET revoked_at = now() "
                "WHERE token_hash = $1 AND revoked_at IS NULL",
                token_hash,
            )

    async def commit_uploaded_file(
        self,
        user_id: UUID,
        display_path: str,
        storage_key: str,
        language: str,
        content_type: str,
        byte_size: int,
        sha256: str,
        indexed_content: str | None,
        file_content: str | None = None,
    ) -> dict[str, Any]:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Lock quota row atomically
                quota_row = await conn.fetchrow(
                    "SELECT used_bytes, quota_bytes FROM public.user_quotas "
                    "WHERE user_id = $1 FOR UPDATE",
                    user_id,
                )
                if not quota_row or (quota_row["used_bytes"] + byte_size) > quota_row["quota_bytes"]:
                    raise QuotaExceededException("Uploading this file would exceed your 5 MiB storage quota.")

                try:
                    file_row = await conn.fetchrow(
                        "INSERT INTO public.files "
                        "(owner_id, display_path, storage_key, language, content_type, byte_size, sha256, indexed_content, file_content) "
                        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) "
                        "RETURNING id, display_path, language, content_type, byte_size, sha256, created_at, updated_at",
                        user_id,
                        display_path,
                        storage_key,
                        language,
                        content_type,
                        byte_size,
                        sha256,
                        indexed_content,
                        file_content,
                    )
                except asyncpg.UniqueViolationError as err:
                    raise ConflictException(
                        code="duplicate_file",
                        message="An identical file is already stored in your vault.",
                    ) from err

                await conn.execute(
                    "UPDATE public.user_quotas "
                    "SET used_bytes = used_bytes + $1, updated_at = now() "
                    "WHERE user_id = $2",
                    byte_size,
                    user_id,
                )
                return dict(file_row)

    async def list_files(
        self, user_id: UUID, limit: int = 25, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        async with self.pool.acquire() as conn:
            if cursor and "|" in cursor:
                cursor_time_str, cursor_id_str = cursor.split("|", 1)
                cursor_time = datetime.datetime.fromisoformat(cursor_time_str)
                cursor_id = UUID(cursor_id_str)
                rows = await conn.fetch(
                    "SELECT id, display_path, language, byte_size, created_at "
                    "FROM public.files WHERE owner_id = $1 AND (created_at, id) < ($2, $3) "
                    "ORDER BY created_at DESC, id DESC LIMIT $4",
                    user_id,
                    cursor_time,
                    cursor_id,
                    limit,
                )
            else:
                rows = await conn.fetch(
                    "SELECT id, display_path, language, byte_size, created_at "
                    "FROM public.files WHERE owner_id = $1 "
                    "ORDER BY created_at DESC, id DESC LIMIT $2",
                    user_id,
                    limit,
                )
            items = [dict(r) for r in rows]
            next_cursor = (
                f"{items[-1]['created_at'].isoformat()}|{items[-1]['id']}"
                if len(items) == limit
                else None
            )
            return items, next_cursor

    async def search_files(
        self, user_id: UUID, query: str, limit: int = 25, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        async with self.pool.acquire() as conn:
            sql = (
                "SELECT id, display_path, language, byte_size, created_at, "
                "ts_headline('simple', coalesce(indexed_content, ''), websearch_to_tsquery('simple', $2), "
                "'StartSel=<b>, StopSel=</b>, MaxWords=35, MinWords=15') as excerpt "
                "FROM public.files "
                "WHERE owner_id = $1 AND search_vector @@ websearch_to_tsquery('simple', $2) "
                "ORDER BY ts_rank(search_vector, websearch_to_tsquery('simple', $2)) DESC, created_at DESC "
                "LIMIT $3"
            )
            rows = await conn.fetch(sql, user_id, query, limit)
            return [dict(r) for r in rows], None

    async def get_file_by_id(self, file_id: UUID, user_id: UUID) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, owner_id, display_path, storage_key, language, content_type, byte_size, sha256, created_at, file_content "
                "FROM public.files WHERE id = $1 AND owner_id = $2",
                file_id,
                user_id,
            )
            return dict(row) if row else None

    async def delete_file(self, file_id: UUID, user_id: UUID) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "DELETE FROM public.files WHERE id = $1 AND owner_id = $2 "
                    "RETURNING id, storage_key, byte_size",
                    file_id,
                    user_id,
                )
                if row:
                    await conn.execute(
                        "UPDATE public.user_quotas "
                        "SET used_bytes = GREATEST(0, used_bytes - $1), updated_at = now() "
                        "WHERE user_id = $2",
                        row["byte_size"],
                        user_id,
                    )
                    return dict(row)
                return None
