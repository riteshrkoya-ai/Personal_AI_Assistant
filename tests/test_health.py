"""Tests for the health endpoints.

The router is mounted on a bare FastAPI app rather than importing
`app.main`, so these run without triggering the application lifespan
(table creation, model warm-up, Telegram setup).
"""

import httpx
import pytest
from fastapi import FastAPI

from app.api import health as health_module


@pytest.fixture
def client():
    api = FastAPI()
    api.include_router(health_module.router)

    transport = httpx.ASGITransport(app=api)

    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_health_reports_healthy(client):
    async with client as http:
        response = await http.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "AI Personal Assistant API",
        "version": "0.1.0",
    }


async def test_database_health_reports_connected(client, monkeypatch):
    async def fake_check():
        return True

    monkeypatch.setattr(
        health_module, "check_database_connection", fake_check
    )

    async with client as http:
        response = await http.get("/health/db")

    assert response.status_code == 200
    assert response.json() == {
        "database": "connected",
        "status": "healthy",
    }


async def test_database_health_reports_failure(client, monkeypatch):
    """A dead database must surface as unhealthy, not raise."""

    async def fake_check():
        return False

    monkeypatch.setattr(
        health_module, "check_database_connection", fake_check
    )

    async with client as http:
        response = await http.get("/health/db")

    assert response.status_code == 200
    assert response.json() == {
        "database": "not connected",
        "status": "unhealthy",
    }
