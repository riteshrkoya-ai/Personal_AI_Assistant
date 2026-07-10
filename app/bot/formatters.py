from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import get_settings


settings = get_settings()


def format_memory_items(memories: list[dict]) -> str:
    if not memories:
        return "No personal memories found."

    lines = ["Your saved memories:\n"]

    for memory in memories:
        content = memory.get("content", "")
        lines.append(f"• {content}")

    lines.append("\nTo delete a memory, use:")
    lines.append("Memory Menu → Delete Memory")

    return "\n".join(lines)


def format_reminder_datetime(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
        local_dt = parsed.astimezone(ZoneInfo(settings.timezone))
        return local_dt.strftime("%Y-%m-%d %I:%M %p")
    except Exception:
        return value


def format_reminder_items(reminders: list[dict]) -> str:
    if not reminders:
        return "No pending reminders found."

    lines = ["Your pending reminders:\n"]

    for reminder in reminders:
        message = reminder.get("message", "")
        scheduled_time = format_reminder_datetime(
            reminder.get("scheduled_time", "")
        )

        lines.append(f"• {scheduled_time} — {message}")

    lines.append("\nTo cancel a reminder, use:")
    lines.append("Reminder Menu → Cancel Reminder")

    return "\n".join(lines)