from datetime import datetime, timezone

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