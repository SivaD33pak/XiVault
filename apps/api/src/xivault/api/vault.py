"""Vault and file management endpoints."""

import hashlib
import os
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile

from xivault.api.deps import get_current_user
from xivault.db.repository import BaseRepository
from xivault.db.session import get_repository
from xivault.exceptions import (
    ConflictException,
    FileTooLargeException,
    NotFoundException,
    QuotaExceededException,
)
from xivault.schemas import (
    FileListResponse,
    FileSearchResponse,
    QuotaPublic,
    UploadResponse,
)
from xivault.services.rate_limiter import rate_limiter
from xivault.services.storage import BaseStorage, get_storage
from xivault.services.validator import (
    MAX_FILE_BYTES,
    validate_display_path,
    validate_source_content,
)

router = APIRouter(tags=["vault"])


@router.get("/me/quota", response_model=QuotaPublic)
async def get_my_quota(
    current_user: dict[str, Any] = Depends(get_current_user),
    repo: BaseRepository = Depends(get_repository),
) -> Any:
    """Fetch storage quota usage and remaining space."""
    return await repo.get_user_quota(current_user["id"])


@router.post("/files", status_code=201, response_model=UploadResponse)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    display_path: str = Form(...),
    current_user: dict[str, Any] = Depends(get_current_user),
    repo: BaseRepository = Depends(get_repository),
    storage: BaseStorage = Depends(get_storage),
) -> Any:
    """Upload a source code file to private vault with quota validation."""
    user_id: UUID = current_user["id"]

    # Rate limiting: 30 uploads per hour
    rate_limiter.check(f"upload:{user_id}", max_requests=30, window_seconds=3600)

    # Validate path
    clean_path = validate_display_path(display_path)

    # Read with 1-byte overflow cap to reject oversized uploads without buffering entire file in RAM
    data = await file.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise FileTooLargeException("File size exceeds maximum allowed 1 MiB limit.")
    language, content_type, indexed_content = validate_source_content(clean_path, data)
    byte_size = len(data)
    file_sha256 = hashlib.sha256(data).hexdigest()

    # Generate isolated storage key: {owner_id}/{file_id}
    file_id = uuid4()
    storage_key = f"{user_id}/{file_id}"

    # Step 1: Upload to private storage (if configured)
    try:
        await storage.upload_object(key=storage_key, data=data, content_type=content_type)
    except Exception:
        # Storage upload is best-effort if database column stores file_content
        pass

    # Step 2: Insert into database and increment quota directly in Supabase
    try:
        text_content = data.decode("utf-8")
        record = await repo.commit_uploaded_file(
            user_id=user_id,
            display_path=clean_path,
            storage_key=storage_key,
            language=language,
            content_type=content_type,
            byte_size=byte_size,
            sha256=file_sha256,
            indexed_content=indexed_content,
            file_content=text_content,
        )
    except (ConflictException, QuotaExceededException):
        await storage.delete_object(storage_key)
        raise
    except Exception as exc:
        # Compensating cleanup: delete orphaned storage object
        await storage.delete_object(storage_key)
        raise exc

    quota = await repo.get_user_quota(user_id)
    return {
        "file": record,
        "quota": quota,
    }


@router.get("/files", response_model=FileListResponse)
async def list_files(
    cursor: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    current_user: dict[str, Any] = Depends(get_current_user),
    repo: BaseRepository = Depends(get_repository),
) -> Any:
    """List stored files in user vault with pagination."""
    items, next_cursor = await repo.list_files(user_id=current_user["id"], limit=limit, cursor=cursor)
    return {"items": items, "next_cursor": next_cursor}


@router.get("/files/search", response_model=FileSearchResponse)
async def search_files(
    q: str = Query(..., min_length=1, max_length=200),
    cursor: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    current_user: dict[str, Any] = Depends(get_current_user),
    repo: BaseRepository = Depends(get_repository),
) -> Any:
    """Full-text search across file paths and indexed content."""
    items, next_cursor = await repo.search_files(
        user_id=current_user["id"], query=q.strip(), limit=limit, cursor=cursor
    )
    return {"items": items, "next_cursor": next_cursor}


@router.get("/files/{file_id}/download")
async def download_file(
    file_id: UUID,
    current_user: dict[str, Any] = Depends(get_current_user),
    repo: BaseRepository = Depends(get_repository),
    storage: BaseStorage = Depends(get_storage),
) -> Response:
    """Download a stored file, streamed from private storage."""
    file_record = await repo.get_file_by_id(file_id=file_id, user_id=current_user["id"])
    if not file_record:
        # Never reveal existence across users
        raise NotFoundException(code="file_not_found", message="File not found.")

    if file_record.get("file_content"):
        content = file_record["file_content"].encode("utf-8")
    else:
        try:
            content = await storage.download_object(file_record["storage_key"])
        except Exception:
            raise NotFoundException(code="file_not_found", message="File object not found.") from None

    filename = os.path.basename(file_record["display_path"])
    return Response(
        content=content,
        media_type=file_record.get("content_type", "text/plain"),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(file_record["byte_size"]),
        },
    )


@router.delete("/files/{file_id}", status_code=204)
async def delete_file(
    file_id: UUID,
    current_user: dict[str, Any] = Depends(get_current_user),
    repo: BaseRepository = Depends(get_repository),
    storage: BaseStorage = Depends(get_storage),
) -> Response:
    """Permanently delete a file from vault and decrement quota."""
    deleted_record = await repo.delete_file(file_id=file_id, user_id=current_user["id"])
    if not deleted_record:
        raise NotFoundException(code="file_not_found", message="File not found.")

    await storage.delete_object(deleted_record["storage_key"])
    return Response(status_code=204)
