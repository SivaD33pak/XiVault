"""Unit and integration tests for Vault API."""

from collections.abc import AsyncGenerator
from typing import Generator

import pytest
from httpx import ASGITransport, AsyncClient

from xivault.db.repository import BaseRepository, InMemoryRepository
from xivault.db.session import get_repository
from xivault.main import app
from xivault.services.rate_limiter import rate_limiter
from xivault.services.storage import _in_memory_storage

test_repo = InMemoryRepository()


async def override_get_repository() -> AsyncGenerator[BaseRepository, None]:
    yield test_repo


@pytest.fixture(autouse=True)
def reset_state() -> Generator[None, None, None]:
    test_repo.users.clear()
    test_repo.quotas.clear()
    test_repo.sessions.clear()
    test_repo.files.clear()
    _in_memory_storage.objects.clear()
    rate_limiter.reset()
    app.dependency_overrides[get_repository] = override_get_repository
    yield
    app.dependency_overrides.clear()


async def create_user_and_token(client: AsyncClient, username: str) -> str:
    await client.post(
        "/v1/auth/register",
        json={"username": username, "password": "password123456"},
    )
    login_res = await client.post(
        "/v1/auth/login",
        json={"username": username, "password": "password123456"},
    )
    return str(login_res.json()["access_token"])


@pytest.mark.asyncio
async def test_upload_and_quota_update() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await create_user_and_token(ac, "alice_uploader")

        # Initial quota check
        quota_res = await ac.get("/v1/me/quota", headers={"Authorization": f"Bearer {token}"})
        assert quota_res.status_code == 200
        assert quota_res.json()["used_bytes"] == 0

        # Upload a valid python file
        content = b"print('Hello, XiVault!')\n"
        upload_res = await ac.post(
            "/v1/files",
            headers={"Authorization": f"Bearer {token}"},
            data={"display_path": "src/hello.py"},
            files={"file": ("hello.py", content, "text/x-python")},
        )
        assert upload_res.status_code == 201
        data = upload_res.json()
        assert data["file"]["display_path"] == "src/hello.py"
        assert data["file"]["language"] == "python"
        assert data["file"]["byte_size"] == len(content)
        assert data["quota"]["used_bytes"] == len(content)
        assert data["quota"]["remaining_bytes"] == 5242880 - len(content)


@pytest.mark.asyncio
async def test_upload_validation_rejections() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await create_user_and_token(ac, "tester_val")

        # 1. Path traversal rejected
        res_trav = await ac.post(
            "/v1/files",
            headers={"Authorization": f"Bearer {token}"},
            data={"display_path": "../evil.py"},
            files={"file": ("evil.py", b"print(1)", "text/plain")},
        )
        assert res_trav.status_code == 422
        assert res_trav.json()["error"]["code"] == "invalid_path"

        # 2. Binary file rejected
        res_bin = await ac.post(
            "/v1/files",
            headers={"Authorization": f"Bearer {token}"},
            data={"display_path": "src/bin.py"},
            files={"file": ("bin.py", b"\x00\x01\x02binary", "application/octet-stream")},
        )
        assert res_bin.status_code == 422
        assert res_bin.json()["error"]["code"] == "invalid_text_encoding"

        # 3. File too large (> 1 MiB)
        huge_content = b"a" * (1048576 + 1)
        res_huge = await ac.post(
            "/v1/files",
            headers={"Authorization": f"Bearer {token}"},
            data={"display_path": "huge.txt"},
            files={"file": ("huge.txt", huge_content, "text/plain")},
        )
        assert res_huge.status_code == 413
        assert res_huge.json()["error"]["code"] == "file_too_large"


@pytest.mark.asyncio
async def test_duplicate_file_prevention() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await create_user_and_token(ac, "dup_tester")
        content = b"def test(): pass\n"

        res1 = await ac.post(
            "/v1/files",
            headers={"Authorization": f"Bearer {token}"},
            data={"display_path": "test.py"},
            files={"file": ("test.py", content, "text/x-python")},
        )
        assert res1.status_code == 201

        res2 = await ac.post(
            "/v1/files",
            headers={"Authorization": f"Bearer {token}"},
            data={"display_path": "test.py"},
            files={"file": ("test.py", content, "text/x-python")},
        )
        assert res2.status_code == 409
        assert res2.json()["error"]["code"] == "duplicate_file"


@pytest.mark.asyncio
async def test_owner_isolation_boundaries() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token_a = await create_user_and_token(ac, "user_alice")
        token_b = await create_user_and_token(ac, "user_bob")

        # Alice uploads a secret file
        secret_content = b"CONFIDENTIAL_SOURCE_CODE = True\n"
        upload_res = await ac.post(
            "/v1/files",
            headers={"Authorization": f"Bearer {token_a}"},
            data={"display_path": "secret.py"},
            files={"file": ("secret.py", secret_content, "text/x-python")},
        )
        file_id = upload_res.json()["file"]["id"]

        # 1. Bob cannot see Alice's file in list
        bob_list = await ac.get("/v1/files", headers={"Authorization": f"Bearer {token_b}"})
        assert len(bob_list.json()["items"]) == 0

        # 2. Bob cannot find Alice's file via search
        bob_search = await ac.get(
            "/v1/files/search?q=CONFIDENTIAL",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert len(bob_search.json()["items"]) == 0

        # 3. Bob cannot download Alice's file (returns 404, never 403)
        bob_download = await ac.get(
            f"/v1/files/{file_id}/download",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert bob_download.status_code == 404

        # 4. Bob cannot delete Alice's file
        bob_delete = await ac.delete(
            f"/v1/files/{file_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert bob_delete.status_code == 404


@pytest.mark.asyncio
async def test_download_and_delete_lifecycle() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await create_user_and_token(ac, "lifecycle_user")
        content = b"export const message = 'test';\n"

        # Upload
        up = await ac.post(
            "/v1/files",
            headers={"Authorization": f"Bearer {token}"},
            data={"display_path": "lib/util.ts"},
            files={"file": ("util.ts", content, "text/x-typescript")},
        )
        file_id = up.json()["file"]["id"]
        assert up.json()["quota"]["used_bytes"] == len(content)

        # Download
        down = await ac.get(
            f"/v1/files/{file_id}/download",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert down.status_code == 200
        assert down.content == content
        assert 'filename="util.ts"' in down.headers["Content-Disposition"]

        # Search
        srch = await ac.get(
            "/v1/files/search?q=util",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert srch.status_code == 200
        assert len(srch.json()["items"]) == 1

        # Delete
        dele = await ac.delete(
            f"/v1/files/{file_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert dele.status_code == 204

        # Quota decremented
        quota_after = await ac.get("/v1/me/quota", headers={"Authorization": f"Bearer {token}"})
        assert quota_after.json()["used_bytes"] == 0

        # Subsequent download is 404
        down_after = await ac.get(
            f"/v1/files/{file_id}/download",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert down_after.status_code == 404
