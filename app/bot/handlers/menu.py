from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.bot.api_client import (
    cancel_reminder_api,
    create_reminder_api,
    delete_memory_api,
    disable_daily_summary_setting_api,
    get_daily_summary_api,
    list_future_me_goals_api,
    list_future_me_tasks_api,
    list_memories_api,
    list_reminders_api,
    list_study_plans_api,
    list_study_tasks_api,
    update_daily_summary_setting_api,
)
from app.bot.auth import is_authorized, send_unauthorized_callback
from app.bot.formatters import (
    format_future_me_goals,
    format_future_me_tasks,
    format_memory_items,
    format_reminder_datetime,
    format_reminder_items,
    format_study_plans,
    format_study_tasks,
)
from app.bot.handlers.future_me import (
    cancel_selected_future_me_goal,
    complete_selected_future_me_task,
    create_selected_future_me_weekly_plan,
)
from app.bot.handlers.reminders import get_quick_reminder_time, get_selected_reminder_day
from app.bot.handlers.study import (
    cancel_selected_study_plan,
    complete_selected_study_task,
    create_selected_study_reminders,
)
from app.bot.keyboards import (
    back_to_future_me_keyboard,
    back_to_main_keyboard,
    back_to_memory_keyboard,
    back_to_reminders_keyboard,
    back_to_study_keyboard,
    cancel_reminder_keyboard,
    cancel_study_plan_keyboard,
    complete_future_me_task_keyboard,
    complete_study_task_keyboard,
    daily_summary_menu_keyboard,
    daily_summary_time_keyboard,
    delete_memory_keyboard,
    future_me_goal_cancel_keyboard,
    future_me_goal_plan_keyboard,
    future_me_menu_keyboard,
    main_menu_keyboard,
    memory_menu_keyboard,
    reminder_day_keyboard,
    reminder_hour_keyboard,
    reminder_menu_keyboard,
    reminder_minute_keyboard,
    reminder_time_keyboard,
    study_menu_keyboard,
    study_reminder_time_keyboard,
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
        clear_active_flow(context)
        await query.edit_message_text(
            "Future Me options:",
            reply_markup=future_me_menu_keyboard(),
        )
        return

    if data == "menu:summary":
        clear_active_flow(context)
        await query.edit_message_text(
            "Daily Summary options:",
            reply_markup=daily_summary_menu_keyboard(),
        )
        return

    if data == "menu:help":
        await query.edit_message_text(
            "Personal AI Assistant MVP Help\n\n"
            "Use the buttons from /menu to access each feature.\n\n"
            "Available modules:\n"
            "• Memory — save, view, search, and delete personal memories\n"
            "• Reminders — create, view, cancel, and receive reminders\n"
            "• Study — create study plans, complete tasks, and add study reminders\n"
            "• Daily Summary — view or schedule a daily activity summary\n"
            "• Future Me — set long-term goals, create weekly plans, and track progress\n\n"
            "Useful shortcuts:\n"
            "/menu - open the main menu\n"
            "/remember <text> - save a memory\n"
            "/memories - view saved memories\n"
            "/memorysearch <query> - search memories\n"
            "/forget - choose a memory to delete\n"
            "/remind YYYY-MM-DD HH:MM <message> - create a reminder\n"
            "/reminders - view reminders\n"
            "/cancelreminder - choose a reminder to cancel\n\n"
            "MVP focus:\n"
            "This assistant is local-first, Telegram-based, multi-user, and designed with user data isolation.",
            reply_markup=back_to_main_keyboard(),
        )
        return

    # Daily Summary callbacks

    if data == "summary:view":
        try:
            summary = await get_daily_summary_api(chat_id)
            summary_text = summary.get("summary_text", "I could not build a daily summary.")

            await query.edit_message_text(
                summary_text,
                reply_markup=back_to_main_keyboard(),
            )
        except Exception as exc:
            await query.edit_message_text(
                "I could not generate the daily summary right now.\n\n"
                f"Technical detail: {type(exc).__name__}: {exc}",
                reply_markup=back_to_main_keyboard(),
            )
        return

    if data == "summary:enable_menu":
        await query.edit_message_text(
            "What time should I send your daily summary?",
            reply_markup=daily_summary_time_keyboard(),
        )
        return

    if data.startswith("summary_time:"):
        parts = data.split(":")

        if len(parts) != 3:
            await query.edit_message_text(
                "I could not understand that summary time.",
                reply_markup=back_to_main_keyboard(),
            )
            return

        try:
            hour = int(parts[1])
            minute = int(parts[2])
        except ValueError:
            await query.edit_message_text(
                "I could not understand that summary time.",
                reply_markup=back_to_main_keyboard(),
            )
            return

        result = await update_daily_summary_setting_api(
            chat_id=chat_id,
            hour=hour,
            minute=minute,
        )

        await query.edit_message_text(
            "Daily summary scheduled.\n\n"
            f"Time: {hour:02d}:{minute:02d}\n"
            f"Timezone: {result.get('timezone', 'America/New_York')}",
            reply_markup=back_to_main_keyboard(),
        )
        return

    if data == "summary:disable":
        await disable_daily_summary_setting_api(chat_id)

        await query.edit_message_text(
            "Daily summary turned off.",
            reply_markup=back_to_main_keyboard(),
        )
        return

    # Future Me callbacks

    if data == "future:set_goal":
        context.user_data["active_flow"] = "future_me_goal_title"
        await query.edit_message_text(
            "What goal do you want your future self to achieve?\n\n"
            "Example: Become stronger in FastAPI and AI agents",
            reply_markup=back_to_future_me_keyboard(),
        )
        return

    if data == "future:goals":
        goals = await list_future_me_goals_api(chat_id)
        await query.edit_message_text(
            format_future_me_goals(goals),
            reply_markup=back_to_future_me_keyboard(),
        )
        return

    if data == "future:plan_menu":
        goals = await list_future_me_goals_api(chat_id)

        if not goals:
            await query.edit_message_text(
                "No active Future Me goals found.\n\n"
                "Create one first using Future Me → Set Future Me Goal.",
                reply_markup=back_to_future_me_keyboard(),
            )
            return

        await query.edit_message_text(
            "Select a Future Me goal to create a weekly plan:",
            reply_markup=future_me_goal_plan_keyboard(goals),
        )
        return

    if data.startswith("future_plan:"):
        goal_id = int(data.split(":", 1)[1])

        result = await create_selected_future_me_weekly_plan(
            chat_id=chat_id,
            goal_id=goal_id,
            days=5,
        )

        tasks = result.get("tasks", [])

        if result.get("created") and tasks:
            await query.edit_message_text(
                "Future Me weekly plan is ready.\n\n"
                f"{format_future_me_tasks(tasks)}",
                reply_markup=complete_future_me_task_keyboard(tasks),
            )
        else:
            await query.edit_message_text(
                result.get("message", "I could not create a weekly plan."),
                reply_markup=back_to_future_me_keyboard(),
            )
        return

    if data == "future:tasks":
        tasks = await list_future_me_tasks_api(chat_id)
        await query.edit_message_text(
            format_future_me_tasks(tasks),
            reply_markup=complete_future_me_task_keyboard(tasks),
        )
        return

    if data.startswith("future_complete:"):
        task_id = int(data.split(":", 1)[1])

        completed = await complete_selected_future_me_task(
            chat_id=chat_id,
            task_id=task_id,
        )

        if completed:
            tasks = await list_future_me_tasks_api(chat_id)
            await query.edit_message_text(
                "Future Me task completed.\n\n"
                f"{format_future_me_tasks(tasks)}",
                reply_markup=complete_future_me_task_keyboard(tasks),
            )
        else:
            await query.edit_message_text(
                "I could not find that pending Future Me task.",
                reply_markup=back_to_future_me_keyboard(),
            )
        return

    if data == "future:cancel_menu":
        goals = await list_future_me_goals_api(chat_id)

        if not goals:
            await query.edit_message_text(
                "No active Future Me goals found.",
                reply_markup=back_to_future_me_keyboard(),
            )
            return

        await query.edit_message_text(
            "Select a Future Me goal to cancel:",
            reply_markup=future_me_goal_cancel_keyboard(goals),
        )
        return

    if data.startswith("future_cancel:"):
        goal_id = int(data.split(":", 1)[1])

        cancelled = await cancel_selected_future_me_goal(
            chat_id=chat_id,
            goal_id=goal_id,
        )

        if cancelled:
            goals = await list_future_me_goals_api(chat_id)
            await query.edit_message_text(
                "Future Me goal cancelled.\n\n"
                f"{format_future_me_goals(goals)}",
                reply_markup=back_to_future_me_keyboard(),
            )
        else:
            await query.edit_message_text(
                "I could not find that active Future Me goal.",
                reply_markup=back_to_future_me_keyboard(),
            )
        return

    # Study callbacks

    if data == "study:create":
        context.user_data["active_flow"] = "study_topic"
        await query.edit_message_text(
            "What topic do you want to study?\n\n"
            "Example: FastAPI and Docker",
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
            reply_markup=complete_study_task_keyboard(tasks),
        )
        return

    if data == "study:cancel_menu":
        study_plans = await list_study_plans_api(chat_id)

        if not study_plans:
            await query.edit_message_text(
                "No active study plans found.",
                reply_markup=back_to_study_keyboard(),
            )
            return

        await query.edit_message_text(
            "Select a study plan to cancel:",
            reply_markup=cancel_study_plan_keyboard(study_plans),
        )
        return

    if data.startswith("study_cancel:"):
        study_plan_id = int(data.split(":", 1)[1])

        cancelled = await cancel_selected_study_plan(
            chat_id=chat_id,
            study_plan_id=study_plan_id,
        )

        if cancelled:
            study_plans = await list_study_plans_api(chat_id)
            await query.edit_message_text(
                "Study plan cancelled.\n\n"
                f"{format_study_plans(study_plans)}",
                reply_markup=back_to_study_keyboard(),
            )
        else:
            await query.edit_message_text(
                "I could not find that active study plan.",
                reply_markup=back_to_study_keyboard(),
            )
        return

    if data.startswith("study_complete:"):
        task_id = int(data.split(":", 1)[1])
        completed = await complete_selected_study_task(
            chat_id=chat_id,
            task_id=task_id,
        )

        if completed:
            tasks = await list_study_tasks_api(chat_id)
            await query.edit_message_text(
                "Study task completed.\n\n"
                f"{format_study_tasks(tasks)}",
                reply_markup=complete_study_task_keyboard(tasks),
            )
        else:
            await query.edit_message_text(
                "I could not find that pending study task.",
                reply_markup=back_to_study_keyboard(),
            )
        return

    if data.startswith("study_reminder_yes:"):
        study_plan_id = int(data.split(":", 1)[1])

        await query.edit_message_text(
            "What time should I remind you each day?",
            reply_markup=study_reminder_time_keyboard(study_plan_id),
        )
        return

    if data == "study_reminder_no":
        await query.edit_message_text(
            "No study reminders added.",
            reply_markup=back_to_study_keyboard(),
        )
        return

    if data.startswith("study_reminder_time:"):
        parts = data.split(":")

        if len(parts) != 4:
            await query.edit_message_text(
                "I could not understand that reminder time.",
                reply_markup=back_to_study_keyboard(),
            )
            return

        try:
            study_plan_id = int(parts[1])
            hour = int(parts[2])
            minute = int(parts[3])
        except ValueError:
            await query.edit_message_text(
                "I could not understand that reminder time.",
                reply_markup=back_to_study_keyboard(),
            )
            return

        result = await create_selected_study_reminders(
            chat_id=chat_id,
            study_plan_id=study_plan_id,
            hour=hour,
            minute=minute,
        )

        if result.get("created"):
            await query.edit_message_text(
                "Study reminders created.\n\n"
                f"Reminder count: {result.get('reminder_count', 0)}\n"
                f"Time: {hour:02d}:{minute:02d}",
                reply_markup=back_to_study_keyboard(),
            )
        else:
            await query.edit_message_text(
                result.get(
                    "message",
                    "I could not create study reminders for this plan.",
                ),
                reply_markup=back_to_study_keyboard(),
            )
        return

    # Memory callbacks

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

    # Reminder callbacks

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

    # Generic flow cancel

    if data == "flow:cancel":
        clear_active_flow(context)
        await query.edit_message_text(
            "Cancelled.",
            reply_markup=main_menu_keyboard(),
        )
        return