from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_message import ChatMessage


async def save_chat_message(
    session: AsyncSession,
    user_id: int,
    role: str,
    content: str,
    source: str = "api",
) -> ChatMessage:
    message = ChatMessage(
        user_id=user_id,
        role=role,
        content=content,
        source=source,
    )

    session.add(message)
    await session.flush()

    return message