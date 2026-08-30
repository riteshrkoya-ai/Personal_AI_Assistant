from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task


async def create_task(
    session: AsyncSession,
    user_id: int,
    title: str,
    due_date: datetime | None = None,
    source: str = "telegram",
) -> Task:
    clean_title = " ".join((title or "").split()).strip()

    if not clean_title:
        raise ValueError("Task title cannot be empty.")

    if due_date is not None and due_date.tzinfo is None:
        raise ValueError("Task due_date must include timezone information.")

    task = Task(
        user_id=user_id,
        title=clean_title,
        due_date=due_date,
        status="pending",
        source=source,
    )

    session.add(task)
    await session.flush()

    return task


async def list_user_tasks(
    session: AsyncSession,
    user_id: int,
    status: str = "pending",
    limit: int = 20,
) -> list[Task]:
    result = await session.execute(
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.status == status,
        )
        .order_by(Task.due_date.asc().nulls_last(), Task.created_at.asc())
        .limit(limit)
    )

    return list(result.scalars().all())


async def get_user_task_by_id(
    session: AsyncSession,
    user_id: int,
    task_id: int,
) -> Task | None:
    result = await session.execute(
        select(Task).where(
            Task.id == task_id,
            Task.user_id == user_id,
        )
    )

    return result.scalar_one_or_none()


async def complete_user_task(
    session: AsyncSession,
    user_id: int,
    task_id: int,
) -> bool:
    task = await get_user_task_by_id(
        session=session,
        user_id=user_id,
        task_id=task_id,
    )

    if not task:
        return False

    if task.status != "pending":
        return False

    task.status = "completed"
    task.completed_at = datetime.now(timezone.utc)
    await session.flush()

    return True


async def delete_user_task(
    session: AsyncSession,
    user_id: int,
    task_id: int,
) -> bool:
    task = await get_user_task_by_id(
        session=session,
        user_id=user_id,
        task_id=task_id,
    )

    if not task:
        return False

    if task.status != "pending":
        return False

    task.status = "deleted"
    await session.flush()

    return True
