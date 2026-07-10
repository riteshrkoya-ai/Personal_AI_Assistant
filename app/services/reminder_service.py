from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reminder import Reminder
from app.models.user import User

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

async def list_due_reminders(
    session: AsyncSession,
    now: datetime,
    limit: int = 20,
) -> list[tuple[Reminder, int]]:
    """
    Return pending reminders that are due.

    Returns each reminder with the user's Telegram chat ID so the bot can send it.
    """
    result = await session.execute(
        select(Reminder, User.telegram_chat_id)
        .join(User, User.id == Reminder.user_id)
        .where(
            Reminder.status == "pending",
            Reminder.scheduled_time <= now,
            User.telegram_chat_id.is_not(None),
        )
        .order_by(Reminder.scheduled_time.asc())
        .limit(limit)
    )

    return [(row[0], row[1]) for row in result.all()]


async def mark_reminder_sent(
    session: AsyncSession,
    reminder_id: int,
    sent_at: datetime,
) -> bool:
    result = await session.execute(
        select(Reminder).where(
            Reminder.id == reminder_id,
            Reminder.status == "pending",
        )
    )

    reminder = result.scalar_one_or_none()

    if not reminder:
        return False

    reminder.status = "sent"
    reminder.sent_at = sent_at
    await session.flush()

    return True