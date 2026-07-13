from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models.reminder import Reminder
from app.services.reminder_service import create_reminder

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.study import StudyPlan, StudyTask


def build_study_tasks(topic: str, days: int) -> list[dict]:
    """
    Build simple default study tasks for Phase 5A.

    Later in Phase 5B/5C, we can make this LLM-generated and more personalized.
    """
    base_tasks = [
        {
            "title": f"Understand the basics of {topic}",
            "description": f"Review the core concepts, definitions, and common use cases of {topic}.",
        },
        {
            "title": f"Practice small examples with {topic}",
            "description": f"Build or review simple examples to understand how {topic} works in practice.",
        },
        {
            "title": f"Learn common interview questions on {topic}",
            "description": f"Prepare short, clear answers for common beginner-to-intermediate questions on {topic}.",
        },
        {
            "title": f"Build a mini project using {topic}",
            "description": f"Apply {topic} in a small hands-on task or mini project.",
        },
        {
            "title": f"Review and explain {topic} out loud",
            "description": f"Summarize what you learned and practice explaining {topic} clearly.",
        },
    ]

    tasks: list[dict] = []

    for index in range(days):
        template = base_tasks[index % len(base_tasks)]
        tasks.append(
            {
                "day_number": index + 1,
                "title": template["title"],
                "description": template["description"],
            }
        )

    return tasks


async def create_study_plan(
    session: AsyncSession,
    user_id: int,
    topic: str,
    goal: str | None = None,
    days: int = 5,
    source: str = "telegram",
) -> tuple[StudyPlan, list[StudyTask]]:
    clean_topic = " ".join((topic or "").split()).strip()
    clean_goal = " ".join((goal or "").split()).strip() if goal else None

    if not clean_topic:
        raise ValueError("Study topic cannot be empty.")

    days = max(1, min(days, 14))

    study_plan = StudyPlan(
        user_id=user_id,
        topic=clean_topic,
        goal=clean_goal,
        status="active",
        source=source,
    )

    session.add(study_plan)
    await session.flush()

    task_payloads = build_study_tasks(topic=clean_topic, days=days)

    study_tasks: list[StudyTask] = []

    for task_payload in task_payloads:
        task = StudyTask(
            user_id=user_id,
            study_plan_id=study_plan.id,
            day_number=task_payload["day_number"],
            title=task_payload["title"],
            description=task_payload["description"],
            status="pending",
        )
        session.add(task)
        study_tasks.append(task)

    await session.flush()

    return study_plan, study_tasks


async def list_user_study_plans(
    session: AsyncSession,
    user_id: int,
    status: str | None = "active",
    limit: int = 20,
) -> list[StudyPlan]:
    query = select(StudyPlan).where(StudyPlan.user_id == user_id)

    if status:
        query = query.where(StudyPlan.status == status)

    result = await session.execute(
        query.order_by(StudyPlan.created_at.desc()).limit(limit)
    )

    return list(result.scalars().all())


async def list_user_study_tasks(
    session: AsyncSession,
    user_id: int,
    study_plan_id: int | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[StudyTask]:
    query = select(StudyTask).where(StudyTask.user_id == user_id)

    if study_plan_id is not None:
        query = query.where(StudyTask.study_plan_id == study_plan_id)

    if status:
        query = query.where(StudyTask.status == status)

    result = await session.execute(
        query.order_by(StudyTask.study_plan_id.desc(), StudyTask.day_number.asc()).limit(limit)
    )

    return list(result.scalars().all())


async def complete_study_task(
    session: AsyncSession,
    user_id: int,
    task_id: int,
) -> bool:
    result = await session.execute(
        select(StudyTask).where(
            StudyTask.id == task_id,
            StudyTask.user_id == user_id,
            StudyTask.status == "pending",
        )
    )

    task = result.scalar_one_or_none()

    if not task:
        return False

    task.status = "completed"
    task.completed_at = datetime.now(timezone.utc)

    await session.flush()

    return True

async def cancel_study_plan(
    session: AsyncSession,
    user_id: int,
    study_plan_id: int,
) -> bool:
    result = await session.execute(
        select(StudyPlan).where(
            StudyPlan.id == study_plan_id,
            StudyPlan.user_id == user_id,
            StudyPlan.status == "active",
        )
    )

    study_plan = result.scalar_one_or_none()

    if not study_plan:
        return False

    study_plan.status = "cancelled"

    tasks_result = await session.execute(
        select(StudyTask).where(
            StudyTask.study_plan_id == study_plan_id,
            StudyTask.user_id == user_id,
            StudyTask.status == "pending",
        )
    )

    pending_tasks = list(tasks_result.scalars().all())

    for task in pending_tasks:
        task.status = "cancelled"
        reminders_result = await session.execute(
        select(Reminder).where(
            Reminder.user_id == user_id,
            Reminder.source == f"study_plan:{study_plan_id}",
            Reminder.status == "pending",
        )
    )

    pending_reminders = list(reminders_result.scalars().all())

    for reminder in pending_reminders:
        reminder.status = "cancelled"

    await session.flush()

    return True

def build_study_reminder_time(
    day_number: int,
    hour: int,
    minute: int,
    timezone_name: str,
) -> datetime:
    timezone_obj = ZoneInfo(timezone_name)
    now = datetime.now(timezone_obj)

    first_reminder_date = now.date()

    first_reminder_time = datetime(
        year=now.year,
        month=now.month,
        day=now.day,
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
        tzinfo=timezone_obj,
    )

    if first_reminder_time <= now:
        first_reminder_date = first_reminder_date + timedelta(days=1)

    reminder_date = first_reminder_date + timedelta(days=day_number - 1)

    return datetime(
        year=reminder_date.year,
        month=reminder_date.month,
        day=reminder_date.day,
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
        tzinfo=timezone_obj,
    )


async def create_study_plan_reminders(
    session: AsyncSession,
    user_id: int,
    study_plan_id: int,
    hour: int,
    minute: int,
    timezone_name: str,
) -> list[Reminder]:
    if hour < 0 or hour > 23:
        raise ValueError("Hour must be between 0 and 23.")

    if minute < 0 or minute > 59:
        raise ValueError("Minute must be between 0 and 59.")

    plan_result = await session.execute(
        select(StudyPlan).where(
            StudyPlan.id == study_plan_id,
            StudyPlan.user_id == user_id,
            StudyPlan.status == "active",
        )
    )

    study_plan = plan_result.scalar_one_or_none()

    if not study_plan:
        return []

    tasks_result = await session.execute(
        select(StudyTask).where(
            StudyTask.study_plan_id == study_plan_id,
            StudyTask.user_id == user_id,
            StudyTask.status == "pending",
        )
        .order_by(StudyTask.day_number.asc())
    )

    pending_tasks = list(tasks_result.scalars().all())

    created_reminders: list[Reminder] = []

    for task in pending_tasks:
        scheduled_time = build_study_reminder_time(
            day_number=task.day_number,
            hour=hour,
            minute=minute,
            timezone_name=timezone_name,
        )

        reminder_message = f"Study Day {task.day_number}: {task.title}"

        reminder = await create_reminder(
            session=session,
            user_id=user_id,
            message=reminder_message,
            scheduled_time=scheduled_time,
            source=f"study_plan:{study_plan_id}",
        )

        created_reminders.append(reminder)

    await session.flush()

    return created_reminders