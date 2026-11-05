"""Test health and request ID middleware."""

import pytest
from httpx import ASGITransport, AsyncClient

from xivault.main import app


@pytest.mark.asyncio
async def test_healthz_endpoint() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "X-Request-ID" in response.headers


@pytest.mark.asyncio
async def test_readyz_endpoint() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert "X-Request-ID" in response.headers
