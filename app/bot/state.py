from telegram.ext import ContextTypes


def clear_active_flow(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("active_flow", None)
    context.user_data.pop("pending_reminder_message", None)
    context.user_data.pop("pending_reminder_day", None)
    context.user_data.pop("pending_reminder_hour", None)