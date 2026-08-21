import hmac

from fastapi import (
    APIRouter,
    Header,
    HTTPException,
    Request,
    status,
)
from telegram import Update

from app.core.config import get_settings


router = APIRouter()
settings = get_settings()


@router.post(
    "/telegram/webhook",
    include_in_schema=False,
)
async def telegram_webhook(
    request: Request,
    telegram_secret: str | None = Header(
        default=None,
        alias="X-Telegram-Bot-Api-Secret-Token",
    ),
) -> dict[str, bool]:
    if settings.telegram_mode.lower() != "webhook":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Telegram webhook is not enabled.",
        )

    if not settings.telegram_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram webhook secret is not configured.",
        )

    if not telegram_secret or not hmac.compare_digest(
        telegram_secret,
        settings.telegram_webhook_secret,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Telegram webhook secret.",
        )

    telegram_application = getattr(
        request.app.state,
        "telegram_application",
        None,
    )

    if telegram_application is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram application is not ready.",
        )

    payload = await request.json()

    update = Update.de_json(
        payload,
        telegram_application.bot,
    )

    # Queue the update and return immediately so Telegram receives
    # a fast HTTP 200 response. python-telegram-bot processes it
    # asynchronously in the application update queue.
    await telegram_application.update_queue.put(update)

    return {"ok": True}