import logging
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
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


# -----------------------------
# Authorization helpers
# -----------------------------

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


# -----------------------------
# Backend readiness
# -----------------------------

def wait_for_backend(max_attempts: int = 30, delay_seconds: int = 2) -> None:
    """
    Wait until the FastAPI backend is ready before Telegram polling starts.
    This prevents Telegram from processing messages before /health is available.
    """
    health_url = f"{settings.api_base_url}/health"

    for attempt in range(1, max_attempts + 1):
        try:
            response = httpx.get(health_url, timeout=5.0)

            if response.status_code == 200:
                logger.info("Assistant backend is ready.")
                return

        except Exception:
            logger.info(
                "Waiting for assistant backend... attempt %s/%s",
                attempt,
                max_attempts,
            )

        time.sleep(delay_seconds)

    raise RuntimeError("Assistant backend was not ready after waiting.")


# -----------------------------
# Shared API helper
# -----------------------------

async def post_to_backend(path: str, payload: dict, timeout: float = 120.0) -> dict:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{settings.api_base_url}{path}",
            json=payload,
        )
        response.raise_for_status()
        return response.json()


# -----------------------------
# Keyboard builders
# -----------------------------

def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Memory", callback_data="menu:memory"),
                InlineKeyboardButton("Reminders", callback_data="menu:reminders"),
            ],
            [
                InlineKeyboardButton("Study", callback_data="menu:study"),
                InlineKeyboardButton("Future Me", callback_data="menu:future_me"),
            ],
            [
                InlineKeyboardButton("Daily Summary", callback_data="menu:summary"),
                InlineKeyboardButton("Help", callback_data="menu:help"),
            ],
        ]
    )


def memory_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Save Memory", callback_data="memory:save"),
                InlineKeyboardButton("View Memories", callback_data="memory:list"),
            ],
            [
                InlineKeyboardButton("Search Memories", callback_data="memory:search"),
                InlineKeyboardButton("Delete Memory", callback_data="memory:delete_menu"),
            ],
            [
                InlineKeyboardButton("Back", callback_data="menu:main"),
            ],
        ]
    )


def reminder_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Create Reminder", callback_data="reminder:create"),
                InlineKeyboardButton("View Reminders", callback_data="reminder:list"),
            ],
            [
                InlineKeyboardButton("Cancel Reminder", callback_data="reminder:cancel_menu"),
            ],
            [
                InlineKeyboardButton("Back", callback_data="menu:main"),
            ],
        ]
    )


def reminder_time_keyboard() -> InlineKeyboardMarkup:
    """
    Button-based reminder time selection.
    Normal users should not need to type date/time.
    """
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("In 15 min", callback_data="reminder_time:in_15"),
                InlineKeyboardButton("In 30 min", callback_data="reminder_time:in_30"),
            ],
            [
                InlineKeyboardButton("In 1 hour", callback_data="reminder_time:in_60"),
                InlineKeyboardButton("In 2 hours", callback_data="reminder_time:in_120"),
            ],
            [
                InlineKeyboardButton("Today 8 PM", callback_data="reminder_time:today_20"),
            ],
            [
                InlineKeyboardButton("Tomorrow 9 AM", callback_data="reminder_time:tomorrow_09"),
                InlineKeyboardButton("Tomorrow 8 PM", callback_data="reminder_time:tomorrow_20"),
            ],
            [
                InlineKeyboardButton("Pick Date/Time", callback_data="reminder_time:pick"),
                InlineKeyboardButton("Cancel", callback_data="flow:cancel"),
            ],
        ]
    )


def reminder_day_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Today", callback_data="reminder_day:today"),
                InlineKeyboardButton("Tomorrow", callback_data="reminder_day:tomorrow"),
            ],
            [
                InlineKeyboardButton("In 2 days", callback_data="reminder_day:in_2_days"),
            ],
            [
                InlineKeyboardButton("Back", callback_data="reminder:back_to_time"),
                InlineKeyboardButton("Cancel", callback_data="flow:cancel"),
            ],
        ]
    )


def reminder_hour_keyboard() -> InlineKeyboardMarkup:
    rows = []

    hours = list(range(8, 23))
    for i in range(0, len(hours), 3):
        row = [
            InlineKeyboardButton(
                f"{hour:02d}:00",
                callback_data=f"reminder_hour:{hour}",
            )
            for hour in hours[i:i + 3]
        ]
        rows.append(row)

    rows.append(
        [
            InlineKeyboardButton("Back", callback_data="reminder_time:pick"),
            InlineKeyboardButton("Cancel", callback_data="flow:cancel"),
        ]
    )

    return InlineKeyboardMarkup(rows)


def reminder_minute_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(":00", callback_data="reminder_minute:00"),
                InlineKeyboardButton(":15", callback_data="reminder_minute:15"),
            ],
            [
                InlineKeyboardButton(":30", callback_data="reminder_minute:30"),
                InlineKeyboardButton(":45", callback_data="reminder_minute:45"),
            ],
            [
                InlineKeyboardButton("Back", callback_data="reminder_day:back_to_hour"),
                InlineKeyboardButton("Cancel", callback_data="flow:cancel"),
            ],
        ]
    )


def back_to_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Main Menu", callback_data="menu:main")]
        ]
    )


def back_to_memory_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Memory Menu", callback_data="menu:memory")]
        ]
    )


def back_to_reminders_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Reminder Menu", callback_data="menu:reminders")]
        ]
    )


def delete_memory_keyboard(memories: list[dict]) -> InlineKeyboardMarkup:
    """
    Build delete buttons without exposing database IDs to the user.

    The real memory ID is still stored inside callback_data.
    """
    rows = []

    for memory in memories:
        memory_id = memory.get("id")
        content = memory.get("content", "")

        label = f"Delete: {content[:35]}"
        if len(content) > 35:
            label += "..."

        rows.append(
            [InlineKeyboardButton(label, callback_data=f"memory_delete:{memory_id}")]
        )

    rows.append([InlineKeyboardButton("Back", callback_data="menu:memory")])

    return InlineKeyboardMarkup(rows)


def cancel_reminder_keyboard(reminders: list[dict]) -> InlineKeyboardMarkup:
    """
    Build cancel buttons without exposing database IDs to the user.

    The real reminder ID is still stored inside callback_data.
    """
    rows = []

    for reminder in reminders:
        reminder_id = reminder.get("id")
        message = reminder.get("message", "")
        scheduled_time = format_reminder_datetime(reminder.get("scheduled_time", ""))

        label = f"Cancel: {scheduled_time} — {message[:25]}"
        if len(message) > 25:
            label += "..."

        rows.append(
            [InlineKeyboardButton(label, callback_data=f"reminder_cancel:{reminder_id}")]
        )

    rows.append([InlineKeyboardButton("Back", callback_data="menu:reminders")])

    return InlineKeyboardMarkup(rows)


# -----------------------------
# Formatting helpers
# -----------------------------

def format_memory_items(memories: list[dict]) -> str:
    """
    Show memories without exposing database IDs.
    """
    if not memories:
        return "No personal memories found."

    lines = ["Your saved memories:\n"]

    for memory in memories:
        content = memory.get("content", "")
        lines.append(f"• {content}")

    lines.append("\nTo delete a memory, use:")
    lines.append("Memory Menu → Delete Memory")

    return "\n".join(lines)


def parse_reminder_args(args: list[str]) -> tuple[datetime, str] | None:
    """
    Parse direct reminder command args for developer/power-user shortcut.

    Expected format:
    /remind 2026-07-09 20:00 Study FastAPI
    """
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


def format_reminder_datetime(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
        local_dt = parsed.astimezone(ZoneInfo(settings.timezone))
        return local_dt.strftime("%Y-%m-%d %I:%M %p")
    except Exception:
        return value


def format_reminder_items(reminders: list[dict]) -> str:
    """
    Show reminders without exposing database IDs.
    """
    if not reminders:
        return "No pending reminders found."

    lines = ["Your pending reminders:\n"]

    for reminder in reminders:
        message = reminder.get("message", "")
        scheduled_time = format_reminder_datetime(
            reminder.get("scheduled_time", "")
        )

        lines.append(f"• {scheduled_time} — {message}")

    lines.append("\nTo cancel a reminder, use:")
    lines.append("Reminder Menu → Cancel Reminder")

    return "\n".join(lines)


def clear_active_flow(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("active_flow", None)
    context.user_data.pop("pending_reminder_message", None)
    context.user_data.pop("pending_reminder_day", None)
    context.user_data.pop("pending_reminder_hour", None)


# -----------------------------
# API action helpers
# -----------------------------

async def save_memory_api(chat_id: int, memory_text: str) -> dict:
    return await post_to_backend(
        "/memory",
        {
            "telegram_chat_id": chat_id,
            "content": memory_text,
            "source": "telegram",
        },
    )


async def list_memories_api(chat_id: int, limit: int = 20) -> list[dict]:
    data = await post_to_backend(
        "/memory/list",
        {
            "telegram_chat_id": chat_id,
            "limit": limit,
        },
    )
    return data.get("memories", [])


async def search_memories_api(chat_id: int, query: str, top_k: int = 5) -> list[dict]:
    data = await post_to_backend(
        "/memory/search",
        {
            "telegram_chat_id": chat_id,
            "query": query,
            "top_k": top_k,
        },
    )
    return data.get("memories", [])


async def delete_memory_api(chat_id: int, memory_id: int) -> bool:
    data = await post_to_backend(
        "/memory/delete",
        {
            "telegram_chat_id": chat_id,
            "memory_id": memory_id,
        },
    )
    return bool(data.get("deleted"))


async def create_reminder_api(
    chat_id: int,
    message: str,
    scheduled_time: datetime,
) -> dict:
    return await post_to_backend(
        "/reminders",
        {
            "telegram_chat_id": chat_id,
            "message": message,
            "scheduled_time": scheduled_time.isoformat(),
            "source": "telegram",
        },
    )


async def list_reminders_api(chat_id: int, limit: int = 20) -> list[dict]:
    data = await post_to_backend(
        "/reminders/list",
        {
            "telegram_chat_id": chat_id,
            "status": "pending",
            "limit": limit,
        },
    )
    return data.get("reminders", [])


async def cancel_reminder_api(chat_id: int, reminder_id: int) -> bool:
    data = await post_to_backend(
        "/reminders/cancel",
        {
            "telegram_chat_id": chat_id,
            "reminder_id": reminder_id,
        },
    )
    return bool(data.get("cancelled"))


# -----------------------------
# Core commands
# -----------------------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    chat_id = update.effective_chat.id if update.effective_chat else None

    await update.message.reply_text(
        "AI Personal Assistant bot is running.\n\n"
        f"Your Telegram chat ID is: {chat_id}\n\n"
        "Use /menu to open the interactive assistant menu.",
        reply_markup=main_menu_keyboard(),
    )


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    chat_id = update.effective_chat.id if update.effective_chat else None

    await update.message.reply_text(
        f"Your Telegram chat ID is: {chat_id}"
    )


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    clear_active_flow(context)

    await update.message.reply_text(
        "What would you like to do?",
        reply_markup=main_menu_keyboard(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    await update.message.reply_text(
        "You can use the assistant in two ways:\n\n"
        "1. Tap buttons from /menu\n"
        "2. Use shortcut commands if you prefer typing\n\n"
        "Useful shortcuts:\n"
        "/remember <text>\n"
        "/memories\n"
        "/memorysearch <query>\n"
        "/forget - choose a memory to delete\n"
        "/remind YYYY-MM-DD HH:MM <message>\n"
        "/reminders\n"
        "/cancelreminder - choose a reminder to cancel",
        reply_markup=main_menu_keyboard(),
    )


# -----------------------------
# Memory commands
# -----------------------------

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

    # Keep typed ID support for developer/testing use, but do not advertise it to normal users.
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


# -----------------------------
# Reminder commands
# -----------------------------

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

    # Keep typed ID support for developer/testing use, but do not advertise it to normal users.
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


# -----------------------------
# Menu callback handler
# -----------------------------

async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query

    if not query or not query.message:
        return

    await query.answer()

    chat_id = query.message.chat_id
    data = query.data or ""

    if not is_authorized(chat_id):
        await send_unauthorized_callback(update, chat_id)
        return

    if data == "menu:main":
        clear_active_flow(context)
        await query.edit_message_text(
            "What would you like to do?",
            reply_markup=main_menu_keyboard(),
        )
        return

    if data == "menu:memory":
        clear_active_flow(context)
        await query.edit_message_text(
            "Memory options:",
            reply_markup=memory_menu_keyboard(),
        )
        return

    if data == "menu:reminders":
        clear_active_flow(context)
        await query.edit_message_text(
            "Reminder options:",
            reply_markup=reminder_menu_keyboard(),
        )
        return

    if data == "menu:study":
        await query.edit_message_text(
            "Study Assistant is coming in Phase 5.\n\n"
            "Soon you will be able to create study plans and track study tasks.",
            reply_markup=back_to_main_keyboard(),
        )
        return

    if data == "menu:future_me":
        await query.edit_message_text(
            "Future Me is coming in Phase 6.\n\n"
            "Soon you will be able to save goals and create weekly plans.",
            reply_markup=back_to_main_keyboard(),
        )
        return

    if data == "menu:summary":
        await query.edit_message_text(
            "Daily Summary is coming in a later phase.\n\n"
            "It will summarize your recent activity, memories, reminders, and progress.",
            reply_markup=back_to_main_keyboard(),
        )
        return

    if data == "menu:help":
        await query.edit_message_text(
            "Use the buttons to interact with the assistant.\n\n"
            "Shortcuts are also available:\n"
            "/remember <text>\n"
            "/memories\n"
            "/memorysearch <query>\n"
            "/forget - choose a memory to delete\n"
            "/remind YYYY-MM-DD HH:MM <message>\n"
            "/reminders\n"
            "/cancelreminder - choose a reminder to cancel",
            reply_markup=back_to_main_keyboard(),
        )
        return

    if data == "memory:save":
        context.user_data["active_flow"] = "save_memory"
        await query.edit_message_text(
            "What would you like me to remember?",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Cancel", callback_data="flow:cancel")]]
            ),
        )
        return

    if data == "memory:list":
        memories = await list_memories_api(chat_id)
        await query.edit_message_text(
            format_memory_items(memories),
            reply_markup=back_to_memory_keyboard(),
        )
        return

    if data == "memory:search":
        context.user_data["active_flow"] = "memory_search"
        await query.edit_message_text(
            "What memory would you like to search for?",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Cancel", callback_data="flow:cancel")]]
            ),
        )
        return

    if data == "memory:delete_menu":
        memories = await list_memories_api(chat_id)

        if not memories:
            await query.edit_message_text(
                "No personal memories found.",
                reply_markup=back_to_memory_keyboard(),
            )
            return

        await query.edit_message_text(
            "Select a memory to delete:",
            reply_markup=delete_memory_keyboard(memories),
        )
        return

    if data.startswith("memory_delete:"):
        memory_id = int(data.split(":", 1)[1])
        deleted = await delete_memory_api(chat_id, memory_id)

        if deleted:
            await query.edit_message_text(
                "Deleted the selected memory.",
                reply_markup=back_to_memory_keyboard(),
            )
        else:
            await query.edit_message_text(
                "I could not find that memory for your account.",
                reply_markup=back_to_memory_keyboard(),
            )
        return

    if data == "reminder:create":
        context.user_data["active_flow"] = "reminder_message"
        await query.edit_message_text(
            "What should I remind you about?",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Cancel", callback_data="flow:cancel")]]
            ),
        )
        return

    if data == "reminder:back_to_time":
        context.user_data["active_flow"] = "reminder_time"
        await query.edit_message_text(
            "When should I remind you?",
            reply_markup=reminder_time_keyboard(),
        )
        return

    if data == "reminder:list":
        reminders = await list_reminders_api(chat_id)
        await query.edit_message_text(
            format_reminder_items(reminders),
            reply_markup=back_to_reminders_keyboard(),
        )
        return

    if data == "reminder:cancel_menu":
        reminders = await list_reminders_api(chat_id)

        if not reminders:
            await query.edit_message_text(
                "No pending reminders found.",
                reply_markup=back_to_reminders_keyboard(),
            )
            return

        await query.edit_message_text(
            "Select a reminder to cancel:",
            reply_markup=cancel_reminder_keyboard(reminders),
        )
        return

    if data.startswith("reminder_cancel:"):
        reminder_id = int(data.split(":", 1)[1])
        cancelled = await cancel_reminder_api(chat_id, reminder_id)

        if cancelled:
            await query.edit_message_text(
                "Cancelled the selected reminder.",
                reply_markup=back_to_reminders_keyboard(),
            )
        else:
            await query.edit_message_text(
                "I could not find that pending reminder.",
                reply_markup=back_to_reminders_keyboard(),
            )
        return

    if data.startswith("reminder_time:"):
        option = data.split(":", 1)[1]

        if option == "pick":
            context.user_data["active_flow"] = "reminder_pick_day"
            await query.edit_message_text(
                "Choose the reminder day:",
                reply_markup=reminder_day_keyboard(),
            )
            return

        scheduled_time = get_quick_reminder_time(option)
        message = context.user_data.get("pending_reminder_message")

        if not scheduled_time or not message:
            clear_active_flow(context)
            await query.edit_message_text(
                "I could not create the reminder because the reminder details were missing.",
                reply_markup=back_to_reminders_keyboard(),
            )
            return

        reminder = await create_reminder_api(chat_id, message, scheduled_time)
        scheduled_display = format_reminder_datetime(reminder.get("scheduled_time", ""))

        clear_active_flow(context)

        await query.edit_message_text(
            "Reminder created.\n\n"
            f"When: {scheduled_display}\n"
            f"Message: {message}",
            reply_markup=back_to_reminders_keyboard(),
        )
        return

    if data.startswith("reminder_day:"):
        option = data.split(":", 1)[1]

        if option == "back_to_hour":
            context.user_data["active_flow"] = "reminder_pick_hour"
            await query.edit_message_text(
                "Choose the reminder hour:",
                reply_markup=reminder_hour_keyboard(),
            )
            return

        selected_day = get_selected_reminder_day(option)

        if not selected_day:
            await query.edit_message_text(
                "I could not understand that day selection.",
                reply_markup=back_to_reminders_keyboard(),
            )
            return

        context.user_data["pending_reminder_day"] = selected_day.isoformat()
        context.user_data["active_flow"] = "reminder_pick_hour"

        await query.edit_message_text(
            "Choose the reminder hour:",
            reply_markup=reminder_hour_keyboard(),
        )
        return

    if data.startswith("reminder_hour:"):
        hour_text = data.split(":", 1)[1]

        try:
            hour = int(hour_text)
        except ValueError:
            await query.edit_message_text(
                "I could not understand that hour selection.",
                reply_markup=back_to_reminders_keyboard(),
            )
            return

        context.user_data["pending_reminder_hour"] = hour
        context.user_data["active_flow"] = "reminder_pick_minute"

        await query.edit_message_text(
            "Choose the reminder minutes:",
            reply_markup=reminder_minute_keyboard(),
        )
        return

    if data.startswith("reminder_minute:"):
        minute_text = data.split(":", 1)[1]

        try:
            minute = int(minute_text)
        except ValueError:
            await query.edit_message_text(
                "I could not understand that minute selection.",
                reply_markup=back_to_reminders_keyboard(),
            )
            return

        day_raw = context.user_data.get("pending_reminder_day")
        hour = context.user_data.get("pending_reminder_hour")
        message = context.user_data.get("pending_reminder_message")

        if not day_raw or hour is None or not message:
            clear_active_flow(context)
            await query.edit_message_text(
                "I could not create the reminder because the reminder details were missing.",
                reply_markup=back_to_reminders_keyboard(),
            )
            return

        try:
            selected_day = datetime.fromisoformat(day_raw)
        except ValueError:
            clear_active_flow(context)
            await query.edit_message_text(
                "I could not create the reminder because the selected day was invalid.",
                reply_markup=back_to_reminders_keyboard(),
            )
            return

        scheduled_time = selected_day.replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
        )

        timezone = ZoneInfo(settings.timezone)
        now = datetime.now(timezone)

        if scheduled_time <= now:
            context.user_data["active_flow"] = "reminder_pick_day"
            await query.edit_message_text(
                "That time has already passed. Please choose another day and time.",
                reply_markup=reminder_day_keyboard(),
            )
            return

        reminder = await create_reminder_api(chat_id, message, scheduled_time)
        scheduled_display = format_reminder_datetime(reminder.get("scheduled_time", ""))

        clear_active_flow(context)

        await query.edit_message_text(
            "Reminder created.\n\n"
            f"When: {scheduled_display}\n"
            f"Message: {message}",
            reply_markup=back_to_reminders_keyboard(),
        )
        return

    if data == "flow:cancel":
        clear_active_flow(context)
        await query.edit_message_text(
            "Cancelled.",
            reply_markup=main_menu_keyboard(),
        )
        return


# -----------------------------
# Text message handler
# -----------------------------

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
        return

    if active_flow == "memory_search":
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
        return

    if active_flow == "reminder_message":
        context.user_data["pending_reminder_message"] = user_message
        context.user_data["active_flow"] = "reminder_time"

        await update.message.reply_text(
            "When should I remind you?",
            reply_markup=reminder_time_keyboard(),
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


# -----------------------------
# Reminder scheduler job
# -----------------------------

async def send_due_reminders_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Periodically check the backend for due reminders and send them through Telegram.
    """
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


# -----------------------------
# App entry point
# -----------------------------

def main() -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is missing. Add it to your .env file."
        )

    wait_for_backend()

    application = Application.builder().token(settings.telegram_bot_token).build()

    # Core commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("help", help_command))

    # Memory commands
    application.add_handler(CommandHandler("remember", remember_command))
    application.add_handler(CommandHandler("memories", memories_command))
    application.add_handler(CommandHandler("memorysearch", memory_search_command))
    application.add_handler(CommandHandler("forget", forget_command))

    # Reminder commands
    application.add_handler(CommandHandler("remind", remind_command))
    application.add_handler(CommandHandler("reminders", reminders_command))
    application.add_handler(CommandHandler("cancelreminder", cancel_reminder_command))

    # Button callbacks
    application.add_handler(CallbackQueryHandler(handle_menu_callback))

    # General chat and guided-flow text
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message)
    )

    if application.job_queue:
        application.job_queue.run_repeating(
            send_due_reminders_job,
            interval=30,
            first=10,
            name="send_due_reminders",
        )
        logger.info("Reminder scheduler job registered.")
    else:
        logger.warning("Telegram job queue is not available. Reminder scheduler disabled.")

    logger.info("Starting Telegram polling worker...")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()