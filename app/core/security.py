"""Shared-secret authentication for the internal REST API.

The Telegram allowlist in `app.bot.auth` only guards the bot handlers. The
REST API is reachable directly, so any caller could previously pass an
arbitrary `telegram_chat_id` and act as that user. These helpers gate the
routes that read or write user data.

Callers present the secret as an `X-API-Key` header. When no key is
configured the API stays open for local development, but refuses to serve
protected routes in production rather than falling back to no protection.
"""

import hmac

from fastapi import Header, HTTPException, status

from app.core.config import get_settings

settings = get_settings()

API_KEY_HEADER = "X-API-Key"


def _is_production() -> bool:
    return settings.app_env.lower() == "production"


def caller_is_trusted(
    x_api_key: str | None = Header(default=None, alias=API_KEY_HEADER),
) -> bool:
    """Report whether the caller presented the shared secret.

    Used by routes that stay publicly reachable but must restrict the
    privileged parts of their payload.
    """
    expected = settings.internal_api_key

    if not expected:
        # Unconfigured: convenient locally, never trusted in production.
        return not _is_production()

    if not x_api_key:
        return False

    return hmac.compare_digest(x_api_key, expected)


def require_trusted_caller(
    x_api_key: str | None = Header(default=None, alias=API_KEY_HEADER),
) -> None:
    """Reject callers that did not present the shared secret."""
    if not settings.internal_api_key and _is_production():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "INTERNAL_API_KEY is not configured; protected routes are "
                "disabled."
            ),
        )

    if not caller_is_trusted(x_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing or invalid {API_KEY_HEADER} header.",
            headers={"WWW-Authenticate": API_KEY_HEADER},
        )
