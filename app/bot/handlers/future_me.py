import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.api_client import (
    cancel_future_me_goal_api,
    complete_future_me_task_api,
    create_future_me_goal_api,
    create_future_me_weekly_plan_api,
    list_future_me_tasks_api,
)
from app.bot.formatters import format_future_me_tasks
from app.bot.keyboards import (
    back_to_future_me_keyboard,
    complete_future_me_task_keyboard,
)
from app.bot.state import clear_active_flow


logger = logging.getLogger(__name__)


async def handle_future_me_goal_title_flow(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_message: str,
) -> None:
    title = " ".join(user_message.split()).strip()

    if not title:
        await update.message.reply_text(
            "Please enter a Future Me goal.",
            reply_markup=back_to_future_me_keyboard(),
        )
        return

    context.user_data["pending_future_me_goal_title"] = title
    context.user_data["active_flow"] = "future_me_goal_weeks"

    await update.message.reply_text(
        "In how many weeks do you want to make progress on this goal?\n\n"
        "Please enter a number between 1 and 52.\n\n"
        "Example: 4",
        reply_markup=back_to_future_me_keyboard(),
    )


async def handle_future_me_goal_weeks_flow(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_message: str,
) -> None:
    raw_weeks = user_message.strip()

    try:
        weeks = int(raw_weeks)
    except ValueError:
        await update.message.reply_text(
            "Please enter only a number between 1 and 52.\n\n"
            "Example: 4",
            reply_markup=back_to_future_me_keyboard(),
        )
        return

    if weeks < 1 or weeks > 52:
        await update.message.reply_text(
            "Please choose between 1 and 52 weeks.",
            reply_markup=back_to_future_me_keyboard(),
        )
        return

    context.user_data["pending_future_me_goal_weeks"] = weeks
    context.user_data["active_flow"] = "future_me_goal_description"

    await update.message.reply_text(
        "Add a short description or reason for this goal.\n\n"
        "Example: I want to prepare for interviews and become more confident.\n\n"
        "You can also type: skip",
        reply_markup=back_to_future_me_keyboard(),
    )


async def handle_future_me_goal_description_flow(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user_message: str,
) -> None:
    title = context.user_data.get("pending_future_me_goal_title")
    weeks = context.user_data.get("pending_future_me_goal_weeks", 4)

    description = " ".join(user_message.split()).strip()

    if description.lower() in {"skip", "none", "no"}:
        description = None

    if not title:
        clear_active_flow(context)
        await update.message.reply_text(
            "I could not create the Future Me goal because the title was missing.",
            reply_markup=back_to_future_me_keyboard(),
        )
        return

    try:
        data = await create_future_me_goal_api(
            chat_id=chat_id,
            title=title,
            description=description,
            target_weeks=weeks,
        )

        goal = data.get("goal", {})

        clear_active_flow(context)

        await update.message.reply_text(
            "Future Me goal saved.\n\n"
            f"Goal: {goal.get('title', title)}\n"
            f"Target: {goal.get('target_weeks', weeks)} week(s)\n"
            f"Target date: {goal.get('target_date', 'Not set')}\n\n"
            "Next step: Future Me → Create Weekly Plan",
            reply_markup=back_to_future_me_keyboard(),
        )

    except Exception as exc:
        logger.exception("Future Me goal creation failed")
        await update.message.reply_text(
            "I could not create that Future Me goal right now.\n\n"
            f"Technical detail: {type(exc).__name__}: {exc}",
            reply_markup=back_to_future_me_keyboard(),
        )


async def create_selected_future_me_weekly_plan(
    chat_id: int,
    goal_id: int,
    days: int = 5,
) -> dict:
    return await create_future_me_weekly_plan_api(
        chat_id=chat_id,
        goal_id=goal_id,
        days=days,
    )


async def cancel_selected_future_me_goal(
    chat_id: int,
    goal_id: int,
) -> bool:
    return await cancel_future_me_goal_api(
        chat_id=chat_id,
        goal_id=goal_id,
    )


async def complete_selected_future_me_task(
    chat_id: int,
    task_id: int,
) -> bool:
    return await complete_future_me_task_api(
        chat_id=chat_id,
        task_id=task_id,
    )


async def show_future_me_tasks_with_complete_buttons(
    update: Update,
    chat_id: int,
) -> None:
    tasks = await list_future_me_tasks_api(chat_id)

    await update.message.reply_text(
        format_future_me_tasks(tasks),
        reply_markup=complete_future_me_task_keyboard(tasks),
    )