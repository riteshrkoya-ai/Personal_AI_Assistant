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

# Reduce noisy logs and avoid exposing Telegram API URLs/tokens in terminal output.
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


async def send_unauthorized_message(update: Update, chat_id: int) -> None:
    if not update.message:
        return

    await update.message.reply_text(
        "You are not authorized to use this assistant yet.\n\n"
        f"Your Telegram chat ID is: {chat_id}\n"
        "Add it to AUTHORIZED_TELEGRAM_CHAT_IDS in your local .env file."
    )


def format_memory_items(memories: list[dict]) -> str:
    if not memories:
        return "No personal memories found."

    lines = ["Your saved memories:\n"]

    for memory in memories:
        memory_id = memory.get("id")
        content = memory.get("content", "")
        lines.append(f"{memory_id}. {content}")

    lines.append("\nTo delete a memory, use:")
    lines.append("/forget <memory_id>")

    return "\n".join(lines)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    chat_id = update.effective_chat.id if update.effective_chat else None

    await update.message.reply_text(
        "AI Personal Assistant bot is running.\n\n"
        f"Your Telegram chat ID is: {chat_id}\n\n"
        "Available commands:\n"
        "/id - show your Telegram chat ID\n"
        "/remember <text> - save a personal memory\n"
        "/memories - list your saved memories\n"
        "/memorysearch <query> - search your memories\n"
        "/forget <memory_id> - delete a memory\n\n"
        "Ask the project lead to add your ID to AUTHORIZED_TELEGRAM_CHAT_IDS."
    )


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    chat_id = update.effective_chat.id if update.effective_chat else None

    await update.message.reply_text(
        f"Your Telegram chat ID is: {chat_id}"
    )


async def remember_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Save an explicit user-provided memory.

    Example:
    /remember My preferred backend framework is FastAPI.
    """
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id

    if not is_authorized(chat_id):
        logger.warning("Unauthorized Telegram chat_id attempted /remember: %s", chat_id)
        await send_unauthorized_message(update, chat_id)
        return

    memory_text = " ".join(context.args).strip()

    if not memory_text:
        await update.message.reply_text(
            "Please provide what you want me to remember.\n\n"
            "Example:\n"
            "/remember My preferred backend framework is FastAPI."
        )
        return

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.api_base_url}/memory",
                json={
                    "telegram_chat_id": chat_id,
                    "content": memory_text,
                    "source": "telegram",
                },
            )

            response.raise_for_status()
            data = response.json()

        memory_id = data.get("memory_id")

        await update.message.reply_text(
            f"Saved this to your personal memory.\n\nMemory ID: {memory_id}"
        )

    except Exception as exc:
        logger.exception("Telegram polling worker failed while saving memory")

        await update.message.reply_text(
            "I could not save that memory right now.\n\n"
            f"Technical detail: {type(exc).__name__}: {exc}"
        )


async def memories_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    List recent saved memories.

    Example:
    /memories
    """
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id

    if not is_authorized(chat_id):
        logger.warning("Unauthorized Telegram chat_id attempted /memories: %s", chat_id)
        await send_unauthorized_message(update, chat_id)
        return

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.api_base_url}/memory/list",
                json={
                    "telegram_chat_id": chat_id,
                    "limit": 20,
                },
            )

            response.raise_for_status()
            data = response.json()

        memories = data.get("memories", [])
        await update.message.reply_text(format_memory_items(memories))

    except Exception as exc:
        logger.exception("Telegram polling worker failed while listing memories")

        await update.message.reply_text(
            "I could not list your memories right now.\n\n"
            f"Technical detail: {type(exc).__name__}: {exc}"
        )


async def memory_search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Search saved memories.

    Example:
    /memorysearch backend framework
    """
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id

    if not is_authorized(chat_id):
        logger.warning("Unauthorized Telegram chat_id attempted /memorysearch: %s", chat_id)
        await send_unauthorized_message(update, chat_id)
        return

    query = " ".join(context.args).strip()

    if not query:
        await update.message.reply_text(
            "Please provide a memory search query.\n\n"
            "Example:\n"
            "/memorysearch backend framework"
        )
        return

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.api_base_url}/memory/search",
                json={
                    "telegram_chat_id": chat_id,
                    "query": query,
                    "top_k": 5,
                },
            )

            response.raise_for_status()
            data = response.json()

        memories = data.get("memories", [])
        await update.message.reply_text(format_memory_items(memories))

    except Exception as exc:
        logger.exception("Telegram polling worker failed while searching memories")

        await update.message.reply_text(
            "I could not search your memories right now.\n\n"
            f"Technical detail: {type(exc).__name__}: {exc}"
        )


async def forget_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Delete a saved memory by ID.

    Example:
    /forget 3
    """
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id

    if not is_authorized(chat_id):
        logger.warning("Unauthorized Telegram chat_id attempted /forget: %s", chat_id)
        await send_unauthorized_message(update, chat_id)
        return

    if not context.args:
        await update.message.reply_text(
            "Please provide the memory ID you want me to forget.\n\n"
            "Example:\n"
            "/forget 3"
        )
        return

    try:
        memory_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "Memory ID must be a number.\n\n"
            "Example:\n"
            "/forget 3"
        )
        return

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.api_base_url}/memory/delete",
                json={
                    "telegram_chat_id": chat_id,
                    "memory_id": memory_id,
                },
            )

            response.raise_for_status()
            data = response.json()

        if data.get("deleted"):
            await update.message.reply_text(f"Deleted memory ID {memory_id}.")
        else:
            await update.message.reply_text(
                f"I could not find memory ID {memory_id} for your account."
            )

    except Exception as exc:
        logger.exception("Telegram polling worker failed while deleting memory")

        await update.message.reply_text(
            "I could not delete that memory right now.\n\n"
            f"Technical detail: {type(exc).__name__}: {exc}"
        )


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    user_message = update.message.text

    if not user_message:
        return

    if not is_authorized(chat_id):
        logger.warning("Unauthorized Telegram chat_id attempted access: %s", chat_id)
        await send_unauthorized_message(update, chat_id)
        return

    await update.message.reply_text("Thinking...")

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.api_base_url}/chat",
                json={
                    "message": user_message,
                    "telegram_chat_id": chat_id,
                    "source": "telegram",
                },
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
    application.add_handler(CommandHandler("remember", remember_command))
    application.add_handler(CommandHandler("memories", memories_command))
    application.add_handler(CommandHandler("memorysearch", memory_search_command))
    application.add_handler(CommandHandler("forget", forget_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message)
    )

    logger.info("Starting Telegram polling worker...")
    application.run_polling()


if __name__ == "__main__":
    main()