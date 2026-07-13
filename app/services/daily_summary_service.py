from datetime import datetime, time
from datetime import date
from zoneinfo import ZoneInfo


from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.personal_memory import PersonalMemory
from app.models.reminder import Reminder
from app.models.study import StudyPlan, StudyTask
from app.models.daily_summary import DailySummarySetting
from app.models.user import User

def _clip_text(text: str, limit: int = 80) -> str:
    clean_text = " ".join((text or "").split()).strip()

    if len(clean_text) <= limit:
        return clean_text

    return clean_text[: limit - 3] + "..."


def _get_day_range(timezone_name: str) -> tuple[datetime, datetime]:
    timezone = ZoneInfo(timezone_name)
    now = datetime.now(timezone)

    start_of_day = datetime.combine(
        now.date(),
        time.min,
        tzinfo=timezone,
    )

    end_of_day = datetime.combine(
        now.date(),
        time.max,
        tzinfo=timezone,
    )

    return start_of_day, end_of_day


async def build_daily_summary(
    session: AsyncSession,
    user_id: int,
    timezone_name: str,
) -> dict:
    start_of_day, end_of_day = _get_day_range(timezone_name)

    active_plans_result = await session.execute(
        select(StudyPlan)
        .where(
            StudyPlan.user_id == user_id,
            StudyPlan.status == "active",
        )
        .order_by(StudyPlan.created_at.desc())
        .limit(5)
    )
    active_plans = list(active_plans_result.scalars().all())

    completed_tasks_today_result = await session.execute(
        select(StudyTask)
        .where(
            StudyTask.user_id == user_id,
            StudyTask.status == "completed",
            StudyTask.completed_at.is_not(None),
            StudyTask.completed_at >= start_of_day,
            StudyTask.completed_at <= end_of_day,
        )
        .order_by(StudyTask.completed_at.desc())
        .limit(10)
    )
    completed_tasks_today = list(completed_tasks_today_result.scalars().all())

    pending_tasks_result = await session.execute(
        select(StudyTask)
        .where(
            StudyTask.user_id == user_id,
            StudyTask.status == "pending",
        )
        .order_by(StudyTask.study_plan_id.desc(), StudyTask.day_number.asc())
        .limit(10)
    )
    pending_tasks = list(pending_tasks_result.scalars().all())

    pending_reminders_result = await session.execute(
        select(Reminder)
        .where(
            Reminder.user_id == user_id,
            Reminder.status == "pending",
        )
        .order_by(Reminder.scheduled_time.asc())
        .limit(10)
    )
    pending_reminders = list(pending_reminders_result.scalars().all())

    reminders_due_today_result = await session.execute(
        select(Reminder)
        .where(
            Reminder.user_id == user_id,
            Reminder.status == "pending",
            Reminder.scheduled_time >= start_of_day,
            Reminder.scheduled_time <= end_of_day,
        )
        .order_by(Reminder.scheduled_time.asc())
        .limit(10)
    )
    reminders_due_today = list(reminders_due_today_result.scalars().all())

    memories_today_result = await session.execute(
        select(PersonalMemory)
        .where(
            PersonalMemory.user_id == user_id,
            PersonalMemory.created_at >= start_of_day,
            PersonalMemory.created_at <= end_of_day,
        )
        .order_by(PersonalMemory.created_at.desc())
        .limit(5)
    )
    memories_today = list(memories_today_result.scalars().all())

    summary_text = format_daily_summary_text(
        active_plans=active_plans,
        completed_tasks_today=completed_tasks_today,
        pending_tasks=pending_tasks,
        pending_reminders=pending_reminders,
        reminders_due_today=reminders_due_today,
        memories_today=memories_today,
        timezone_name=timezone_name,
    )

    return {
        "summary_text": summary_text,
        "counts": {
            "active_study_plans": len(active_plans),
            "completed_study_tasks_today": len(completed_tasks_today),
            "pending_study_tasks": len(pending_tasks),
            "pending_reminders": len(pending_reminders),
            "reminders_due_today": len(reminders_due_today),
            "memories_saved_today": len(memories_today),
        },
    }


def format_daily_summary_text(
    active_plans: list[StudyPlan],
    completed_tasks_today: list[StudyTask],
    pending_tasks: list[StudyTask],
    pending_reminders: list[Reminder],
    reminders_due_today: list[Reminder],
    memories_today: list[PersonalMemory],
    timezone_name: str,
) -> str:
    lines: list[str] = []

    lines.append("Daily Summary")
    lines.append("")

    lines.append("Study")
    if active_plans:
        lines.append(f"• Active study plans: {len(active_plans)}")
        for plan in active_plans[:3]:
            if plan.goal:
                lines.append(f"  - {plan.topic} — Goal: {_clip_text(plan.goal, 60)}")
            else:
                lines.append(f"  - {plan.topic}")
    else:
        lines.append("• No active study plans.")

    if completed_tasks_today:
        lines.append(f"• Completed study tasks today: {len(completed_tasks_today)}")
        for task in completed_tasks_today[:3]:
            lines.append(f"  - Day {task.day_number}: {_clip_text(task.title, 70)}")
    else:
        lines.append("• Completed study tasks today: 0")

    if pending_tasks:
        lines.append(f"• Pending study tasks: {len(pending_tasks)}")
        next_task = pending_tasks[0]
        lines.append(
            f"• Suggested next study task: Day {next_task.day_number}: "
            f"{_clip_text(next_task.title, 70)}"
        )
    else:
        lines.append("• No pending study tasks.")

    lines.append("")
    lines.append("Reminders")
    lines.append(f"• Pending reminders: {len(pending_reminders)}")

    if reminders_due_today:
        lines.append(f"• Reminders due today: {len(reminders_due_today)}")
        for reminder in reminders_due_today[:3]:
            scheduled = reminder.scheduled_time.strftime("%I:%M %p")
            lines.append(f"  - {scheduled}: {_clip_text(reminder.message, 70)}")
    else:
        lines.append("• No reminders due today.")

    lines.append("")
    lines.append("Memory")
    if memories_today:
        lines.append(f"• Memories saved today: {len(memories_today)}")
        for memory in memories_today[:3]:
            lines.append(f"  - {_clip_text(memory.content, 70)}")
    else:
        lines.append("• No new memories saved today.")

    lines.append("")
    lines.append("Suggested Next Step")

    if pending_tasks:
        next_task = pending_tasks[0]
        lines.append(
            f"Complete your next study task: Day {next_task.day_number}: "
            f"{_clip_text(next_task.title, 80)}"
        )
    elif reminders_due_today:
        next_reminder = reminders_due_today[0]
        lines.append(
            f"Focus on your next reminder: {_clip_text(next_reminder.message, 80)}"
        )
    elif active_plans:
        lines.append("Review your active study plan and decide the next task.")
    else:
        lines.append("Create a study plan or save a memory to make the assistant more useful.")

    lines.append("")
    lines.append(f"Timezone: {timezone_name}")

    return "\n".join(lines)

async def get_or_create_daily_summary_setting(
    session: AsyncSession,
    user_id: int,
    timezone_name: str,
) -> DailySummarySetting:
    result = await session.execute(
        select(DailySummarySetting).where(
            DailySummarySetting.user_id == user_id,
        )
    )

    setting = result.scalar_one_or_none()

    if setting:
        return setting

    setting = DailySummarySetting(
        user_id=user_id,
        is_enabled=False,
        hour=20,
        minute=0,
        timezone=timezone_name,
    )

    session.add(setting)
    await session.flush()

    return setting


async def update_daily_summary_setting(
    session: AsyncSession,
    user_id: int,
    hour: int,
    minute: int,
    timezone_name: str,
) -> DailySummarySetting:
    if hour < 0 or hour > 23:
        raise ValueError("Hour must be between 0 and 23.")

    if minute < 0 or minute > 59:
        raise ValueError("Minute must be between 0 and 59.")

    setting = await get_or_create_daily_summary_setting(
        session=session,
        user_id=user_id,
        timezone_name=timezone_name,
    )

    setting.is_enabled = True
    setting.hour = hour
    setting.minute = minute
    setting.timezone = timezone_name

    await session.flush()

    return setting


async def disable_daily_summary_setting(
    session: AsyncSession,
    user_id: int,
    timezone_name: str,
) -> DailySummarySetting:
    setting = await get_or_create_daily_summary_setting(
        session=session,
        user_id=user_id,
        timezone_name=timezone_name,
    )

    setting.is_enabled = False

    await session.flush()

    return setting


async def list_due_daily_summary_settings(
    session: AsyncSession,
    now_utc: datetime,
    limit: int = 50,
) -> list[tuple[DailySummarySetting, int]]:
    result = await session.execute(
        select(DailySummarySetting, User.telegram_chat_id)
        .join(User, User.id == DailySummarySetting.user_id)
        .where(
            DailySummarySetting.is_enabled.is_(True),
            User.telegram_chat_id.is_not(None),
        )
        .limit(limit)
    )

    rows = result.all()
    due_items: list[tuple[DailySummarySetting, int]] = []

    for setting, telegram_chat_id in rows:
        timezone_obj = ZoneInfo(setting.timezone)
        local_now = now_utc.astimezone(timezone_obj)
        local_today = local_now.date()

        scheduled_today = datetime(
            year=local_now.year,
            month=local_now.month,
            day=local_now.day,
            hour=setting.hour,
            minute=setting.minute,
            second=0,
            microsecond=0,
            tzinfo=timezone_obj,
        )

        already_sent_today = setting.last_sent_date == local_today

        if local_now >= scheduled_today and not already_sent_today:
            due_items.append((setting, telegram_chat_id))

    return due_items


async def mark_daily_summary_sent(
    session: AsyncSession,
    setting_id: int,
    sent_date: date,
) -> bool:
    result = await session.execute(
        select(DailySummarySetting).where(
            DailySummarySetting.id == setting_id,
        )
    )

    setting = result.scalar_one_or_none()

    if not setting:
        return False

    setting.last_sent_date = sent_date

    await session.flush()

    return True