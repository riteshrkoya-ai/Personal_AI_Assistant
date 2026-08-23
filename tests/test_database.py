"""Unit tests for database URL normalization.

Render supplies `postgres://` and `postgresql://` URLs, but SQLAlchemy's async
engine requires the `postgresql+asyncpg://` driver prefix. These cases cover
that translation, which runs on every startup.
"""

import pytest

from app.core.database import normalize_database_url


def test_bare_postgres_scheme_gets_asyncpg_driver():
    result = normalize_database_url(
        "postgres://user:pw@host:5432/assistant_db"
    )

    assert result == "postgresql+asyncpg://user:pw@host:5432/assistant_db"


def test_postgresql_scheme_gets_asyncpg_driver():
    result = normalize_database_url(
        "postgresql://user:pw@host:5432/assistant_db"
    )

    assert result == "postgresql+asyncpg://user:pw@host:5432/assistant_db"


def test_already_normalized_url_is_unchanged():
    url = "postgresql+asyncpg://user:pw@host:5432/assistant_db"

    assert normalize_database_url(url) == url


def test_non_postgres_url_is_passed_through():
    url = "sqlite+aiosqlite:///./local.db"

    assert normalize_database_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "postgres://user:pw@host/db",
        "postgresql://user:pw@host/db",
        "postgresql+asyncpg://user:pw@host/db",
    ],
)
def test_result_is_always_asyncpg_for_postgres_urls(url):
    """Whatever Render hands us, the engine must end up on asyncpg."""
    assert normalize_database_url(url).startswith("postgresql+asyncpg://")


def test_credentials_and_query_string_survive_normalization():
    result = normalize_database_url(
        "postgres://u:p%40ss@host:5432/db?sslmode=require"
    )

    assert result == (
        "postgresql+asyncpg://u:p%40ss@host:5432/db?sslmode=require"
    )
