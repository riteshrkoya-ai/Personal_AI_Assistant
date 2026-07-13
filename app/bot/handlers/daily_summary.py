import logging

from telegram.ext import ContextTypes

from app.bot.api_client import (
    list_due_daily_summaries_api,
    mark_daily_summary_sent_api,
)

logger = logging.getLogger(__name__)


async def send_due_daily_summaries_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        due_summaries = await list_due_daily_summaries_api(limit=50)

        for item in due_summaries:
            setting_id = item.get("setting_id")
            telegram_chat_id = item.get("telegram_chat_id")
            summary_text = item.get("summary_text")

            if not setting_id or not telegram_chat_id or not summary_text:
                continue

            await context.bot.send_message(
                chat_id=telegram_chat_id,
                text=summary_text,
            )

            await mark_daily_summary_sent_api(setting_id)

    except Exception:
        logger.exception("Failed while sending due daily summaries")