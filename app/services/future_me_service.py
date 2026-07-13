from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.future_me import FutureMeGoal, FutureMeTask


def _clean_text(value: str | None) -> str:
    return " ".join((value or "").split()).strip()


def build_future_me_tasks(goal_title: str, days: int = 5) -> list[dict]:
    clean_goal = _clean_text(goal_title)

    base_tasks = [
        {
            "title": f"Clarify your goal: {clean_goal}",
            "description": "Write down what success looks like and why this goal matters.",
        },
        {
            "title": f"Learn one core concept for {clean_goal}",
            "description": "Spend focused time learning one important concept related to your goal.",
        },
        {
            "title": f"Do one practical action for {clean_goal}",
            "description": "Complete a small hands-on task that moves you closer to your goal.",
        },
        {
            "title": f"Practice explaining your progress on {clean_goal}",
            "description": "Summarize what you learned or completed in simple words.",
        },
        {
            "title": f"Review and plan the next step for {clean_goal}",
            "description": "Review progress and decide what to focus on next.",
        },
        {
            "title": f"Improve one weak area for {clean_goal}",
            "description": "Pick one area that feels unclear and spend time improving it.",
        },
        {
            "title": f"Prepare next week's action plan for {clean_goal}",
            "description": "Create a short plan for how you will continue next week.",
        },
    ]

    days = max(1, min(days, 7))

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


async def create_future_me_goal(
    session: AsyncSession,
    user_id: int,
    title: str,
    description: str | None = None,
    target_weeks: int = 4,
    source: str = "telegram",
) -> FutureMeGoal:
    clean_title = _clean_text(title)
    clean_description = _clean_text(description) if description else None

    if not clean_title:
        raise ValueError("Future Me goal title cannot be empty.")

    target_weeks = max(1, min(target_weeks, 52))
    target_date = date.today() + timedelta(weeks=target_weeks)

    goal = FutureMeGoal(
        user_id=user_id,
        title=clean_title,
        description=clean_description,
        target_weeks=target_weeks,
        target_date=target_date,
        status="active",
        source=source,
    )

    session.add(goal)
    await session.flush()

    return goal


async def list_user_future_me_goals(
    session: AsyncSession,
    user_id: int,
    status: str | None = "active",
    limit: int = 20,
) -> list[FutureMeGoal]:
    query = select(FutureMeGoal).where(FutureMeGoal.user_id == user_id)

    if status:
        query = query.where(FutureMeGoal.status == status)

    result = await session.execute(
        query.order_by(FutureMeGoal.created_at.desc()).limit(limit)
    )

    return list(result.scalars().all())


async def cancel_future_me_goal(
    session: AsyncSession,
    user_id: int,
    goal_id: int,
) -> bool:
    result = await session.execute(
        select(FutureMeGoal).where(
            FutureMeGoal.id == goal_id,
            FutureMeGoal.user_id == user_id,
            FutureMeGoal.status == "active",
        )
    )

    goal = result.scalar_one_or_none()

    if not goal:
        return False

    goal.status = "cancelled"

    tasks_result = await session.execute(
        select(FutureMeTask).where(
            FutureMeTask.goal_id == goal_id,
            FutureMeTask.user_id == user_id,
            FutureMeTask.status == "pending",
        )
    )

    pending_tasks = list(tasks_result.scalars().all())

    for task in pending_tasks:
        task.status = "cancelled"

    await session.flush()

    return True


async def create_future_me_weekly_plan(
    session: AsyncSession,
    user_id: int,
    goal_id: int,
    days: int = 5,
) -> list[FutureMeTask]:
    goal_result = await session.execute(
        select(FutureMeGoal).where(
            FutureMeGoal.id == goal_id,
            FutureMeGoal.user_id == user_id,
            FutureMeGoal.status == "active",
        )
    )

    goal = goal_result.scalar_one_or_none()

    if not goal:
        return []

    existing_tasks_result = await session.execute(
        select(FutureMeTask).where(
            FutureMeTask.goal_id == goal_id,
            FutureMeTask.user_id == user_id,
            FutureMeTask.status == "pending",
        )
        .order_by(FutureMeTask.day_number.asc())
    )

    existing_tasks = list(existing_tasks_result.scalars().all())

    if existing_tasks:
        return existing_tasks

    days = max(1, min(days, 7))
    today = date.today()
    task_payloads = build_future_me_tasks(goal_title=goal.title, days=days)

    created_tasks: list[FutureMeTask] = []

    for payload in task_payloads:
        task = FutureMeTask(
            user_id=user_id,
            goal_id=goal.id,
            day_number=payload["day_number"],
            title=payload["title"],
            description=payload["description"],
            status="pending",
            due_date=today + timedelta(days=payload["day_number"] - 1),
        )
        session.add(task)
        created_tasks.append(task)

    await session.flush()

    return created_tasks


async def list_user_future_me_tasks(
    session: AsyncSession,
    user_id: int,
    goal_id: int | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[FutureMeTask]:
    query = select(FutureMeTask).where(FutureMeTask.user_id == user_id)

    if goal_id is not None:
        query = query.where(FutureMeTask.goal_id == goal_id)

    if status:
        query = query.where(FutureMeTask.status == status)

    result = await session.execute(
        query.order_by(
            FutureMeTask.goal_id.desc(),
            FutureMeTask.day_number.asc(),
        ).limit(limit)
    )

    return list(result.scalars().all())


async def complete_future_me_task(
    session: AsyncSession,
    user_id: int,
    task_id: int,
) -> bool:
    result = await session.execute(
        select(FutureMeTask).where(
            FutureMeTask.id == task_id,
            FutureMeTask.user_id == user_id,
            FutureMeTask.status == "pending",
        )
    )

    task = result.scalar_one_or_none()

    if not task:
        return False

    task.status = "completed"
    task.completed_at = datetime.now(timezone.utc)

    await session.flush()

    return True