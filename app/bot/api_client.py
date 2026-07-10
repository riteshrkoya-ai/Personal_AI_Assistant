import httpx

from app.core.config import get_settings


settings = get_settings()


async def post_to_backend(path: str, payload: dict, timeout: float = 120.0) -> dict:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{settings.api_base_url}{path}",
            json=payload,
        )
        response.raise_for_status()
        return response.json()


async def save_memory_api(chat_id: int, memory_text: str) -> dict:
    return await post_to_backend(
        "/memory",
        {
            "telegram_chat_id": chat_id,
            "content": memory_text,
            "source": "telegram",
        },
    )


async def list_memories_api(chat_id: int, limit: int = 20) -> list[dict]:
    data = await post_to_backend(
        "/memory/list",
        {
            "telegram_chat_id": chat_id,
            "limit": limit,
        },
    )
    return data.get("memories", [])


async def search_memories_api(chat_id: int, query: str, top_k: int = 5) -> list[dict]:
    data = await post_to_backend(
        "/memory/search",
        {
            "telegram_chat_id": chat_id,
            "query": query,
            "top_k": top_k,
        },
    )
    return data.get("memories", [])


async def delete_memory_api(chat_id: int, memory_id: int) -> bool:
    data = await post_to_backend(
        "/memory/delete",
        {
            "telegram_chat_id": chat_id,
            "memory_id": memory_id,
        },
    )
    return bool(data.get("deleted"))


async def create_reminder_api(
    chat_id: int,
    message: str,
    scheduled_time,
) -> dict:
    return await post_to_backend(
        "/reminders",
        {
            "telegram_chat_id": chat_id,
            "message": message,
            "scheduled_time": scheduled_time.isoformat(),
            "source": "telegram",
        },
    )


async def list_reminders_api(chat_id: int, limit: int = 20) -> list[dict]:
    data = await post_to_backend(
        "/reminders/list",
        {
            "telegram_chat_id": chat_id,
            "status": "pending",
            "limit": limit,
        },
    )
    return data.get("reminders", [])


async def cancel_reminder_api(chat_id: int, reminder_id: int) -> bool:
    data = await post_to_backend(
        "/reminders/cancel",
        {
            "telegram_chat_id": chat_id,
            "reminder_id": reminder_id,
        },
    )
    return bool(data.get("cancelled"))