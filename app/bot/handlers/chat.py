import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.api_client import post_to_backend
from app.bot.auth import is_authorized, send_unauthorized_message
from app.bot.handlers.memory import handle_memory_search_flow, handle_save_memory_flow
from app.bot.handlers.reminders import handle_reminder_message_flow


logger = logging.getLogger(__name__)


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

    active_flow = context.user_data.get("active_flow")

    if active_flow == "save_memory":
        await handle_save_memory_flow(
            update=update,
            context=context,
            chat_id=chat_id,
            user_message=user_message,
        )
        return

    if active_flow == "memory_search":
        await handle_memory_search_flow(
            update=update,
            context=context,
            chat_id=chat_id,
            user_message=user_message,
        )
        return

    if active_flow == "reminder_message":
        await handle_reminder_message_flow(
            update=update,
            context=context,
            user_message=user_message,
        )
        return

    await update.message.reply_text("Thinking...")

    try:
        data = await post_to_backend(
            "/chat",
            {
                "message": user_message,
                "telegram_chat_id": chat_id,
                "source": "telegram",
            },
        )

        assistant_response = data.get("response", "I could not generate a response.")
        await update.message.reply_text(assistant_response)

    except Exception as exc:
        logger.exception("Telegram polling worker failed while calling /chat")

        await update.message.reply_text(
            "I could not reach the assistant backend right now.\n\n"
            f"Technical detail: {type(exc).__name__}: {exc}"
        )