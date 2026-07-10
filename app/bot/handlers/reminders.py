import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.bot.api_client import (
    cancel_reminder_api,
    create_reminder_api,
    list_reminders_api,
    post_to_backend,
)
from app.bot.auth import is_authorized, send_unauthorized_message
from app.bot.formatters import format_reminder_datetime, format_reminder_items
from app.bot.keyboards import (
    back_to_reminders_keyboard,
    cancel_reminder_keyboard,
    reminder_time_keyboard,
)
from app.bot.state import clear_active_flow
from app.core.config import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()


def parse_reminder_args(args: list[str]) -> tuple[datetime, str] | None:
    if len(args) < 3:
        return None

    date_part = args[0]
    time_part = args[1]
    message = " ".join(args[2:]).strip()

    if not message:
        return None

    try:
        scheduled_naive = datetime.strptime(
            f"{date_part} {time_part}",
            "%Y-%m-%d %H:%M",
        )
    except ValueError:
        return None

    timezone = ZoneInfo(settings.timezone)
    scheduled_time = scheduled_naive.replace(tzinfo=timezone)

    return scheduled_time, message


def get_quick_reminder_time(option: str) -> datetime | None:
    timezone = ZoneInfo(settings.timezone)
    now = datetime.now(timezone)

    if option == "in_15":
        return now + timedelta(minutes=15)

    if option == "in_30":
        return now + timedelta(minutes=30)

    if option == "in_60":
        return now + timedelta(hours=1)

    if option == "in_120":
        return now + timedelta(hours=2)

    if option == "today_20":
        scheduled = now.replace(hour=20, minute=0, second=0, microsecond=0)
        if scheduled <= now:
            scheduled = scheduled + timedelta(days=1)
        return scheduled

    if option == "tomorrow_09":
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)

    if option == "tomorrow_20":
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=20, minute=0, second=0, microsecond=0)

    return None


def get_selected_reminder_day(option: str) -> datetime | None:
    timezone = ZoneInfo(settings.timezone)
    now = datetime.now(timezone)

    if option == "today":
        return now

    if option == "tomorrow":
        return now + timedelta(days=1)

    if option == "in_2_days":
        return now + timedelta(days=2)

    return None


async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id

    if not is_authorized(chat_id):
        logger.warning("Unauthorized Telegram chat_id attempted /remind: %s", chat_id)
        await send_unauthorized_message(update, chat_id)
        return

    parsed = parse_reminder_args(context.args)

    if not parsed:
        context.user_data["active_flow"] = "reminder_message"
        await update.message.reply_text(
            "What should I remind you about?",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Cancel", callback_data="flow:cancel")]]
            ),
        )
        return

    scheduled_time, message = parsed

    try:
        data = await create_reminder_api(chat_id, message, scheduled_time)
        scheduled_display = format_reminder_datetime(data.get("scheduled_time", ""))

        await update.message.reply_text(
            "Reminder created.\n\n"
            f"When: {scheduled_display}\n"
            f"Message: {message}",
            reply_markup=back_to_reminders_keyboard(),
        )

    except Exception as exc:
        logger.exception("Telegram polling worker failed while creating reminder")
        await update.message.reply_text(
            "I could not create that reminder right now.\n\n"
            f"Technical detail: {type(exc).__name__}: {exc}"
        )


async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id

    if not is_authorized(chat_id):
        logger.warning("Unauthorized Telegram chat_id attempted /reminders: %s", chat_id)
        await send_unauthorized_message(update, chat_id)
        return

    try:
        reminders = await list_reminders_api(chat_id)
        await update.message.reply_text(
            format_reminder_items(reminders),
            reply_markup=back_to_reminders_keyboard(),
        )

    except Exception as exc:
        logger.exception("Telegram polling worker failed while listing reminders")
        await update.message.reply_text(
            "I could not list your reminders right now.\n\n"
            f"Technical detail: {type(exc).__name__}: {exc}"
        )


async def cancel_reminder_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id

    if not is_authorized(chat_id):
        logger.warning("Unauthorized Telegram chat_id attempted /cancelreminder: %s", chat_id)
        await send_unauthorized_message(update, chat_id)
        return

    if not context.args:
        reminders = await list_reminders_api(chat_id)

        if not reminders:
            await update.message.reply_text(
                "No pending reminders found.",
                reply_markup=back_to_reminders_keyboard(),
            )
            return

        await update.message.reply_text(
            "Select a reminder to cancel:",
            reply_markup=cancel_reminder_keyboard(reminders),
        )
        return

    try:
        reminder_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "Please use Reminder Menu → Cancel Reminder.",
            reply_markup=back_to_reminders_keyboard(),
        )
        return

    try:
        cancelled = await cancel_reminder_api(chat_id, reminder_id)

        if cancelled:
            await update.message.reply_text(
                "Cancelled the selected reminder.",
                reply_markup=back_to_reminders_keyboard(),
            )
        else:
            await update.message.reply_text(
                "I could not find that pending reminder.",
                reply_markup=back_to_reminders_keyboard(),
            )

    except Exception as exc:
        logger.exception("Telegram polling worker failed while cancelling reminder")
        await update.message.reply_text(
            "I could not cancel that reminder right now.\n\n"
            f"Technical detail: {type(exc).__name__}: {exc}"
        )


async def handle_reminder_message_flow(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_message: str,
) -> None:
    context.user_data["pending_reminder_message"] = user_message
    context.user_data["active_flow"] = "reminder_time"

    await update.message.reply_text(
        "When should I remind you?",
        reply_markup=reminder_time_keyboard(),
    )


async def send_due_reminders_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        data = await post_to_backend(
            "/reminders/due",
            {
                "limit": 20,
            },
            timeout=30.0,
        )

        due_reminders = data.get("reminders", [])

        for reminder in due_reminders:
            reminder_id = reminder.get("id")
            telegram_chat_id = reminder.get("telegram_chat_id")
            message = reminder.get("message", "")

            if not reminder_id or not telegram_chat_id or not message:
                continue

            try:
                await context.bot.send_message(
                    chat_id=telegram_chat_id,
                    text=f"Reminder:\n\n{message}",
                )

                await post_to_backend(
                    "/reminders/mark-sent",
                    {
                        "reminder_id": reminder_id,
                    },
                    timeout=30.0,
                )

                logger.info("Sent reminder ID %s", reminder_id)

            except Exception:
                logger.exception("Failed to send reminder ID %s", reminder_id)

    except Exception:
        logger.exception("Reminder scheduler failed while checking due reminders")