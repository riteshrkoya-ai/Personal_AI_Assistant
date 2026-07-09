from sqlalchemy import select
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