from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.personal_memory import PersonalMemory
from app.services.embedding_service import generate_embedding

settings = get_settings()


async def create_memory(
    session: AsyncSession,
    user_id: int,
    content: str,
    source: str = "telegram",
) -> PersonalMemory:
    clean_content = " ".join((content or "").split()).strip()

    if not clean_content:
        raise ValueError("Memory content cannot be empty.")

    embedding = generate_embedding(clean_content)

    memory = PersonalMemory(
        user_id=user_id,
        content=clean_content,
        source=source,
        embedding=embedding,
    )

    session.add(memory)
    await session.flush()

    return memory


async def search_user_memories(
    session: AsyncSession,
    user_id: int,
    query: str,
    top_k: int | None = None,
) -> list[PersonalMemory]:
    clean_query = " ".join((query or "").split()).strip()

    if not clean_query:
        return []

    limit = top_k or settings.memory_search_top_k
    query_embedding = generate_embedding(clean_query)

    result = await session.execute(
        select(PersonalMemory)
        .where(PersonalMemory.user_id == user_id)
        .order_by(PersonalMemory.embedding.cosine_distance(query_embedding))
        .limit(limit)
    )

    return list(result.scalars().all())


async def list_user_memories(
    session: AsyncSession,
    user_id: int,
    limit: int = 20,
) -> list[PersonalMemory]:
    result = await session.execute(
        select(PersonalMemory)
        .where(PersonalMemory.user_id == user_id)
        .order_by(PersonalMemory.created_at.desc())
        .limit(limit)
    )

    return list(result.scalars().all())


async def get_user_memory_by_id(
    session: AsyncSession,
    user_id: int,
    memory_id: int,
) -> PersonalMemory | None:
    result = await session.execute(
        select(PersonalMemory).where(
            PersonalMemory.id == memory_id,
            PersonalMemory.user_id == user_id,
        )
    )

    return result.scalar_one_or_none()


async def delete_user_memory(
    session: AsyncSession,
    user_id: int,
    memory_id: int,
) -> bool:
    """
    Delete one memory only if it belongs to the current user.

    Returns True if deleted, False if no matching memory was found.
    """
    result = await session.execute(
        delete(PersonalMemory)
        .where(
            PersonalMemory.id == memory_id,
            PersonalMemory.user_id == user_id,
        )
        .returning(PersonalMemory.id)
    )

    deleted_id = result.scalar_one_or_none()
    return deleted_id is not None