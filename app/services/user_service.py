from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_user_by_telegram_chat_id(
    session: AsyncSession,
    telegram_chat_id: int,
) -> User | None:
    result = await session.execute(
        select(User).where(User.telegram_chat_id == telegram_chat_id)
    )
    return result.scalar_one_or_none()


async def get_or_create_telegram_user(
    session: AsyncSession,
    telegram_chat_id: int,
) -> User:
    user = await get_user_by_telegram_chat_id(
        session=session,
        telegram_chat_id=telegram_chat_id,
    )

    if user:
        return user

    user = User(
        telegram_chat_id=telegram_chat_id,
    )

    session.add(user)
    await session.flush()

    return user