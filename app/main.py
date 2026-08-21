import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
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
from app.services.llm_client import warm_up_model


logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_database_tables()
    asyncio.create_task(warm_up_model())

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

        telegram_application = build_telegram_application(
            webhook=True
        )

        await telegram_application.initialize()

        await telegram_application.bot.set_webhook(
            url=settings.telegram_webhook_url,
            secret_token=settings.telegram_webhook_secret,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=False,
        )

        await telegram_application.start()

        app.state.telegram_application = telegram_application

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


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="AI Personal Assistant MVP backend",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(agent_router)
app.include_router(chat_router)
app.include_router(memory_router)
app.include_router(reminders_router)
app.include_router(study_router)
app.include_router(daily_summary_router)
app.include_router(future_me_router)
app.include_router(telegram_webhook_router)


@app.get("/")
async def root():
    return {
        "message": "AI Personal Assistant API is running",
        "docs": "/docs",
        "health": "/health",
    }