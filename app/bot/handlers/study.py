import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.api_client import (
    cancel_study_plan_api,
    complete_study_task_api,
    create_study_plan_api,
    list_study_tasks_api,
)
from app.bot.formatters import format_study_tasks
from app.bot.keyboards import back_to_study_keyboard, complete_study_task_keyboard
from app.bot.state import clear_active_flow


logger = logging.getLogger(__name__)


async def handle_study_topic_flow(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_message: str,
) -> None:
    topic = " ".join(user_message.split()).strip()

    if not topic:
        await update.message.reply_text(
            "Please enter a study topic.",
            reply_markup=back_to_study_keyboard(),
        )
        return

    context.user_data["pending_study_topic"] = topic
    context.user_data["active_flow"] = "study_days"

    await update.message.reply_text(
        "How many days do you want for this study plan?\n\n"
        "Please enter a number between 1 and 14.\n\n"
        "Example: 5",
        reply_markup=back_to_study_keyboard(),
    )


async def handle_study_days_flow(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_message: str,
) -> None:
    raw_days = user_message.strip()

    try:
        days = int(raw_days)
    except ValueError:
        await update.message.reply_text(
            "Please enter only a number between 1 and 14.\n\n"
            "Example: 5",
            reply_markup=back_to_study_keyboard(),
        )
        return

    if days < 1 or days > 14:
        await update.message.reply_text(
            "Please choose between 1 and 14 days.",
            reply_markup=back_to_study_keyboard(),
        )
        return

    context.user_data["pending_study_days"] = days
    context.user_data["active_flow"] = "study_goal"

    await update.message.reply_text(
        "What is your study goal?\n\n"
        "Example: Prepare for interviews in one week",
        reply_markup=back_to_study_keyboard(),
    )


async def handle_study_goal_flow(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user_message: str,
) -> None:
    goal = " ".join(user_message.split()).strip()
    topic = context.user_data.get("pending_study_topic")
    days = context.user_data.get("pending_study_days", 5)

    if not topic:
        clear_active_flow(context)
        await update.message.reply_text(
            "I could not create the study plan because the topic was missing.",
            reply_markup=back_to_study_keyboard(),
        )
        return

    try:
        data = await create_study_plan_api(
            chat_id=chat_id,
            topic=topic,
            goal=goal,
            days=days,
        )

        tasks = data.get("tasks", [])

        clear_active_flow(context)

        await update.message.reply_text(
            "Study plan created.\n\n"
            f"Topic: {topic}\n"
            f"Duration: {days} day(s)\n"
            f"Goal: {goal if goal else 'Not provided'}\n\n"
            f"{format_study_tasks(tasks)}",
            reply_markup=back_to_study_keyboard(),
        )

    except Exception as exc:
        logger.exception("Guided study plan creation failed")
        await update.message.reply_text(
            "I could not create that study plan right now.\n\n"
            f"Technical detail: {type(exc).__name__}: {exc}",
            reply_markup=back_to_study_keyboard(),
        )


async def complete_selected_study_task(
    chat_id: int,
    task_id: int,
) -> bool:
    return await complete_study_task_api(chat_id=chat_id, task_id=task_id)


async def show_study_tasks_with_complete_buttons(
    update: Update,
    chat_id: int,
) -> None:
    tasks = await list_study_tasks_api(chat_id)

    await update.message.reply_text(
        format_study_tasks(tasks),
        reply_markup=complete_study_task_keyboard(tasks),
    )

async def cancel_selected_study_plan(
    chat_id: int,
    study_plan_id: int,
) -> bool:
    return await cancel_study_plan_api(
        chat_id=chat_id,
        study_plan_id=study_plan_id,
    )