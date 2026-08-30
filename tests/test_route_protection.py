"""End-to-end checks that the live route table is actually gated.

These drive the real application object, so adding a router to
`app.main` without protecting it makes a test here fail. Unauthorized
requests are rejected before any handler runs, so no database is needed.
"""

from types import SimpleNamespace

import httpx
import pytest

from app.core import security
from app.main import app

TEST_KEY = "test-shared-secret"

# Every route that reads or writes stored user data.
PROTECTED_PATHS = [
    "/agent/run",
    "/memory",
    "/memory/list",
    "/memory/search",
    "/memory/delete",
    "/reminders",
    "/reminders/list",
    "/reminders/cancel",
    "/tasks",
    "/tasks/list",
    "/tasks/complete",
    "/tasks/delete",
    "/study/plans",
    "/study/plans/list",
    "/daily-summary",
    "/daily-summary/settings",
    "/future-me/goals",
    "/future-me/goals/list",
    "/future-me/tasks/list",
]


@pytest.fixture(autouse=True)
def configured_key(monkeypatch):
    monkeypatch.setattr(
        security,
        "settings",
        SimpleNamespace(internal_api_key=TEST_KEY, app_env="production"),
    )


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.parametrize("path", PROTECTED_PATHS)
async def test_protected_path_rejects_anonymous_request(client, path):
    async with client as http:
        response = await http.post(path, json={"telegram_chat_id": 1})

    assert response.status_code == 401, (
        f"{path} answered {response.status_code} without an API key"
    )


@pytest.mark.parametrize("path", PROTECTED_PATHS)
async def test_protected_path_rejects_wrong_key(client, path):
    async with client as http:
        response = await http.post(
            path,
            json={"telegram_chat_id": 1},
            headers={security.API_KEY_HEADER: "wrong-key"},
        )

    assert response.status_code == 401


async def test_health_stays_public(client):
    """Render's health check is unauthenticated."""
    async with client as http:
        response = await http.get("/health")

    assert response.status_code == 200


async def test_chat_rejects_impersonation_without_key(client):
    """Naming another user's chat id requires the secret."""
    async with client as http:
        response = await http.post(
            "/chat",
            json={"message": "hello", "telegram_chat_id": 99999},
        )

    assert response.status_code == 401


async def test_anonymous_chat_still_works(client, monkeypatch):
    """The public browser chat sends no chat id and must keep working."""

    async def fake_response(user_message: str) -> str:
        return "canned reply"

    monkeypatch.setattr(
        "app.api.chat.generate_chat_response", fake_response
    )

    async with client as http:
        response = await http.post(
            "/chat", json={"message": "hello", "source": "web"}
        )

    assert response.status_code == 200
    assert response.json()["response"] == "canned reply"
