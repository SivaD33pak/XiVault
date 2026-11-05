"""Unit and integration tests for Authentication API."""

from collections.abc import AsyncGenerator
from typing import Generator

import pytest
from httpx import ASGITransport, AsyncClient

from xivault.db.repository import BaseRepository, InMemoryRepository
from xivault.db.session import get_repository
from xivault.main import app
from xivault.services.rate_limiter import rate_limiter

test_repo = InMemoryRepository()


async def override_get_repository() -> AsyncGenerator[BaseRepository, None]:
    yield test_repo


@pytest.fixture(autouse=True)
def reset_state() -> Generator[None, None, None]:
    """Reset repository and rate limiter between tests."""
    test_repo.users.clear()
    test_repo.quotas.clear()
    test_repo.sessions.clear()
    test_repo.files.clear()
    rate_limiter.reset()
    app.dependency_overrides[get_repository] = override_get_repository
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_register_success_and_duplicate() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Register valid user
        res = await ac.post(
            "/v1/auth/register",
            json={"username": "alice_dev", "password": "supersecretpassword123"},
        )
        assert res.status_code == 201
        data = res.json()
        assert data["user"]["username"] == "alice_dev"
        assert data["quota"]["used_bytes"] == 0
        assert data["quota"]["quota_bytes"] == 15728640
        assert data["quota"]["remaining_bytes"] == 15728640
        assert "password" not in str(data)

        # 2. Duplicate username returns 409
        res2 = await ac.post(
            "/v1/auth/register",
            json={"username": "alice_dev", "password": "supersecretpassword123"},
        )
        assert res2.status_code == 409
        assert res2.json()["error"]["code"] == "username_taken"


@pytest.mark.asyncio
async def test_register_invalid_inputs() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Empty username is rejected
        res = await ac.post(
            "/v1/auth/register",
            json={"username": "   ", "password": "supersecretpassword123"},
        )
        assert res.status_code == 422

        # Password too short (< 6 chars)
        res2 = await ac.post(
            "/v1/auth/register",
            json={"username": "valid_user", "password": "short"},
        )
        assert res2.status_code == 422


@pytest.mark.asyncio
async def test_check_username_endpoint() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Check non-existent username
        res = await ac.get("/v1/auth/check-username", params={"username": "BrandNewUser123"})
        assert res.status_code == 200
        data = res.json()
        assert data["exists"] is False
        assert data["available"] is True

        # Register user
        reg_res = await ac.post(
            "/v1/auth/register",
            json={"username": "BrandNewUser123", "password": "password123456"},
        )
        assert reg_res.status_code == 201

        # Check existing username (case-insensitive)
        res_taken = await ac.get("/v1/auth/check-username", params={"username": "brandnewuser123"})
        assert res_taken.status_code == 200
        data_taken = res_taken.json()
        assert data_taken["exists"] is True
        assert data_taken["available"] is False


@pytest.mark.asyncio
async def test_login_and_credential_enumeration_prevention() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post(
            "/v1/auth/register",
            json={"username": "bob_developer", "password": "securepassword123"},
        )

        # Non-existent user
        res1 = await ac.post(
            "/v1/auth/login",
            json={"username": "non_existent", "password": "securepassword123"},
        )
        # Wrong password for existing user
        res2 = await ac.post(
            "/v1/auth/login",
            json={"username": "bob_developer", "password": "wrongpassword123"},
        )

        assert res1.status_code == 401
        assert res2.status_code == 401
        # Both must return identical error structure
        assert res1.json()["error"]["code"] == "invalid_credentials"
        assert res2.json()["error"]["code"] == "invalid_credentials"

        # Correct password
        res3 = await ac.post(
            "/v1/auth/login",
            json={"username": "bob_developer", "password": "securepassword123"},
        )
        assert res3.status_code == 200
        token_data = res3.json()
        assert "access_token" in token_data
        assert "refresh_token" in token_data
        assert token_data["expires_in"] == 900


@pytest.mark.asyncio
async def test_refresh_token_rotation_and_replay_revocation() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Register and login
        await ac.post(
            "/v1/auth/register",
            json={"username": "carol_dev", "password": "carolpassword123"},
        )
        login_res = await ac.post(
            "/v1/auth/login",
            json={"username": "carol_dev", "password": "carolpassword123"},
        )
        first_refresh = login_res.json()["refresh_token"]

        # Successful rotation
        rot_res = await ac.post(
            "/v1/auth/refresh",
            json={"refresh_token": first_refresh},
        )
        assert rot_res.status_code == 200
        second_refresh = rot_res.json()["refresh_token"]
        assert second_refresh != first_refresh

        # Replay attack: reusing the old refresh token
        replay_res = await ac.post(
            "/v1/auth/refresh",
            json={"refresh_token": first_refresh},
        )
        assert replay_res.status_code == 401
        assert replay_res.json()["error"]["code"] == "refresh_token_reuse"

        # Since reuse revoked all sessions, second_refresh should now also be invalid!
        invalidated_res = await ac.post(
            "/v1/auth/refresh",
            json={"refresh_token": second_refresh},
        )
        assert invalidated_res.status_code == 401


@pytest.mark.asyncio
async def test_logout_clears_session() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post(
            "/v1/auth/register",
            json={"username": "dan_developer", "password": "danpassword123"},
        )
        login_res = await ac.post(
            "/v1/auth/login",
            json={"username": "dan_developer", "password": "danpassword123"},
        )
        access_token = login_res.json()["access_token"]
        refresh_token = login_res.json()["refresh_token"]

        # Logout
        logout_res = await ac.post(
            "/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"refresh_token": refresh_token},
        )
        assert logout_res.status_code == 204

        # Refresh with logged-out token should fail
        refresh_fail = await ac.post(
            "/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_fail.status_code == 401
