import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from telegram import Update

from app.api.agent import router as agent_router
from app.api.chat import router as chat_router
from app.api.daily_summary import router as daily_summary_router
from app.api.future_me import router as future_me_router
from app.api.health import router as health_router
from app.api.memory import router as memory_router
from app.api.reminders import router as reminders_router
from app.api.study import router as study_router
from app.api.telegram_webhook import router as telegram_webhook_router
from app.bot.application import build_telegram_application
from app.core.config import get_settings
from app.core.database import create_database_tables
from app.core.security import require_trusted_caller
from app.services.llm_client import warm_up_model


logger = logging.getLogger(__name__)
settings = get_settings()

WEB_INDEX = (
    Path(__file__).resolve().parent
    / "web"
    / "index.html"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_database_tables()

    asyncio.create_task(
        warm_up_model()
    )

    telegram_application = None

    if settings.telegram_mode.lower() == "webhook":

        if not settings.telegram_bot_token:
            raise RuntimeError(
                "TELEGRAM_BOT_TOKEN is required in webhook mode."
            )

        if not settings.telegram_webhook_url:
            raise RuntimeError(
                "TELEGRAM_WEBHOOK_URL is required in webhook mode."
            )

        if not settings.telegram_webhook_secret:
            raise RuntimeError(
                "TELEGRAM_WEBHOOK_SECRET is required in webhook mode."
            )

        telegram_application = (
            build_telegram_application(
                webhook=True
            )
        )

        await telegram_application.initialize()

        await telegram_application.bot.set_webhook(
            url=settings.telegram_webhook_url,
            secret_token=settings.telegram_webhook_secret,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=False,
        )

        await telegram_application.start()

        app.state.telegram_application = (
            telegram_application
        )

        logger.info(
            "Telegram webhook configured: %s",
            settings.telegram_webhook_url,
        )

    try:
        yield

    finally:

        if telegram_application is not None:
            await telegram_application.stop()
            await telegram_application.shutdown()


IS_PRODUCTION = settings.app_env.lower() == "production"

# The interactive docs enumerate every route and payload shape, so they
# stay off on the public deployment.
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="AI Personal Assistant MVP backend",
    lifespan=lifespan,
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

# Routes that read or write stored user data. They accept a
# telegram_chat_id in the body, so they must not be callable by anyone
# who happens to know the URL.
PROTECTED = [Depends(require_trusted_caller)]


# Public: Render's health check probes this.
app.include_router(health_router)

# Public: serves the browser chat UI. Guards its own privileged
# telegram_chat_id field internally.
app.include_router(chat_router)

# Public: authenticated by Telegram's own webhook secret header.
app.include_router(telegram_webhook_router)

app.include_router(agent_router, dependencies=PROTECTED)
app.include_router(memory_router, dependencies=PROTECTED)
app.include_router(reminders_router, dependencies=PROTECTED)
app.include_router(study_router, dependencies=PROTECTED)
app.include_router(daily_summary_router, dependencies=PROTECTED)
app.include_router(future_me_router, dependencies=PROTECTED)


@app.get(
    "/",
    include_in_schema=False,
)
async def root():
    return FileResponse(
        WEB_INDEX
    )


@app.get(
    "/api/info",
    tags=["meta"],
)
async def api_info():
    return {
        "message": (
            "AI Personal Assistant API is running"
        ),
        "docs": "/docs",
        "health": "/health",
        "database_health": "/health/db",
    }