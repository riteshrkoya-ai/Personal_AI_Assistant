from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.bot.api_client import (
    cancel_reminder_api,
    create_reminder_api,
    delete_memory_api,
    list_memories_api,
    list_reminders_api,
    list_study_plans_api,
    list_study_tasks_api,
)
from app.bot.auth import is_authorized, send_unauthorized_callback
from app.bot.formatters import (
    format_memory_items,
    format_reminder_datetime,
    format_reminder_items,
    format_study_plans,
    format_study_tasks,
)
from app.bot.handlers.reminders import get_quick_reminder_time, get_selected_reminder_day
from app.bot.keyboards import (
    back_to_main_keyboard,
    back_to_memory_keyboard,
    back_to_reminders_keyboard,
    back_to_study_keyboard,
    cancel_reminder_keyboard,
    delete_memory_keyboard,
    main_menu_keyboard,
    memory_menu_keyboard,
    reminder_day_keyboard,
    reminder_hour_keyboard,
    reminder_menu_keyboard,
    reminder_minute_keyboard,
    reminder_time_keyboard,
    study_menu_keyboard,
)
from app.bot.state import clear_active_flow
from app.core.config import get_settings


settings = get_settings()


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
        clear_active_flow(context)
        await query.edit_message_text(
            "Study options:",
            reply_markup=study_menu_keyboard(),
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

    if data == "study:create":
        await query.edit_message_text(
            "Create Study Plan will be added in Phase 5B.\n\n"
            "For Phase 5A, the backend database and API are ready. "
            "You can test study plan creation from FastAPI /docs.",
            reply_markup=back_to_study_keyboard(),
        )
        return

    if data == "study:list":
        study_plans = await list_study_plans_api(chat_id)
        await query.edit_message_text(
            format_study_plans(study_plans),
            reply_markup=back_to_study_keyboard(),
        )
        return

    if data == "study:tasks":
        tasks = await list_study_tasks_api(chat_id)
        await query.edit_message_text(
            format_study_tasks(tasks),
            reply_markup=back_to_study_keyboard(),
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