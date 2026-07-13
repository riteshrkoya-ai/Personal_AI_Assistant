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

def format_study_plans(study_plans: list[dict]) -> str:
    if not study_plans:
        return "No active study plans found."

    lines = ["Your active study plans:\n"]

    for plan in study_plans:
        topic = plan.get("topic", "")
        goal = plan.get("goal")

        if goal:
            lines.append(f"• {topic}\n  Goal: {goal}")
        else:
            lines.append(f"• {topic}")

    lines.append("\nTo create a new study plan, use:")
    lines.append("Study Menu → Create Study Plan")

    return "\n".join(lines)


def format_study_tasks(tasks: list[dict]) -> str:
    if not tasks:
        return "No study tasks found."

    lines = ["Your study tasks:\n"]

    for task in tasks:
        day_number = task.get("day_number")
        title = task.get("title", "")
        description = task.get("description")
        status = task.get("status", "")

        status_label = "Done" if status == "completed" else "Pending"

        lines.append(f"• Day {day_number}: {title}")
        lines.append(f"  Status: {status_label}")

        if description:
            lines.append(f"  {description}")

        lines.append("")

    return "\n".join(lines).strip()

def format_future_me_goals(goals: list[dict]) -> str:
    if not goals:
        return "No active Future Me goals found."

    lines = ["Your active Future Me goals:\n"]

    for goal in goals:
        title = goal.get("title", "")
        description = goal.get("description")
        target_weeks = goal.get("target_weeks")
        target_date = goal.get("target_date")

        lines.append(f"• {title}")

        if description:
            lines.append(f"  Why: {description}")

        if target_weeks:
            lines.append(f"  Target: {target_weeks} week(s)")

        if target_date:
            lines.append(f"  Target date: {target_date}")

        lines.append("")

    lines.append("To create a weekly plan, use:")
    lines.append("Future Me → Create Weekly Plan")

    return "\n".join(lines).strip()


def format_future_me_tasks(tasks: list[dict]) -> str:
    if not tasks:
        return "No Future Me tasks found."

    lines = ["Your Future Me tasks:\n"]

    for task in tasks:
        day_number = task.get("day_number")
        title = task.get("title", "")
        description = task.get("description")
        status = task.get("status", "")
        due_date = task.get("due_date")

        if status == "completed":
            status_label = "Done"
        elif status == "cancelled":
            status_label = "Cancelled"
        else:
            status_label = "Pending"

        lines.append(f"• Day {day_number}: {title}")
        lines.append(f"  Status: {status_label}")

        if due_date:
            lines.append(f"  Due: {due_date}")

        if description:
            lines.append(f"  {description}")

        lines.append("")

    return "\n".join(lines).strip()