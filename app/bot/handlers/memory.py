import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.bot.api_client import (
    delete_memory_api,
    list_memories_api,
    save_memory_api,
    search_memories_api,
)
from app.bot.auth import is_authorized, send_unauthorized_message
from app.bot.formatters import format_memory_items
from app.bot.keyboards import back_to_memory_keyboard, delete_memory_keyboard
from app.bot.state import clear_active_flow


logger = logging.getLogger(__name__)


async def remember_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id

    if not is_authorized(chat_id):
        logger.warning("Unauthorized Telegram chat_id attempted /remember: %s", chat_id)
        await send_unauthorized_message(update, chat_id)
        return

    memory_text = " ".join(context.args).strip()

    if not memory_text:
        context.user_data["active_flow"] = "save_memory"
        await update.message.reply_text(
            "What would you like me to remember?",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Cancel", callback_data="flow:cancel")]]
            ),
        )
        return

    try:
        await save_memory_api(chat_id, memory_text)

        await update.message.reply_text(
            "Saved this to your personal memory.",
            reply_markup=back_to_memory_keyboard(),
        )

    except Exception as exc:
        logger.exception("Telegram polling worker failed while saving memory")
        await update.message.reply_text(
            "I could not save that memory right now.\n\n"
            f"Technical detail: {type(exc).__name__}: {exc}"
        )


async def memories_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id

    if not is_authorized(chat_id):
        logger.warning("Unauthorized Telegram chat_id attempted /memories: %s", chat_id)
        await send_unauthorized_message(update, chat_id)
        return

    try:
        memories = await list_memories_api(chat_id)
        await update.message.reply_text(
            format_memory_items(memories),
            reply_markup=back_to_memory_keyboard(),
        )

    except Exception as exc:
        logger.exception("Telegram polling worker failed while listing memories")
        await update.message.reply_text(
            "I could not list your memories right now.\n\n"
            f"Technical detail: {type(exc).__name__}: {exc}"
        )


async def memory_search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id

    if not is_authorized(chat_id):
        logger.warning("Unauthorized Telegram chat_id attempted /memorysearch: %s", chat_id)
        await send_unauthorized_message(update, chat_id)
        return

    query = " ".join(context.args).strip()

    if not query:
        context.user_data["active_flow"] = "memory_search"
        await update.message.reply_text(
            "What memory would you like to search for?",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Cancel", callback_data="flow:cancel")]]
            ),
        )
        return

    try:
        memories = await search_memories_api(chat_id, query)
        await update.message.reply_text(
            format_memory_items(memories),
            reply_markup=back_to_memory_keyboard(),
        )

    except Exception as exc:
        logger.exception("Telegram polling worker failed while searching memories")
        await update.message.reply_text(
            "I could not search your memories right now.\n\n"
            f"Technical detail: {type(exc).__name__}: {exc}"
        )


async def forget_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id

    if not is_authorized(chat_id):
        logger.warning("Unauthorized Telegram chat_id attempted /forget: %s", chat_id)
        await send_unauthorized_message(update, chat_id)
        return

    if not context.args:
        memories = await list_memories_api(chat_id)

        if not memories:
            await update.message.reply_text(
                "No personal memories found.",
                reply_markup=back_to_memory_keyboard(),
            )
            return

        await update.message.reply_text(
            "Select a memory to delete:",
            reply_markup=delete_memory_keyboard(memories),
        )
        return

    try:
        memory_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "Please use Memory Menu → Delete Memory.",
            reply_markup=back_to_memory_keyboard(),
        )
        return

    try:
        deleted = await delete_memory_api(chat_id, memory_id)

        if deleted:
            await update.message.reply_text(
                "Deleted the selected memory.",
                reply_markup=back_to_memory_keyboard(),
            )
        else:
            await update.message.reply_text(
                "I could not find that memory for your account.",
                reply_markup=back_to_memory_keyboard(),
            )

    except Exception as exc:
        logger.exception("Telegram polling worker failed while deleting memory")
        await update.message.reply_text(
            "I could not delete that memory right now.\n\n"
            f"Technical detail: {type(exc).__name__}: {exc}"
        )


async def handle_save_memory_flow(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user_message: str,
) -> None:
    try:
        await save_memory_api(chat_id, user_message)

        clear_active_flow(context)

        await update.message.reply_text(
            "Saved this to your personal memory.",
            reply_markup=back_to_memory_keyboard(),
        )

    except Exception as exc:
        logger.exception("Guided memory save failed")
        await update.message.reply_text(
            "I could not save that memory right now.\n\n"
            f"Technical detail: {type(exc).__name__}: {exc}"
        )


async def handle_memory_search_flow(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user_message: str,
) -> None:
    try:
        memories = await search_memories_api(chat_id, user_message)

        clear_active_flow(context)

        await update.message.reply_text(
            format_memory_items(memories),
            reply_markup=back_to_memory_keyboard(),
        )

    except Exception as exc:
        logger.exception("Guided memory search failed")
        await update.message.reply_text(
            "I could not search your memories right now.\n\n"
            f"Technical detail: {type(exc).__name__}: {exc}"
        )