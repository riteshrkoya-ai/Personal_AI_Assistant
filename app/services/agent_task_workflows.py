import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import get_settings


settings = get_settings()


# Lightweight in-process conversation context.
# This intentionally starts simple for Phase 11.
# Later we can persist agent context in PostgreSQL if needed.
_TASK_CONTEXT: dict[int, dict[str, Any]] = {}


_TASK_LIST_PATTERNS = {
    "what tasks do i have",
    "show my tasks",
    "show me my tasks",
    "list my tasks",
    "list tasks",
    "what are my tasks",
    "show my todo list",
    "show my to-do list",
    "show my task list",
}


_COMPLETE_LAST_PATTERNS = {
    "complete that",
    "complete it",
    "complete that task",
    "mark that complete",
    "mark it complete",
    "mark that task complete",
    "finish that",
    "finish it",
    "finish that task",
}


_ORDINAL_INDEX = {
    "first": 0,
    "1st": 0,
    "second": 1,
    "2nd": 1,
    "third": 2,
    "3rd": 2,
    "fourth": 3,
    "4th": 3,
    "fifth": 4,
    "5th": 4,
}


_TEMPORAL_MARKERS = (
    " today",
    " tomorrow",
    " tonight",
    " monday",
    " tuesday",
    " wednesday",
    " thursday",
    " friday",
    " saturday",
    " sunday",
    " due ",
    " by ",
    " at ",
)


def _normalize(value: str) -> str:
    return " ".join(
        (value or "").strip().split()
    )


def _clean_task_title(value: str) -> str:
    title = _normalize(value)

    title = title.strip(
        ' "\''
    )

    return title.rstrip(".").strip()


def _context_for(
    user_id: int,
) -> dict[str, Any]:
    return _TASK_CONTEXT.setdefault(
        user_id,
        {
            "last_task": None,
            "last_task_list": [],
        },
    )


def _complete_task_plan(
    task_id: int,
) -> dict[str, Any]:
    return {
        "response_type": "tool_calls",
        "final_response": "",
        "tool_calls": [
            {
                "tool_name": "complete_task",
                "arguments": {
                    "task_id": task_id,
                },
            }
        ],
    }


def _resolve_last_task_id(
    user_id: int,
) -> int | None:
    context = _context_for(user_id)

    last_task = (
        context.get("last_task")
        or {}
    )

    try:
        return int(
            last_task.get("id")
        )

    except (TypeError, ValueError):
        return None


def _resolve_ordinal_task_id(
    user_id: int,
    ordinal: str,
) -> int | None:
    index = _ORDINAL_INDEX.get(
        ordinal.lower()
    )

    if index is None:
        return None

    tasks = (
        _context_for(user_id)
        .get("last_task_list")
        or []
    )

    if index >= len(tasks):
        return None

    try:
        return int(
            tasks[index].get("id")
        )

    except (TypeError, ValueError):
        return None


def _extract_creation_title(
    message: str,
) -> str | None:
    clean_message = _normalize(
        message
    )

    patterns = (
        r"^add\s+task\s+(.+)$",
        r"^create\s+(?:a\s+)?task\s+(.+)$",
        r"^add\s+(.+?)\s+to\s+my\s+tasks?$",
        r"^add\s+(.+?)\s+to\s+my\s+task\s+list$",
        r"^add\s+(.+?)\s+to\s+my\s+(?:to-do|todo)\s+list$",
    )

    for pattern in patterns:
        match = re.match(
            pattern,
            clean_message,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        title = _clean_task_title(
            match.group(1)
        )

        if not title:
            return None

        lower_title = (
            f" {title.lower()} "
        )

        # Tasks containing due-date language are
        # intentionally left to the LLM planner,
        # which already knows how to populate
        # due_date_iso.
        if any(
            marker in lower_title
            for marker
            in _TEMPORAL_MARKERS
        ):
            return None

        return title

    return None


def build_task_plan(
    message: str,
    user_id: int | None,
) -> dict[str, Any] | None:
    clean_message = _normalize(
        message
    )

    lower_message = (
        clean_message
        .lower()
        .rstrip("?.!")
    )

    if not clean_message:
        return None

    # List tasks.
    if lower_message in _TASK_LIST_PATTERNS:
        return {
            "response_type": "tool_calls",
            "final_response": "",
            "tool_calls": [
                {
                    "tool_name": "list_tasks",
                    "arguments": {
                        "limit": 20,
                    },
                }
            ],
        }

    # Explicit task ID:
    # "complete task 5"
    direct_id_match = re.match(
        r"^(?:complete|finish)\s+task\s+#?(\d+)$",
        lower_message,
    )

    # "mark task 5 complete"
    if not direct_id_match:
        direct_id_match = re.match(
            r"^mark\s+task\s+#?(\d+)\s+"
            r"(?:as\s+)?complete$",
            lower_message,
        )

    if direct_id_match:
        return _complete_task_plan(
            int(
                direct_id_match.group(1)
            )
        )

    # Conversation follow-up:
    # "complete the first one"
    ordinal_match = re.match(
        r"^(?:complete|finish|mark)\s+"
        r"(?:the\s+)?"
        r"(first|1st|second|2nd|third|3rd|"
        r"fourth|4th|fifth|5th)"
        r"(?:\s+one|\s+task)?"
        r"(?:\s+(?:as\s+)?complete)?$",
        lower_message,
    )

    if (
        ordinal_match
        and user_id is not None
    ):
        task_id = (
            _resolve_ordinal_task_id(
                user_id=user_id,
                ordinal=(
                    ordinal_match.group(1)
                ),
            )
        )

        if task_id is None:
            return {
                "response_type": "final",
                "final_response": (
                    "I do not have a recent task list "
                    "to resolve that reference. "
                    "Ask me to list your tasks first."
                ),
                "tool_calls": [],
            }

        return _complete_task_plan(
            task_id
        )

    # Conversation follow-up:
    # "complete that"
    if lower_message in _COMPLETE_LAST_PATTERNS:

        if user_id is None:
            return None

        task_id = (
            _resolve_last_task_id(
                user_id
            )
        )

        if task_id is None:
            return {
                "response_type": "final",
                "final_response": (
                    "I am not sure which task you mean. "
                    "Tell me the task ID or ask me "
                    "to list your tasks."
                ),
                "tool_calls": [],
            }

        return _complete_task_plan(
            task_id
        )

    # Natural task creation.
    title = _extract_creation_title(
        clean_message
    )

    if title:
        return {
            "response_type": "tool_calls",
            "final_response": "",
            "tool_calls": [
                {
                    "tool_name": "create_task",
                    "arguments": {
                        "title": title,
                    },
                }
            ],
        }

    return None


def remember_task_tool_result(
    user_id: int,
    result: dict[str, Any],
) -> None:
    if result.get("success") is not True:
        return

    tool_name = str(
        result.get("tool")
        or ""
    )

    context = _context_for(
        user_id
    )

    if tool_name == "create_task":
        task = (
            result.get("task")
            or {}
        )

        task_id = (
            task.get("id")
            or result.get("task_id")
        )

        title = (
            task.get("title")
            or result.get("title")
        )

        if task_id is not None:
            context["last_task"] = {
                "id": int(task_id),
                "title": title,
                "status": (
                    task.get("status")
                    or "pending"
                ),
            }

        return

    if tool_name == "list_tasks":
        tasks = (
            result.get("tasks")
            or []
        )

        context["last_task_list"] = [
            {
                "id": task.get("id"),
                "title": task.get("title"),
                "status": task.get(
                    "status"
                ),
            }
            for task in tasks
            if task.get("id") is not None
        ]

        return

    if tool_name == "complete_task":
        task_id = result.get(
            "task_id"
        )

        if task_id is None:
            task = (
                result.get("task")
                or {}
            )

            task_id = task.get(
                "id"
            )

        try:
            normalized_task_id = int(
                task_id
            )

        except (TypeError, ValueError):
            return

        last_task = (
            context.get("last_task")
            or {}
        )

        if (
            last_task.get("id")
            == normalized_task_id
        ):
            result["_task_title"] = (
                last_task.get("title")
            )

            last_task["status"] = (
                "completed"
            )

        for task in (
            context.get(
                "last_task_list"
            )
            or []
        ):
            if (
                task.get("id")
                == normalized_task_id
            ):
                result.setdefault(
                    "_task_title",
                    task.get("title"),
                )

                task["status"] = (
                    "completed"
                )

                break


def _format_due_date(
    value: str | None,
) -> str:
    if not value:
        return ""

    try:
        parsed = datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00",
            )
        )

    except ValueError:
        return str(value)

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=ZoneInfo(
                settings.timezone
            )
        )

    local_time = (
        parsed.astimezone(
            ZoneInfo(
                settings.timezone
            )
        )
    )

    return local_time.strftime(
        "%a, %b %d at %I:%M %p"
    ).replace(
        " 0",
        " ",
    )


def format_task_tool_result(
    result: dict[str, Any],
) -> str | None:
    tool_name = str(
        result.get("tool")
        or ""
    )

    if tool_name == "create_task":
        task = (
            result.get("task")
            or {}
        )

        title = (
            task.get("title")
            or result.get("title")
            or "your task"
        )

        due_date = _format_due_date(
            task.get("due_date")
            or result.get("due_date")
        )

        if due_date:
            return (
                f'Done — I added "{title}" '
                f"to your tasks, due {due_date}."
            )

        return (
            f'Done — I added "{title}" '
            "to your tasks."
        )

    if tool_name == "list_tasks":
        tasks = (
            result.get("tasks")
            or []
        )

        if not tasks:
            return (
                "You do not have "
                "any pending tasks."
            )

        lines: list[str] = []

        for index, task in enumerate(
            tasks,
            start=1,
        ):
            title = (
                task.get("title")
                or "Untitled task"
            )

            task_id = task.get(
                "id"
            )

            due_date = (
                _format_due_date(
                    task.get("due_date")
                )
            )

            line = (
                f"{index}. {title}"
            )

            if task_id is not None:
                line += (
                    f" (ID {task_id})"
                )

            if due_date:
                line += (
                    f" — due {due_date}"
                )

            lines.append(line)

        return (
            "Here are your pending tasks:\n"
            + "\n".join(lines)
        )

    if tool_name == "complete_task":
        title = result.get(
            "_task_title"
        )

        task_id = result.get(
            "task_id"
        )

        if title:
            return (
                f'Done — I marked "{title}" '
                "complete."
            )

        if task_id is not None:
            return (
                f"Done — I marked task "
                f"{task_id} complete."
            )

        return (
            "Done — I marked that "
            "task complete."
        )

    return None