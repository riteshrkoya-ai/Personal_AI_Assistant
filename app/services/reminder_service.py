from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reminder import Reminder


async def create_reminder(
    session: AsyncSession,
    user_id: int,
    message: str,
    scheduled_time: datetime,
    source: str = "telegram",
) -> Reminder:
    clean_message = " ".join((message or "").split()).strip()

    if not clean_message:
        raise ValueError("Reminder message cannot be empty.")

    if scheduled_time.tzinfo is None:
        raise ValueError("Reminder scheduled_time must include timezone information.")

    reminder = Reminder(
        user_id=user_id,
        message=clean_message,
        scheduled_time=scheduled_time,
        status="pending",
        source=source,
    )

    session.add(reminder)
    await session.flush()

    return reminder


async def list_user_reminders(
    session: AsyncSession,
    user_id: int,
    status: str = "pending",
    limit: int = 20,
) -> list[Reminder]:
    result = await session.execute(
        select(Reminder)
        .where(
            Reminder.user_id == user_id,
            Reminder.status == status,
        )
        .order_by(Reminder.scheduled_time.asc())
        .limit(limit)
    )

    return list(result.scalars().all())


async def get_user_reminder_by_id(
    session: AsyncSession,
    user_id: int,
    reminder_id: int,
) -> Reminder | None:
    result = await session.execute(
        select(Reminder).where(
            Reminder.id == reminder_id,
            Reminder.user_id == user_id,
        )
    )

    return result.scalar_one_or_none()


async def cancel_user_reminder(
    session: AsyncSession,
    user_id: int,
    reminder_id: int,
) -> bool:
    reminder = await get_user_reminder_by_id(
        session=session,
        user_id=user_id,
        reminder_id=reminder_id,
    )

    if not reminder:
        return False

    if reminder.status != "pending":
        return False

    reminder.status = "cancelled"
    await session.flush()

    return True