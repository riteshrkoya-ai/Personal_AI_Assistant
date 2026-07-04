import logging

import httpx
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.core.config import get_settings

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
settings = get_settings()


def get_authorized_chat_ids() -> set[int]:
    """
    Parse AUTHORIZED_TELEGRAM_CHAT_IDS from .env.

    Example:
    AUTHORIZED_TELEGRAM_CHAT_IDS=123456789,987654321
    """
    raw_ids = settings.authorized_telegram_chat_ids

    if not raw_ids:
        return set()

    chat_ids: set[int] = set()

    for item in raw_ids.split(","):
        item = item.strip()
        if item:
            chat_ids.add(int(item))

    return chat_ids


def is_authorized(chat_id: int) -> bool:
    authorized_chat_ids = get_authorized_chat_ids()
    return chat_id in authorized_chat_ids


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id if update.effective_chat else None

    await update.message.reply_text(
        "AI Personal Assistant bot is running.\n\n"
        f"Your Telegram chat ID is: {chat_id}\n\n"
        "Ask the project lead to add this ID to AUTHORIZED_TELEGRAM_CHAT_IDS."
    )


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id if update.effective_chat else None

    await update.message.reply_text(
        f"Your Telegram chat ID is: {chat_id}"
    )


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    user_message = update.message.text

    if not is_authorized(chat_id):
        logger.warning("Unauthorized Telegram chat_id attempted access: %s", chat_id)
        await update.message.reply_text(
            "You are not authorized to use this assistant yet.\n\n"
            f"Your Telegram chat ID is: {chat_id}\n"
            "Add it to AUTHORIZED_TELEGRAM_CHAT_IDS in your local .env file."
        )
        return

    await update.message.reply_text("Thinking...")

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.api_base_url}/chat",
                json={"message": user_message},
            )
            response.raise_for_status()
            data = response.json()

        assistant_response = data.get("response", "I could not generate a response.")
        await update.message.reply_text(assistant_response)

    except Exception as exc:
        logger.exception("Telegram polling worker failed while calling /chat")

        await update.message.reply_text(
            "I could not reach the assistant backend right now.\n\n"
            f"Technical detail: {type(exc).__name__}: {exc}"
        )


def main() -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is missing. Add it to your .env file."
        )

    application = Application.builder().token(settings.telegram_bot_token).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    logger.info("Starting Telegram polling worker...")
    application.run_polling()


if __name__ == "__main__":
    main()