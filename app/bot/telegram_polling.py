import logging
import time

import httpx
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from app.bot.handlers.chat import handle_text_message
from app.bot.handlers.core import help_command, id_command, menu_command, start_command
from app.bot.handlers.daily_summary import send_due_daily_summaries_job
from app.bot.handlers.memory import (
    forget_command,
    memories_command,
    memory_search_command,
    remember_command,
)
from app.bot.handlers.menu import handle_menu_callback
from app.bot.handlers.reminders import (
    cancel_reminder_command,
    remind_command,
    reminders_command,
    send_due_reminders_job,
)
from app.core.config import get_settings


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
settings = get_settings()


def wait_for_backend(max_attempts: int = 30, delay_seconds: int = 2) -> None:
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


def main() -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is missing. Add it to your .env file."
        )

    wait_for_backend()

    application = Application.builder().token(settings.telegram_bot_token).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("help", help_command))

    application.add_handler(CommandHandler("remember", remember_command))
    application.add_handler(CommandHandler("memories", memories_command))
    application.add_handler(CommandHandler("memorysearch", memory_search_command))
    application.add_handler(CommandHandler("forget", forget_command))

    application.add_handler(CommandHandler("remind", remind_command))
    application.add_handler(CommandHandler("reminders", reminders_command))
    application.add_handler(CommandHandler("cancelreminder", cancel_reminder_command))

    application.add_handler(CallbackQueryHandler(handle_menu_callback))

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

        application.job_queue.run_repeating(
            send_due_daily_summaries_job,
            interval=60,
            first=20,
            name="send_due_daily_summaries",
        )

        logger.info("Reminder scheduler job registered.")
        logger.info("Daily summary scheduler job registered.")
    else:
        logger.warning(
            "Telegram job queue is not available. Scheduled jobs disabled."
        )

    logger.info("Starting Telegram polling worker...")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()