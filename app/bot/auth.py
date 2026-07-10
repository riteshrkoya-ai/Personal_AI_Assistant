from telegram import Update

from app.core.config import get_settings


settings = get_settings()


def get_authorized_chat_ids() -> set[int]:
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


async def send_unauthorized_callback(update: Update, chat_id: int) -> None:
    query = update.callback_query
    if not query:
        return

    await query.answer()
    await query.edit_message_text(
        "You are not authorized to use this assistant yet.\n\n"
        f"Your Telegram chat ID is: {chat_id}\n"
        "Add it to AUTHORIZED_TELEGRAM_CHAT_IDS in your local .env file."
    )