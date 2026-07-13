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

async def create_study_plan_api(
    chat_id: int,
    topic: str,
    goal: str | None = None,
    days: int = 5,
) -> dict:
    return await post_to_backend(
        "/study/plans",
        {
            "telegram_chat_id": chat_id,
            "topic": topic,
            "goal": goal,
            "days": days,
            "source": "telegram",
        },
    )


async def list_study_plans_api(chat_id: int, limit: int = 20) -> list[dict]:
    data = await post_to_backend(
        "/study/plans/list",
        {
            "telegram_chat_id": chat_id,
            "status": "active",
            "limit": limit,
        },
    )
    return data.get("study_plans", [])


async def list_study_tasks_api(chat_id: int, limit: int = 50) -> list[dict]:
    data = await post_to_backend(
        "/study/tasks/list",
        {
            "telegram_chat_id": chat_id,
            "study_plan_id": None,
            "status": None,
            "limit": limit,
        },
    )
    return data.get("tasks", [])


async def complete_study_task_api(chat_id: int, task_id: int) -> bool:
    data = await post_to_backend(
        "/study/tasks/complete",
        {
            "telegram_chat_id": chat_id,
            "task_id": task_id,
        },
    )
    return bool(data.get("completed"))