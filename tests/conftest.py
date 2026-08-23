"""Shared test configuration.

DATABASE_URL is the only required setting, and `app.core.database` builds its
engine at import time. Provide a default before any app module is imported so
the suite can be collected without a .env file (e.g. on CI).
"""

import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://assistant_user:assistant_password@postgres:5432/assistant_db",
)
