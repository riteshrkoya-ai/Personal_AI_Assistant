from telegram.ext import ContextTypes


def clear_active_flow(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("active_flow", None)

    context.user_data.pop("pending_reminder_message", None)
    context.user_data.pop("pending_reminder_day", None)
    context.user_data.pop("pending_reminder_hour", None)

    context.user_data.pop("pending_study_topic", None)
    context.user_data.pop("pending_study_days", None)

    context.user_data.pop("pending_future_me_goal_title", None)
    context.user_data.pop("pending_future_me_goal_weeks", None)