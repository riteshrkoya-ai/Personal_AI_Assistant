import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.bot.api_client import complete_task_api, create_task_api, list_tasks_api
from app.bot.auth import is_authorized, send_unauthorized_message
from app.bot.formatters import format_task_items
from app.bot.keyboards import back_to_tasks_keyboard, complete_task_keyboard

logger = logging.getLogger(__name__)


async def task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id

    if not is_authorized(chat_id):
        logger.warning("Unauthorized Telegram chat_id attempted /task: %s", chat_id)
        await send_unauthorized_message(update, chat_id)
        return

    title = " ".join(context.args).strip() if context.args else ""

    if not title:
        context.user_data["active_flow"] = "task_message"
        await update.message.reply_text(
            "What's the task?",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Cancel", callback_data="flow:cancel")]]
            ),
        )
        return

    await _create_task_and_reply(update, chat_id, title)


async def _create_task_and_reply(update: Update, chat_id: int, title: str) -> None:
    try:
        await create_task_api(chat_id, title)

        await update.message.reply_text(
            f"Task added.\n\nTask: {title}",
            reply_markup=back_to_tasks_keyboard(),
        )

    except Exception as exc:
        logger.exception("Telegram polling worker failed while creating task")
        await update.message.reply_text(
            "I could not add that task right now.\n\n"
            f"Technical detail: {type(exc).__name__}: {exc}"
        )


async def handle_task_message_flow(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_message: str,
) -> None:
    context.user_data.pop("active_flow", None)

    chat_id = update.effective_chat.id
    await _create_task_and_reply(update, chat_id, user_message)


async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id

    if not is_authorized(chat_id):
        logger.warning("Unauthorized Telegram chat_id attempted /tasks: %s", chat_id)
        await send_unauthorized_message(update, chat_id)
        return

    try:
        tasks = await list_tasks_api(chat_id)
        await update.message.reply_text(
            format_task_items(tasks),
            reply_markup=back_to_tasks_keyboard(),
        )

    except Exception as exc:
        logger.exception("Telegram polling worker failed while listing tasks")
        await update.message.reply_text(
            "I could not list your tasks right now.\n\n"
            f"Technical detail: {type(exc).__name__}: {exc}"
        )


async def done_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id

    if not is_authorized(chat_id):
        logger.warning("Unauthorized Telegram chat_id attempted /donetask: %s", chat_id)
        await send_unauthorized_message(update, chat_id)
        return

    if not context.args:
        tasks = await list_tasks_api(chat_id)

        if not tasks:
            await update.message.reply_text(
                "No pending tasks found.",
                reply_markup=back_to_tasks_keyboard(),
            )
            return

        await update.message.reply_text(
            "Select a task to complete:",
            reply_markup=complete_task_keyboard(tasks),
        )
        return

    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "Please use Tasks Menu → Complete Task.",
            reply_markup=back_to_tasks_keyboard(),
        )
        return

    try:
        completed = await complete_task_api(chat_id, task_id)

        if completed:
            await update.message.reply_text(
                "Marked that task as done.",
                reply_markup=back_to_tasks_keyboard(),
            )
        else:
            await update.message.reply_text(
                "I could not find that pending task.",
                reply_markup=back_to_tasks_keyboard(),
            )

    except Exception as exc:
        logger.exception("Telegram polling worker failed while completing task")
        await update.message.reply_text(
            "I could not complete that task right now.\n\n"
            f"Technical detail: {type(exc).__name__}: {exc}"
        )
