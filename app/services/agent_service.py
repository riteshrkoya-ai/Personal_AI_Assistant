import json
import logging
import re
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from litellm import acompletion
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.agent_tools import AGENT_TOOL_SCHEMAS, execute_agent_tool

logger = logging.getLogger(__name__)
settings = get_settings()

PENDING_REMINDER_REQUESTS: dict[int, dict[str, Any]] = {}


def _message_content(response: Any) -> str:
    message = response.choices[0].message

    if isinstance(message, dict):
        return str(message.get("content") or "")

    return str(getattr(message, "content", "") or "")


def _extract_json_object(text: str) -> dict[str, Any]:
    clean_text = text.strip()

    if clean_text.startswith("```"):
        clean_text = clean_text.strip("`").strip()

        if clean_text.lower().startswith("json"):
            clean_text = clean_text[4:].strip()

    try:
        return json.loads(clean_text)
    except json.JSONDecodeError:
        pass

    start = clean_text.find("{")
    end = clean_text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError("Model did not return a JSON object.")

    return json.loads(clean_text[start : end + 1])


def _format_tool_catalog() -> str:
    tool_lines: list[str] = []

    for tool in AGENT_TOOL_SCHEMAS:
        function = tool["function"]
        tool_lines.append(
            json.dumps(
                {
                    "name": function["name"],
                    "description": function["description"],
                    "parameters": function["parameters"],
                },
                indent=2,
            )
        )

    return "\n\n".join(tool_lines)


def _technical_assistant_prompt() -> str:
    return (
        "You are a helpful AI personal assistant for a software engineering project. "
        "Answer clearly, accurately, concisely, and practically. "
        "The user may ask about Python, FastAPI, Docker, PostgreSQL, APIs, system design, "
        "AI, ML, LLMs, RAG, vector databases, and software architecture. "
        "When the user asks about RAG in an AI, ML, LLM, or software context, "
        "RAG means Retrieval-Augmented Generation. "
        "If an acronym has multiple meanings, choose the meaning that best fits the user's context. "
        "If the context is unclear, briefly state the most likely meaning and ask one short clarifying question. "
        "Do not invent technical definitions, facts, implementation details, or user-specific information. "
        "If you are unsure, say you are unsure. "
        "Prefer direct answers over long explanations. "
        "Keep responses readable and not too long."
    )


def _build_planner_prompt() -> str:
    now = datetime.now(ZoneInfo(settings.timezone))

    return f"""
You are an AI personal assistant agent planner.

Your job is to decide whether the user's message needs a tool call.

Current datetime:
{now.isoformat()}

Timezone:
{settings.timezone}

Available tools:
{_format_tool_catalog()}

Important rules:
- Return ONLY valid JSON.
- Do not include markdown.
- Do not include explanations outside JSON.
- Never invent that an action was completed.
- If saving a memory, use save_memory.
- If the user says remember, save, note, or keep in mind something personal, use save_memory.
- If searching saved information, use search_memory.
- If the user asks what you remember, what do you know about me, or anything from memory, use search_memory.
- If creating a reminder, use create_reminder.
- If listing reminders, use list_reminders.
- If the user asks what they should focus on today, use get_daily_summary.
- If the user asks to create a study plan, use create_study_plan.
- If the user asks to create a future goal, use create_future_me_goal.
- If the user asks to create a Future Me weekly plan, use create_future_me_weekly_plan.
- If a reminder request is missing a clear future date or time, do not call a tool. Ask one short clarification question.
- For create_reminder, scheduled_time_iso must be a future ISO datetime with timezone.
- The server injects user_id. Never ask for or generate user_id.

Return JSON in exactly one of these formats.

For normal answer without tools:
{{
  "response_type": "final",
  "final_response": "",
  "tool_calls": []
}}

For tool usage:
{{
  "response_type": "tool_calls",
  "final_response": "",
  "tool_calls": [
    {{
      "tool_name": "save_memory",
      "arguments": {{
        "content": "memory text"
      }}
    }}
  ]
}}

You may return multiple tool calls only when the user's message clearly asks for multiple actions.
Keep arguments minimal and accurate.
""".strip()


async def _call_llm(
    messages: list[dict[str, str]],
    temperature: float = 0.1,
    max_tokens: int = 512,
) -> str:
    response = await acompletion(
        model=f"ollama/{settings.ollama_model}",
        api_base=settings.ollama_base_url,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    return _message_content(response)


def _extract_memory_content(message: str) -> str:
    patterns = [
        r"^remember that\s+",
        r"^remember\s+",
        r"^save that\s+",
        r"^save this\s+",
        r"^note that\s+",
        r"^keep in mind that\s+",
        r"^keep in mind\s+",
    ]

    content = message.strip()

    for pattern in patterns:
        content = re.sub(pattern, "", content, flags=re.IGNORECASE).strip()

    return content.rstrip(".")


def _extract_memory_query(message: str) -> str:
    clean_message = message.strip().rstrip("?")

    replacements = [
        "what do you remember about",
        "what do you know about",
        "what have i told you about",
        "search memory for",
        "search memory",
        "find memory about",
        "find memory",
    ]

    query = clean_message

    for replacement in replacements:
        query = re.sub(
            f"^{re.escape(replacement)}",
            "",
            query,
            flags=re.IGNORECASE,
        ).strip()

    return query or clean_message


def _format_datetime_for_user(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo(settings.timezone))

        local_time = parsed.astimezone(ZoneInfo(settings.timezone))

        hour = local_time.strftime("%I").lstrip("0") or "12"
        minute = local_time.strftime("%M")
        am_pm = local_time.strftime("%p")

        return (
            f"{local_time.strftime('%b')} "
            f"{local_time.day}, "
            f"{local_time.year} "
            f"at {hour}:{minute} {am_pm}"
        )

    except Exception:
        return value


def _extract_date_from_text(
    message: str,
    now: datetime,
) -> tuple[Any | None, bool]:
    lower_message = message.lower()

    if "tomorrow" in lower_message:
        return (now + timedelta(days=1)).date(), True

    if "today" in lower_message:
        return now.date(), True

    date_match = re.search(
        r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b",
        lower_message,
    )

    if not date_match:
        return None, False

    month = int(date_match.group(1))
    day = int(date_match.group(2))
    year_text = date_match.group(3)

    if year_text:
        year = int(year_text)
        if year < 100:
            year += 2000
    else:
        year = now.year

    try:
        parsed_date = datetime(year, month, day).date()
    except ValueError:
        return None, False

    return parsed_date, True


def _extract_time_from_text(
    message: str,
    default_meridiem: str | None = None,
) -> tuple[int | None, int | None, str | None, str | None]:
    lower_message = message.lower()

    time_match = re.search(
        r"\b(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
        lower_message,
    )

    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
        meridiem = time_match.group(3)

        if hour < 1 or hour > 12 or minute < 0 or minute > 59:
            return None, None, None, "Please provide a valid reminder time."

        if meridiem == "pm" and hour != 12:
            hour += 12

        if meridiem == "am" and hour == 12:
            hour = 0

        return hour, minute, meridiem, None

    no_meridiem_match = re.search(
        r"\b(?:at\s+)?(\d{1,2}):(\d{2})\b",
        lower_message,
    )

    if not no_meridiem_match:
        return None, None, None, "What time should I set the reminder for?"

    hour = int(no_meridiem_match.group(1))
    minute = int(no_meridiem_match.group(2))

    if minute < 0 or minute > 59:
        return None, None, None, "Please provide a valid reminder time."

    if hour > 12:
        if hour > 23:
            return None, None, None, "Please provide a valid reminder time."

        return hour, minute, None, None

    if default_meridiem:
        meridiem = default_meridiem

        if meridiem == "pm" and hour != 12:
            hour += 12

        if meridiem == "am" and hour == 12:
            hour = 0

        return hour, minute, meridiem, None

    return None, None, None, "Is that AM or PM?"


def _build_scheduled_time_from_text(
    message: str,
    default_meridiem: str | None = None,
) -> tuple[datetime | None, str | None, str | None]:
    timezone = ZoneInfo(settings.timezone)
    now = datetime.now(timezone)

    scheduled_date, date_was_explicit = _extract_date_from_text(
        message=message,
        now=now,
    )

    hour, minute, meridiem, time_error = _extract_time_from_text(
        message=message,
        default_meridiem=default_meridiem,
    )

    if time_error:
        return None, time_error, meridiem

    if hour is None or minute is None:
        return None, "What time should I set the reminder for?", meridiem

    if scheduled_date is None:
        scheduled_time = datetime.combine(
            now.date(),
            time(hour=hour, minute=minute),
            tzinfo=timezone,
        )

        if scheduled_time <= now:
            scheduled_time = scheduled_time + timedelta(days=1)

        return scheduled_time, None, meridiem

    scheduled_time = datetime.combine(
        scheduled_date,
        time(hour=hour, minute=minute),
        tzinfo=timezone,
    )

    if scheduled_time <= now:
        if date_was_explicit:
            return (
                None,
                "That reminder time has already passed. What future time should I use?",
                meridiem,
            )

        scheduled_time = scheduled_time + timedelta(days=1)

    return scheduled_time, None, meridiem


def _extract_reminder_message(message: str) -> str:
    message_part = " ".join(message.split()).strip()

    message_part = re.sub(
        r"(?i)^remind me\s+",
        "",
        message_part,
    ).strip()

    message_part = re.sub(
        r"(?i)\b(today|tomorrow)\b",
        "",
        message_part,
    ).strip()

    message_part = re.sub(
        r"(?i)\b(on\s+)?\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?\b",
        "",
        message_part,
    ).strip()

    message_part = re.sub(
        r"(?i)\bat\s+\d{1,2}(:\d{2})?\s*(am|pm)?\b",
        "",
        message_part,
    ).strip()

    message_part = re.sub(
        r"(?i)\b\d{1,2}(:\d{2})?\s*(am|pm)\b",
        "",
        message_part,
    ).strip()

    message_part = re.sub(
        r"(?i)^to\s+",
        "",
        message_part,
    ).strip()

    message_part = re.sub(
        r"(?i)\b(and|on|at)\b$",
        "",
        message_part,
    ).strip()

    return message_part.strip(" .")


def _contains_date_or_time(message: str) -> bool:
    lower_message = message.lower()

    has_date_word = "today" in lower_message or "tomorrow" in lower_message
    has_date_number = re.search(
        r"\b\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?\b",
        lower_message,
    )
    has_time = re.search(
        r"\b(?:at\s+)?\d{1,2}(:\d{2})?\s*(am|pm)\b",
        lower_message,
    ) or re.search(
        r"\b(?:at\s+)?\d{1,2}:\d{2}\b",
        lower_message,
    )

    return bool(has_date_word or has_date_number or has_time)


def _looks_like_standalone_datetime(message: str) -> bool:
    lower_message = " ".join(message.lower().split()).strip()

    if not _contains_date_or_time(lower_message):
        return False

    if "remind" in lower_message or "remember" in lower_message:
        return False

    remaining = lower_message

    remaining = re.sub(
        r"\b(today|tomorrow)\b",
        " ",
        remaining,
    )

    remaining = re.sub(
        r"\b(on\s+)?\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?\b",
        " ",
        remaining,
    )

    remaining = re.sub(
        r"\bat\s+\d{1,2}(:\d{2})?\s*(am|pm)?\b",
        " ",
        remaining,
    )

    remaining = re.sub(
        r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b",
        " ",
        remaining,
    )

    remaining = re.sub(
        r"\b\d{1,2}:\d{2}\b",
        " ",
        remaining,
    )

    remaining = re.sub(
        r"\b(and|at|on|for)\b",
        " ",
        remaining,
    )

    remaining = re.sub(r"[^a-z0-9]+", " ", remaining).strip()

    return remaining == ""


def _build_pending_reminder_plan(
    user_id: int,
    message: str,
) -> dict[str, Any] | None:
    pending_reminder = PENDING_REMINDER_REQUESTS.get(user_id)

    if not pending_reminder:
        return None

    clean_message = " ".join(message.split()).strip()
    lower_message = clean_message.lower()

    if lower_message in {"cancel", "cancel reminder", "never mind", "nevermind"}:
        PENDING_REMINDER_REQUESTS.pop(user_id, None)

        return {
            "response_type": "final",
            "final_response": "Okay, I cancelled that pending reminder request.",
            "tool_calls": [],
        }

    if not _contains_date_or_time(clean_message):
        return None

    scheduled_time, question, meridiem = _build_scheduled_time_from_text(
        message=clean_message,
        default_meridiem=pending_reminder.get("meridiem"),
    )

    if scheduled_time is None:
        if meridiem:
            pending_reminder["meridiem"] = meridiem

        return {
            "response_type": "final",
            "final_response": question or "What date and time should I set the reminder for?",
            "tool_calls": [],
        }

    reminder_message = str(pending_reminder.get("message") or "").strip()

    if not reminder_message:
        PENDING_REMINDER_REQUESTS.pop(user_id, None)

        return {
            "response_type": "final",
            "final_response": "What should I remind you about?",
            "tool_calls": [],
        }

    PENDING_REMINDER_REQUESTS.pop(user_id, None)

    return {
        "response_type": "tool_calls",
        "final_response": "",
        "tool_calls": [
            {
                "tool_name": "create_reminder",
                "arguments": {
                    "message": reminder_message,
                    "scheduled_time_iso": scheduled_time.isoformat(),
                },
            }
        ],
    }


def _parse_simple_reminder(
    message: str,
    user_id: int | None = None,
) -> dict[str, Any] | None:
    clean_message = " ".join(message.split()).strip()
    lower_message = clean_message.lower()

    if "remind me" not in lower_message:
        return None

    reminder_message = _extract_reminder_message(clean_message)

    scheduled_time, question, meridiem = _build_scheduled_time_from_text(
        message=clean_message,
    )

    if not reminder_message and scheduled_time is not None:
        return {
            "response_type": "final",
            "final_response": "What should I remind you about?",
            "tool_calls": [],
        }

    if scheduled_time is None:
        if user_id is not None and reminder_message:
            PENDING_REMINDER_REQUESTS[user_id] = {
                "message": reminder_message,
                "created_at": datetime.now(ZoneInfo(settings.timezone)).isoformat(),
                "meridiem": meridiem,
            }

        return {
            "response_type": "final",
            "final_response": question or "What date and time should I set the reminder for?",
            "tool_calls": [],
        }

    return {
        "response_type": "tool_calls",
        "final_response": "",
        "tool_calls": [
            {
                "tool_name": "create_reminder",
                "arguments": {
                    "message": reminder_message,
                    "scheduled_time_iso": scheduled_time.isoformat(),
                },
            }
        ],
    }


def _extract_number_before_word(
    message: str,
    word_patterns: tuple[str, ...],
    default_value: int,
    minimum: int,
    maximum: int,
) -> int:
    lower_message = message.lower()

    for word_pattern in word_patterns:
        match = re.search(
            rf"\b(\d+)\s*{word_pattern}\b",
            lower_message,
        )

        if match:
            value = int(match.group(1))
            return max(minimum, min(value, maximum))

    return default_value


def _clean_study_topic(topic: str) -> str:
    clean_topic = " ".join(topic.split()).strip(" .")

    clean_topic = re.sub(
        r"(?i)\bfor\s+\d+\s*(days?|weeks?)\b",
        "",
        clean_topic,
    ).strip(" .")

    clean_topic = re.sub(
        r"(?i)\bover\s+\d+\s*(days?|weeks?)\b",
        "",
        clean_topic,
    ).strip(" .")

    return clean_topic


def _extract_study_plan_details(message: str) -> tuple[str, str | None, int]:
    clean_message = " ".join(message.split()).strip()

    days = _extract_number_before_word(
        message=clean_message,
        word_patterns=("days?",),
        default_value=5,
        minimum=1,
        maximum=14,
    )

    topic = clean_message

    patterns = [
        r"(?i)^create\s+(a\s+)?study\s+plan\s+for\s+",
        r"(?i)^make\s+(a\s+)?study\s+plan\s+for\s+",
        r"(?i)^build\s+(a\s+)?study\s+plan\s+for\s+",
        r"(?i)^generate\s+(a\s+)?study\s+plan\s+for\s+",
        r"(?i)^help\s+me\s+study\s+",
        r"(?i)^i\s+want\s+to\s+study\s+",
    ]

    for pattern in patterns:
        updated_topic = re.sub(pattern, "", topic).strip()

        if updated_topic != topic:
            topic = updated_topic
            break

    topic = _clean_study_topic(topic)

    goal = None
    if topic:
        goal = f"Build practical understanding of {topic}"

    return topic, goal, days


def _extract_future_goal_details(message: str) -> tuple[str, str | None, int]:
    clean_message = " ".join(message.split()).strip()

    target_weeks = _extract_number_before_word(
        message=clean_message,
        word_patterns=("weeks?",),
        default_value=4,
        minimum=1,
        maximum=52,
    )

    title = clean_message

    patterns = [
        r"(?i)^create\s+(a\s+)?future\s+me\s+goal\s+to\s+",
        r"(?i)^create\s+(a\s+)?future\s+goal\s+to\s+",
        r"(?i)^add\s+(a\s+)?future\s+me\s+goal\s+to\s+",
        r"(?i)^add\s+(a\s+)?future\s+goal\s+to\s+",
        r"(?i)^my\s+future\s+me\s+goal\s+is\s+to\s+",
        r"(?i)^i\s+want\s+to\s+become\s+",
        r"(?i)^i\s+want\s+to\s+improve\s+",
    ]

    matched_pattern = ""

    for pattern in patterns:
        updated_title = re.sub(pattern, "", title).strip()

        if updated_title != title:
            title = updated_title
            matched_pattern = pattern
            break

    title = re.sub(
        r"(?i)\b(in|over|for)\s+\d+\s*weeks?\b",
        "",
        title,
    ).strip(" .")

    if title:
        if "become" in matched_pattern.lower():
            title = f"Become {title}"
        elif "improve" in matched_pattern.lower():
            title = f"Improve {title}"

    description = None
    if title:
        description = f"Future Me goal created from natural language request: {clean_message}"

    return title, description, target_weeks


def _extract_future_weekly_plan_details(message: str) -> tuple[int | None, int]:
    clean_message = " ".join(message.split()).strip()

    days = _extract_number_before_word(
        message=clean_message,
        word_patterns=("days?",),
        default_value=5,
        minimum=1,
        maximum=7,
    )

    goal_match = re.search(
        r"(?i)\bgoal\s*(id\s*)?#?\s*(\d+)\b",
        clean_message,
    )

    if not goal_match:
        return None, days

    goal_id = int(goal_match.group(2))
    return goal_id, days


def _deterministic_plan(
    message: str,
    user_id: int | None = None,
) -> dict[str, Any] | None:
    clean_message = " ".join((message or "").split()).strip()
    lower_message = clean_message.lower()

    if user_id is not None:
        pending_reminder_plan = _build_pending_reminder_plan(
            user_id=user_id,
            message=clean_message,
        )

        if pending_reminder_plan is not None:
            return pending_reminder_plan

    if lower_message in {
        "what is rag?",
        "what is rag",
        "why do we use rag?",
        "why do we use rag",
    }:
        return {
            "response_type": "final",
            "final_response": (
                "RAG means Retrieval-Augmented Generation. "
                "It helps an LLM answer using retrieved external or user-specific context "
                "instead of relying only on the model's built-in knowledge."
            ),
            "tool_calls": [],
        }

    if lower_message.startswith(
        (
            "remember ",
            "remember that ",
            "save that ",
            "save this ",
            "note that ",
            "keep in mind ",
            "keep in mind that ",
        )
    ):
        content = _extract_memory_content(clean_message)

        if not content:
            return {
                "response_type": "final",
                "final_response": "What would you like me to remember?",
                "tool_calls": [],
            }

        return {
            "response_type": "tool_calls",
            "final_response": "",
            "tool_calls": [
                {
                    "tool_name": "save_memory",
                    "arguments": {
                        "content": content,
                    },
                }
            ],
        }

    if lower_message.startswith(
        (
            "what do you remember",
            "what do you know about",
            "what have i told you about",
            "search memory",
            "find memory",
        )
    ):
        query = _extract_memory_query(clean_message)

        return {
            "response_type": "tool_calls",
            "final_response": "",
            "tool_calls": [
                {
                    "tool_name": "search_memory",
                    "arguments": {
                        "query": query,
                        "top_k": 5,
                    },
                }
            ],
        }

    if (
        "study plan" in lower_message
        or lower_message.startswith("help me study ")
        or lower_message.startswith("i want to study ")
    ):
        topic, goal, days = _extract_study_plan_details(clean_message)

        if not topic:
            return {
                "response_type": "final",
                "final_response": "What topic should I create a study plan for?",
                "tool_calls": [],
            }

        return {
            "response_type": "tool_calls",
            "final_response": "",
            "tool_calls": [
                {
                    "tool_name": "create_study_plan",
                    "arguments": {
                        "topic": topic,
                        "goal": goal,
                        "days": days,
                    },
                }
            ],
        }

    if (
        "future me goal" in lower_message
        or "future goal" in lower_message
        or lower_message.startswith("my future me goal is")
        or lower_message.startswith("i want to become ")
        or lower_message.startswith("i want to improve ")
    ):
        title, description, target_weeks = _extract_future_goal_details(clean_message)

        if not title:
            return {
                "response_type": "final",
                "final_response": "What Future Me goal would you like to create?",
                "tool_calls": [],
            }

        return {
            "response_type": "tool_calls",
            "final_response": "",
            "tool_calls": [
                {
                    "tool_name": "create_future_me_goal",
                    "arguments": {
                        "title": title,
                        "description": description,
                        "target_weeks": target_weeks,
                    },
                }
            ],
        }

    if (
        "weekly plan" in lower_message
        and ("future me" in lower_message or "goal" in lower_message)
    ):
        goal_id, days = _extract_future_weekly_plan_details(clean_message)

        if goal_id is None:
            return {
                "response_type": "final",
                "final_response": (
                    "Please provide the Future Me goal ID. "
                    "For example: create a weekly plan for goal 1."
                ),
                "tool_calls": [],
            }

        return {
            "response_type": "tool_calls",
            "final_response": "",
            "tool_calls": [
                {
                    "tool_name": "create_future_me_weekly_plan",
                    "arguments": {
                        "goal_id": goal_id,
                        "days": days,
                    },
                }
            ],
        }

    reminder_plan = _parse_simple_reminder(
        message=clean_message,
        user_id=user_id,
    )

    if reminder_plan is not None:
        return reminder_plan

    if _looks_like_standalone_datetime(clean_message):
        return {
            "response_type": "final",
            "final_response": "What should I remind you about?",
            "tool_calls": [],
        }

    return None


def _format_tool_results(tool_results: list[dict[str, Any]]) -> str:
    if not tool_results:
        return "I could not complete that action."

    failed_tools = [
        result
        for result in tool_results
        if result.get("success") is not True
    ]

    if failed_tools:
        error = failed_tools[0].get("error", "Unknown error")
        return f"I could not complete that action. {error}"

    first_result = tool_results[0]
    tool_name = first_result.get("tool")

    if tool_name == "save_memory":
        memory = first_result.get("memory", {})
        content = memory.get("content", "that")
        duplicate = first_result.get("duplicate") is True

        if duplicate:
            return f"I already had this memory saved: {content}"

        return f"Got it — I saved this memory: {content}"

    if tool_name == "search_memory":
        memories = first_result.get("memories", [])

        if not memories:
            return "I did not find any matching memories."

        seen_contents: set[str] = set()
        memory_lines: list[str] = []

        for memory in memories:
            content = memory.get("content")

            if not content:
                continue

            normalized_content = " ".join(content.lower().strip().rstrip(".").split())

            if normalized_content in seen_contents:
                continue

            seen_contents.add(normalized_content)
            memory_lines.append(f"- {content}")

        if not memory_lines:
            return "I did not find any matching memories."

        return "Here is what I found in your memory:\n" + "\n".join(memory_lines)

    if tool_name == "create_reminder":
        reminder = first_result.get("reminder", {})
        message = reminder.get("message", "your reminder")
        scheduled_time = reminder.get("scheduled_time", "")
        readable_time = _format_datetime_for_user(scheduled_time)

        return f"Done — I created the reminder: {message} for {readable_time}."

    if tool_name == "list_reminders":
        reminders = first_result.get("reminders", [])

        if not reminders:
            return "You do not have any pending reminders."

        reminder_lines = [
            (
                f"- {_format_datetime_for_user(reminder.get('scheduled_time', ''))}: "
                f"{reminder.get('message')}"
            )
            for reminder in reminders
        ]

        return "Here are your pending reminders:\n" + "\n".join(reminder_lines)

    if tool_name == "get_daily_summary":
        return str(first_result.get("summary_text", "Here is your daily summary."))

    if tool_name == "create_study_plan":
        study_plan = first_result.get("study_plan", {})
        topic = study_plan.get("topic", "your topic")
        tasks = first_result.get("tasks", [])
        return f"Done — I created a study plan for {topic} with {len(tasks)} tasks."

    if tool_name == "create_future_me_goal":
        goal = first_result.get("goal", {})
        title = goal.get("title", "your goal")
        return f"Done — I created your Future Me goal: {title}"

    if tool_name == "create_future_me_weekly_plan":
        tasks = first_result.get("tasks", [])
        return f"Done — I created your Future Me weekly plan with {len(tasks)} tasks."

    return "Done — I completed the requested action."


async def _normal_answer(user_message: str) -> str:
    lower_message = user_message.lower().strip()

    if lower_message in {
        "what is rag?",
        "what is rag",
        "why do we use rag?",
        "why do we use rag",
    }:
        return (
            "RAG means Retrieval-Augmented Generation. "
            "It helps an LLM answer using retrieved external or user-specific context "
            "instead of relying only on the model's built-in knowledge."
        )

    answer = await _call_llm(
        messages=[
            {
                "role": "system",
                "content": _technical_assistant_prompt(),
            },
            {
                "role": "user",
                "content": user_message,
            },
        ],
        temperature=0.2,
        max_tokens=256,
    )

    return answer.strip()


async def run_agent(
    session: AsyncSession,
    user_id: int,
    user_message: str,
) -> dict[str, Any]:
    clean_message = " ".join((user_message or "").split()).strip()

    if not clean_message:
        return {
            "success": False,
            "final_response": "Please send a message for me to help with.",
            "planner_output": {},
            "tool_results": [],
        }

    deterministic_plan = _deterministic_plan(
        message=clean_message,
        user_id=user_id,
    )

    if deterministic_plan is not None:
        planner_output = deterministic_plan
    else:
        planner_prompt = _build_planner_prompt()

        try:
            planner_text = await _call_llm(
                messages=[
                    {
                        "role": "system",
                        "content": planner_prompt,
                    },
                    {
                        "role": "user",
                        "content": clean_message,
                    },
                ],
                temperature=0,
                max_tokens=512,
            )

            planner_output = _extract_json_object(planner_text)

        except Exception:
            logger.exception("Agent planner failed. Falling back to normal answer.")

            fallback_answer = await _normal_answer(clean_message)

            return {
                "success": True,
                "final_response": fallback_answer,
                "planner_output": {},
                "tool_results": [],
            }

    response_type = planner_output.get("response_type")

    if response_type == "final":
        deterministic_final = str(planner_output.get("final_response") or "").strip()

        if deterministic_plan is not None and deterministic_final:
            final_response = deterministic_final
        else:
            final_response = await _normal_answer(clean_message)

        return {
            "success": True,
            "final_response": final_response,
            "planner_output": planner_output,
            "tool_results": [],
        }

    if response_type != "tool_calls":
        fallback_answer = await _normal_answer(clean_message)

        return {
            "success": True,
            "final_response": fallback_answer,
            "planner_output": planner_output,
            "tool_results": [],
        }

    tool_calls = planner_output.get("tool_calls") or []

    if not isinstance(tool_calls, list) or not tool_calls:
        return {
            "success": False,
            "final_response": "I could not find a tool action to run.",
            "planner_output": planner_output,
            "tool_results": [],
        }

    tool_results: list[dict[str, Any]] = []

    for tool_call in tool_calls[:3]:
        tool_name = str(tool_call.get("tool_name") or "").strip()
        arguments = tool_call.get("arguments") or {}

        if not isinstance(arguments, dict):
            arguments = {}

        try:
            result = await execute_agent_tool(
                session=session,
                user_id=user_id,
                tool_name=tool_name,
                arguments=arguments,
            )
            tool_results.append(result)

        except Exception as exc:
            logger.exception("Agent tool execution failed.")

            tool_results.append(
                {
                    "tool": tool_name,
                    "success": False,
                    "error": str(exc),
                }
            )

    final_response = _format_tool_results(tool_results)

    return {
        "success": True,
        "final_response": final_response,
        "planner_output": planner_output,
        "tool_results": tool_results,
    }