"""The bot calls the protected API, so it must present the shared secret.

If the header stops being attached the bot breaks in production, where every
data route requires it.
"""

from types import SimpleNamespace

import pytest

from app.bot import api_client
from app.core.security import API_KEY_HEADER


def test_auth_header_is_attached_when_key_is_configured(monkeypatch):
    monkeypatch.setattr(
        api_client,
        "settings",
        SimpleNamespace(internal_api_key="s3cret", api_base_url="http://api"),
    )

    assert api_client._auth_headers() == {API_KEY_HEADER: "s3cret"}


def test_no_auth_header_when_key_is_unset(monkeypatch):
    """Local runs have no secret and must not send an empty header."""
    monkeypatch.setattr(
        api_client,
        "settings",
        SimpleNamespace(internal_api_key=None, api_base_url="http://api"),
    )

    assert api_client._auth_headers() == {}


async def test_post_to_backend_sends_the_header(monkeypatch):
    """Covers the wiring, not just the helper."""
    monkeypatch.setattr(
        api_client,
        "settings",
        SimpleNamespace(internal_api_key="s3cret", api_base_url="http://api"),
    )

    seen = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None, headers=None):
            seen["url"] = url
            seen["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr(api_client.httpx, "AsyncClient", FakeClient)

    result = await api_client.post_to_backend("/memory/list", {"a": 1})

    assert result == {"ok": True}
    assert seen["url"] == "http://api/memory/list"
    assert seen["headers"] == {API_KEY_HEADER: "s3cret"}
