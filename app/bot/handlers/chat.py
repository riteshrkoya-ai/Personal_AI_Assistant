import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.api_client import get_daily_summary_api, post_to_backend
from app.bot.auth import is_authorized, send_unauthorized_message
from app.bot.handlers.future_me import (
    handle_future_me_goal_description_flow,
    handle_future_me_goal_title_flow,
    handle_future_me_goal_weeks_flow,
)
from app.bot.handlers.memory import handle_memory_search_flow, handle_save_memory_flow
from app.bot.handlers.reminders import handle_reminder_message_flow
from app.bot.handlers.study import (
    handle_study_days_flow,
    handle_study_goal_flow,
    handle_study_topic_flow,
)


logger = logging.getLogger(__name__)


def is_planning_or_progress_question(user_message: str) -> bool:
    normalized = " ".join(user_message.lower().split()).strip()

    trigger_phrases = [
        "what should i do today",
        "what should i do now",
        "what should i focus on",
        "what is my next step",
        "what's my next step",
        "what should i work on",
        "what is my progress",
        "what's my progress",
        "how am i doing",
        "summarize my progress",
        "what do i need to do",
        "what are my pending tasks",
    ]

    return any(phrase in normalized for phrase in trigger_phrases)


def extract_suggested_next_step(summary_text: str) -> str | None:
    marker = "Suggested Next Step"

    if marker not in summary_text:
        return None

    after_marker = summary_text.split(marker, 1)[1].strip()

    if "Timezone:" in after_marker:
        after_marker = after_marker.split("Timezone:", 1)[0].strip()

    return after_marker or None


async def handle_planning_or_progress_question(
    update: Update,
    chat_id: int,
) -> None:
    await update.message.reply_text("Checking your current plans...")

    try:
        summary = await get_daily_summary_api(chat_id)
        summary_text = summary.get("summary_text", "")

        suggested_next_step = extract_suggested_next_step(summary_text)

        if suggested_next_step:
            await update.message.reply_text(
                "Based on your current plans, I would focus on this next:\n\n"
                f"{suggested_next_step}\n\n"
                "For the full breakdown, open Daily Summary from /menu."
            )
            return

        await update.message.reply_text(
            "I checked your current plans, but I could not find a clear next step yet.\n\n"
            "Try creating a Study plan, Future Me goal, reminder, or memory first."
        )

    except Exception as exc:
        logger.exception("Failed while building quick planning/progress response")
        await update.message.reply_text(
            "I could not check your current plans right now.\n\n"
            f"Technical detail: {type(exc).__name__}: {exc}"
        )


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

    if active_flow == "study_topic":
        await handle_study_topic_flow(
            update=update,
            context=context,
            user_message=user_message,
        )
        return

    if active_flow == "study_days":
        await handle_study_days_flow(
            update=update,
            context=context,
            user_message=user_message,
        )
        return

    if active_flow == "study_goal":
        await handle_study_goal_flow(
            update=update,
            context=context,
            chat_id=chat_id,
            user_message=user_message,
        )
        return

    if active_flow == "future_me_goal_title":
        await handle_future_me_goal_title_flow(
            update=update,
            context=context,
            user_message=user_message,
        )
        return

    if active_flow == "future_me_goal_weeks":
        await handle_future_me_goal_weeks_flow(
            update=update,
            context=context,
            user_message=user_message,
        )
        return

    if active_flow == "future_me_goal_description":
        await handle_future_me_goal_description_flow(
            update=update,
            context=context,
            chat_id=chat_id,
            user_message=user_message,
        )
        return

    if is_planning_or_progress_question(user_message):
        await handle_planning_or_progress_question(
            update=update,
            chat_id=chat_id,
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