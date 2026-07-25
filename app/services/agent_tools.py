from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.daily_summary_service import build_daily_summary
from app.services.future_me_service import (
    create_future_me_goal,
    create_future_me_weekly_plan,
)
from app.services.memory_service import create_memory, search_user_memories
from app.services.reminder_service import create_reminder, list_user_reminders
from app.services.study_service import create_study_plan

settings = get_settings()


AGENT_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save an important personal memory for the current authenticated user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The memory text to save.",
                    },
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": "Search the current user's saved memories using semantic search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Maximum number of memories to return.",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_reminder",
            "description": "Create a reminder for the current authenticated user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Reminder message.",
                    },
                    "scheduled_time_iso": {
                        "type": "string",
                        "description": (
                            "Reminder time in ISO format. "
                            "Example: 2026-07-26T20:00:00-04:00"
                        ),
                    },
                },
                "required": ["message", "scheduled_time_iso"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_reminders",
            "description": "List pending reminders for the current authenticated user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of reminders to return.",
                        "default": 20,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_daily_summary",
            "description": "Get today's summary for the current authenticated user.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_study_plan",
            "description": "Create a study plan and study tasks for the current authenticated user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "The topic to study.",
                    },
                    "goal": {
                        "type": "string",
                        "description": "Optional study goal.",
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of study days, between 1 and 14.",
                        "default": 5,
                    },
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_future_me_goal",
            "description": "Create a Future Me goal for the current authenticated user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Goal title.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional reason or description for the goal.",
                    },
                    "target_weeks": {
                        "type": "integer",
                        "description": "Target duration in weeks.",
                        "default": 4,
                    },
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_future_me_weekly_plan",
            "description": "Create weekly tasks for an existing Future Me goal.",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal_id": {
                        "type": "integer",
                        "description": "Future Me goal ID.",
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of task days, between 1 and 7.",
                        "default": 5,
                    },
                },
                "required": ["goal_id"],
            },
        },
    },
]


def get_agent_tool_names() -> list[str]:
    return [
        tool["function"]["name"]
        for tool in AGENT_TOOL_SCHEMAS
    ]


def parse_agent_datetime(value: str) -> datetime:
    clean_value = " ".join((value or "").split()).strip()

    if not clean_value:
        raise ValueError("scheduled_time_iso cannot be empty.")

    normalized = clean_value.replace("Z", "+00:00")

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(
            "scheduled_time_iso must be a valid ISO datetime. "
            "Example: 2026-07-26T20:00:00-04:00"
        ) from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(settings.timezone))

    now = datetime.now(parsed.tzinfo)

    if parsed <= now:
        raise ValueError("Reminder time must be in the future.")

    return parsed


async def execute_agent_tool(
    session: AsyncSession,
    user_id: int,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    args = arguments or {}

    if tool_name == "save_memory":
        content = str(args.get("content", "")).strip()

        memory = await create_memory(
            session=session,
            user_id=user_id,
            content=content,
            source="agent",
        )

        return {
            "tool": tool_name,
            "success": True,
            "memory": {
                "id": memory.id,
                "content": memory.content,
                "source": memory.source,
            },
        }

    if tool_name == "search_memory":
        query = str(args.get("query", "")).strip()
        top_k = int(args.get("top_k", 5))

        memories = await search_user_memories(
            session=session,
            user_id=user_id,
            query=query,
            top_k=top_k,
        )

        return {
            "tool": tool_name,
            "success": True,
            "memories": [
                {
                    "id": memory.id,
                    "content": memory.content,
                    "source": memory.source,
                    "created_at": memory.created_at.isoformat(),
                }
                for memory in memories
            ],
        }

    if tool_name == "create_reminder":
        message = str(args.get("message", "")).strip()
        scheduled_time_iso = str(args.get("scheduled_time_iso", "")).strip()
        scheduled_time = parse_agent_datetime(scheduled_time_iso)

        reminder = await create_reminder(
            session=session,
            user_id=user_id,
            message=message,
            scheduled_time=scheduled_time,
            source="agent",
        )

        return {
            "tool": tool_name,
            "success": True,
            "reminder": {
                "id": reminder.id,
                "message": reminder.message,
                "scheduled_time": reminder.scheduled_time.isoformat(),
                "status": reminder.status,
                "source": reminder.source,
            },
        }

    if tool_name == "list_reminders":
        limit = int(args.get("limit", 20))

        reminders = await list_user_reminders(
            session=session,
            user_id=user_id,
            status="pending",
            limit=limit,
        )

        return {
            "tool": tool_name,
            "success": True,
            "reminders": [
                {
                    "id": reminder.id,
                    "message": reminder.message,
                    "scheduled_time": reminder.scheduled_time.isoformat(),
                    "status": reminder.status,
                    "source": reminder.source,
                }
                for reminder in reminders
            ],
        }

    if tool_name == "get_daily_summary":
        summary = await build_daily_summary(
            session=session,
            user_id=user_id,
            timezone_name=settings.timezone,
        )

        return {
            "tool": tool_name,
            "success": True,
            "summary_text": summary["summary_text"],
            "counts": summary["counts"],
        }

    if tool_name == "create_study_plan":
        topic = str(args.get("topic", "")).strip()
        goal_value = args.get("goal")
        goal = str(goal_value).strip() if goal_value else None
        days = int(args.get("days", 5))

        study_plan, tasks = await create_study_plan(
            session=session,
            user_id=user_id,
            topic=topic,
            goal=goal,
            days=days,
            source="agent",
        )

        return {
            "tool": tool_name,
            "success": True,
            "study_plan": {
                "id": study_plan.id,
                "topic": study_plan.topic,
                "goal": study_plan.goal,
                "status": study_plan.status,
                "source": study_plan.source,
            },
            "tasks": [
                {
                    "id": task.id,
                    "day_number": task.day_number,
                    "title": task.title,
                    "description": task.description,
                    "status": task.status,
                }
                for task in tasks
            ],
        }

    if tool_name == "create_future_me_goal":
        title = str(args.get("title", "")).strip()
        description_value = args.get("description")
        description = str(description_value).strip() if description_value else None
        target_weeks = int(args.get("target_weeks", 4))

        goal = await create_future_me_goal(
            session=session,
            user_id=user_id,
            title=title,
            description=description,
            target_weeks=target_weeks,
            source="agent",
        )

        return {
            "tool": tool_name,
            "success": True,
            "goal": {
                "id": goal.id,
                "title": goal.title,
                "description": goal.description,
                "target_weeks": goal.target_weeks,
                "target_date": goal.target_date.isoformat() if goal.target_date else None,
                "status": goal.status,
                "source": goal.source,
            },
        }

    if tool_name == "create_future_me_weekly_plan":
        goal_id = int(args.get("goal_id"))
        days = int(args.get("days", 5))

        tasks = await create_future_me_weekly_plan(
            session=session,
            user_id=user_id,
            goal_id=goal_id,
            days=days,
        )

        return {
            "tool": tool_name,
            "success": True,
            "goal_id": goal_id,
            "tasks": [
                {
                    "id": task.id,
                    "day_number": task.day_number,
                    "title": task.title,
                    "description": task.description,
                    "status": task.status,
                    "due_date": task.due_date.isoformat() if task.due_date else None,
                }
                for task in tasks
            ],
        }

    raise ValueError(f"Unknown agent tool: {tool_name}")