"""Database repository abstraction for XiVault."""

import abc
import datetime
from typing import Any
from uuid import UUID, uuid4

from xivault.exceptions import ConflictException, QuotaExceededException


class BaseRepository(abc.ABC):
    """Abstract base repository interface."""

    @abc.abstractmethod
    async def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        """Fetch user by username."""
        pass

    @abc.abstractmethod
    async def get_user_by_id(self, user_id: UUID) -> dict[str, Any] | None:
        """Fetch user by id."""
        pass

    @abc.abstractmethod
    async def create_user_with_quota(
        self, username: str, password_hash: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Atomically create user and user_quota record."""
        pass

    @abc.abstractmethod
    async def get_user_quota(self, user_id: UUID) -> dict[str, int]:
        """Fetch quota details for user."""
        pass

    @abc.abstractmethod
    async def create_refresh_session(
        self, user_id: UUID, token_hash: str, expires_at: datetime.datetime
    ) -> UUID:
        """Create a new refresh session."""
        pass

    @abc.abstractmethod
    async def get_refresh_session_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        """Fetch session by hashed refresh token."""
        pass

    @abc.abstractmethod
    async def rotate_refresh_session(
        self,
        old_session_id: UUID,
        user_id: UUID,
        new_token_hash: str,
        new_expires_at: datetime.datetime,
    ) -> UUID:
        """Atomically rotate a refresh session."""
        pass

    @abc.abstractmethod
    async def revoke_all_user_sessions(self, user_id: UUID) -> None:
        """Revoke all active sessions for a user (on token reuse)."""
        pass

    @abc.abstractmethod
    async def revoke_refresh_session(self, token_hash: str) -> None:
        """Revoke a single session."""
        pass

    @abc.abstractmethod
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
        """Atomically insert file metadata and increment used quota."""
        pass

    @abc.abstractmethod
    async def list_files(
        self, user_id: UUID, limit: int = 25, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        """List user's files with cursor pagination."""
        pass

    @abc.abstractmethod
    async def search_files(
        self, user_id: UUID, query: str, limit: int = 25, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Search user's files using full-text search."""
        pass

    @abc.abstractmethod
    async def get_file_by_id(self, file_id: UUID, user_id: UUID) -> dict[str, Any] | None:
        """Get file metadata verifying owner isolation."""
        pass

    @abc.abstractmethod
    async def delete_file(self, file_id: UUID, user_id: UUID) -> dict[str, Any] | None:
        """Atomically delete file metadata and decrement quota."""
        pass


class InMemoryRepository(BaseRepository):
    """Thread-safe in-memory repository for unit testing without external services."""

    def __init__(self) -> None:
        self.users: dict[UUID, dict[str, Any]] = {}
        self.quotas: dict[UUID, dict[str, Any]] = {}
        self.sessions: dict[UUID, dict[str, Any]] = {}
        self.files: dict[UUID, dict[str, Any]] = {}

    async def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        for u in self.users.values():
            if u["username"].lower() == username.lower():
                return u
        return None

    async def get_user_by_id(self, user_id: UUID) -> dict[str, Any] | None:
        return self.users.get(user_id)

    async def create_user_with_quota(
        self, username: str, password_hash: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        user_id = uuid4()
        now = datetime.datetime.now(datetime.timezone.utc)
        user = {
            "id": user_id,
            "username": username,
            "password_hash": password_hash,
            "created_at": now,
            "disabled_at": None,
        }
        quota: dict[str, Any] = {
            "user_id": user_id,
            "used_bytes": 0,
            "quota_bytes": 15728640,
            "updated_at": now,
        }
        self.users[user_id] = user
        self.quotas[user_id] = quota
        used: int = quota["used_bytes"]
        total: int = quota["quota_bytes"]
        return user, {
            "used_bytes": used,
            "quota_bytes": total,
            "remaining_bytes": total - used,
        }

    async def get_user_quota(self, user_id: UUID) -> dict[str, int]:
        q = self.quotas.get(user_id)
        if not q:
            return {"used_bytes": 0, "quota_bytes": 15728640, "remaining_bytes": 15728640}
        used: int = q["used_bytes"]
        total: int = q["quota_bytes"]
        return {
            "used_bytes": used,
            "quota_bytes": total,
            "remaining_bytes": total - used,
        }

    async def create_refresh_session(
        self, user_id: UUID, token_hash: str, expires_at: datetime.datetime
    ) -> UUID:
        session_id = uuid4()
        now = datetime.datetime.now(datetime.timezone.utc)
        self.sessions[session_id] = {
            "id": session_id,
            "user_id": user_id,
            "token_hash": token_hash,
            "expires_at": expires_at,
            "revoked_at": None,
            "replaced_by": None,
            "created_at": now,
            "last_used_at": None,
        }
        return session_id

    async def get_refresh_session_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        for s in self.sessions.values():
            if s["token_hash"] == token_hash:
                return s
        return None

    async def rotate_refresh_session(
        self,
        old_session_id: UUID,
        user_id: UUID,
        new_token_hash: str,
        new_expires_at: datetime.datetime,
    ) -> UUID:
        now = datetime.datetime.now(datetime.timezone.utc)
        new_session_id = uuid4()
        if old_session_id in self.sessions:
            self.sessions[old_session_id]["revoked_at"] = now
            self.sessions[old_session_id]["replaced_by"] = new_session_id
            self.sessions[old_session_id]["last_used_at"] = now

        self.sessions[new_session_id] = {
            "id": new_session_id,
            "user_id": user_id,
            "token_hash": new_token_hash,
            "expires_at": new_expires_at,
            "revoked_at": None,
            "replaced_by": None,
            "created_at": now,
            "last_used_at": None,
        }
        return new_session_id

    async def revoke_all_user_sessions(self, user_id: UUID) -> None:
        now = datetime.datetime.now(datetime.timezone.utc)
        for s in self.sessions.values():
            if s["user_id"] == user_id and s["revoked_at"] is None:
                s["revoked_at"] = now

    async def revoke_refresh_session(self, token_hash: str) -> None:
        now = datetime.datetime.now(datetime.timezone.utc)
        for s in self.sessions.values():
            if s["token_hash"] == token_hash:
                s["revoked_at"] = now

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
        # Atomic quota check
        q = self.quotas.get(user_id)
        if not q or (q["used_bytes"] + byte_size) > q["quota_bytes"]:
            raise QuotaExceededException("Uploading this file would exceed your 15 MiB storage quota.")

        # Atomic duplicate check
        for ef in self.files.values():
            if ef["owner_id"] == user_id and ef["display_path"] == display_path and ef.get("sha256") == sha256:
                raise ConflictException(
                    code="duplicate_file",
                    message="An identical file is already stored in your vault.",
                )

        file_id = uuid4()
        now = datetime.datetime.now(datetime.timezone.utc)
        record = {
            "id": file_id,
            "owner_id": user_id,
            "display_path": display_path,
            "storage_key": storage_key,
            "language": language,
            "content_type": content_type,
            "byte_size": byte_size,
            "sha256": sha256,
            "indexed_content": indexed_content,
            "file_content": file_content,
            "created_at": now,
            "updated_at": now,
        }
        self.files[file_id] = record
        self.quotas[user_id]["used_bytes"] += byte_size
        return record

    async def list_files(
        self, user_id: UUID, limit: int = 25, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        user_files = [f for f in self.files.values() if f["owner_id"] == user_id]
        user_files.sort(key=lambda x: (x["created_at"], str(x["id"])), reverse=True)
        if cursor and "|" in cursor:
            c_time, c_id = cursor.split("|", 1)
            user_files = [
                f for f in user_files
                if (f["created_at"].isoformat(), str(f["id"])) < (c_time, c_id)
            ]
        items = user_files[:limit]
        next_cursor = (
            f"{items[-1]['created_at'].isoformat()}|{items[-1]['id']}"
            if len(items) == limit and len(user_files) > limit
            else None
        )
        return items, next_cursor

    async def search_files(
        self, user_id: UUID, query: str, limit: int = 25, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        q_lower = query.lower()
        results: list[dict[str, Any]] = []
        for f in self.files.values():
            if f["owner_id"] == user_id:
                path_match = q_lower in f["display_path"].lower()
                content_match = f["indexed_content"] and q_lower in f["indexed_content"].lower()
                if path_match or content_match:
                    item = dict(f)
                    if content_match and f["indexed_content"]:
                        idx = f["indexed_content"].lower().find(q_lower)
                        start = max(0, idx - 40)
                        end = min(len(f["indexed_content"]), idx + len(q_lower) + 40)
                        item["excerpt"] = f["indexed_content"][start:end]
                    else:
                        item["excerpt"] = None
                    results.append(item)
        results.sort(key=lambda x: (x["created_at"], str(x["id"])), reverse=True)
        return results[:limit], None

    async def get_file_by_id(self, file_id: UUID, user_id: UUID) -> dict[str, Any] | None:
        file = self.files.get(file_id)
        if file and file["owner_id"] == user_id:
            return file
        return None

    async def delete_file(self, file_id: UUID, user_id: UUID) -> dict[str, Any] | None:
        file = self.files.get(file_id)
        if file and file["owner_id"] == user_id:
            del self.files[file_id]
            if user_id in self.quotas:
                self.quotas[user_id]["used_bytes"] = max(
                    0, self.quotas[user_id]["used_bytes"] - file["byte_size"]
                )
            return file
        return None
