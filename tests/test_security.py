"""Tests for the REST API shared-secret guard.

The Telegram allowlist only covers bot handlers, so these cover the gate that
stops arbitrary callers from acting as another user over HTTP.
"""

from types import SimpleNamespace

import httpx
import pytest
from fastapi import Depends, FastAPI, HTTPException

from app.core import security


def configure(monkeypatch, *, key, env="local"):
    """Swap the module-level settings rather than mutating shared state."""
    monkeypatch.setattr(
        security,
        "settings",
        SimpleNamespace(internal_api_key=key, app_env=env),
    )


# --- caller_is_trusted -------------------------------------------------


def test_valid_key_is_trusted(monkeypatch):
    configure(monkeypatch, key="s3cret")

    assert security.caller_is_trusted("s3cret") is True


def test_wrong_key_is_not_trusted(monkeypatch):
    configure(monkeypatch, key="s3cret")

    assert security.caller_is_trusted("guess") is False


def test_missing_key_is_not_trusted(monkeypatch):
    configure(monkeypatch, key="s3cret")

    assert security.caller_is_trusted(None) is False


def test_unconfigured_key_is_trusted_locally(monkeypatch):
    """Local development runs without a secret."""
    configure(monkeypatch, key=None, env="local")

    assert security.caller_is_trusted(None) is True


def test_unconfigured_key_is_never_trusted_in_production(monkeypatch):
    """A missing secret must not silently disable the guard on Render."""
    configure(monkeypatch, key=None, env="production")

    assert security.caller_is_trusted(None) is False


# --- require_trusted_caller -------------------------------------------


def test_require_rejects_wrong_key(monkeypatch):
    configure(monkeypatch, key="s3cret")

    with pytest.raises(HTTPException) as exc:
        security.require_trusted_caller("guess")

    assert exc.value.status_code == 401


def test_require_allows_valid_key(monkeypatch):
    configure(monkeypatch, key="s3cret")

    assert security.require_trusted_caller("s3cret") is None


def test_require_fails_closed_when_unconfigured_in_production(monkeypatch):
    configure(monkeypatch, key=None, env="production")

    with pytest.raises(HTTPException) as exc:
        security.require_trusted_caller("anything")

    assert exc.value.status_code == 503


# --- applied as a route dependency ------------------------------------


@pytest.fixture
def protected_client():
    api = FastAPI()

    @api.get(
        "/protected",
        dependencies=[Depends(security.require_trusted_caller)],
    )
    async def protected():
        return {"ok": True}

    transport = httpx.ASGITransport(app=api)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_protected_route_rejects_missing_header(
    protected_client, monkeypatch
):
    configure(monkeypatch, key="s3cret")

    async with protected_client as http:
        response = await http.get("/protected")

    assert response.status_code == 401


async def test_protected_route_accepts_valid_header(
    protected_client, monkeypatch
):
    configure(monkeypatch, key="s3cret")

    async with protected_client as http:
        response = await http.get(
            "/protected", headers={security.API_KEY_HEADER: "s3cret"}
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
