"""Pydantic schemas matching the REST API contract."""

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator


class RegisterRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        pattern = r"^[a-z0-9_-]{3,32}$"
        if not re.match(pattern, v):
            raise ValueError(
                "Username must be 3-32 characters and only contain lowercase letters, numbers, _, -"
            )
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters long.")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class UserPublic(BaseModel):
    id: UUID
    username: str
    created_at: datetime | None = None


class QuotaPublic(BaseModel):
    used_bytes: int
    quota_bytes: int = 5242880
    remaining_bytes: int


class RegisterResponse(BaseModel):
    user: UserPublic
    quota: QuotaPublic


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 900
    refresh_token: str
    user: UserPublic


class FilePublic(BaseModel):
    id: UUID
    display_path: str
    language: str
    content_type: str | None = None
    byte_size: int
    sha256: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class FileListItem(BaseModel):
    id: UUID
    display_path: str
    language: str
    byte_size: int
    created_at: datetime


class FileListResponse(BaseModel):
    items: list[FileListItem]
    next_cursor: str | None = None


class FileSearchItem(BaseModel):
    id: UUID
    display_path: str
    language: str
    byte_size: int
    created_at: datetime
    excerpt: str | None = None


class FileSearchResponse(BaseModel):
    items: list[FileSearchItem]
    next_cursor: str | None = None


class UploadResponse(BaseModel):
    file: FilePublic
    quota: QuotaPublic
