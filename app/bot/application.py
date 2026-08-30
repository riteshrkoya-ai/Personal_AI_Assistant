import logging

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from app.bot.handlers.chat import handle_text_message
from app.bot.handlers.core import (
    help_command,
    id_command,
    menu_command,
    start_command,
)
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
from app.bot.handlers.tasks import done_task_command, task_command, tasks_command
from app.core.config import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()


def build_telegram_application(*, webhook: bool = False) -> Application:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing.")

    builder = Application.builder().token(settings.telegram_bot_token)

    # In webhook mode FastAPI receives Telegram updates, so python-telegram-bot
    # does not need its own Updater/polling component.
    if webhook:
        builder = builder.updater(None)

    application = builder.build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("help", help_command))

    application.add_handler(CommandHandler("remember", remember_command))
    application.add_handler(CommandHandler("memories", memories_command))
    application.add_handler(
        CommandHandler("memorysearch", memory_search_command)
    )
    application.add_handler(CommandHandler("forget", forget_command))

    application.add_handler(CommandHandler("remind", remind_command))
    application.add_handler(CommandHandler("reminders", reminders_command))
    application.add_handler(
        CommandHandler("cancelreminder", cancel_reminder_command)
    )

    application.add_handler(CommandHandler("task", task_command))
    application.add_handler(CommandHandler("tasks", tasks_command))
    application.add_handler(CommandHandler("donetask", done_task_command))

    application.add_handler(
        CallbackQueryHandler(handle_menu_callback)
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_text_message,
        )
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

    return application