import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from litellm import acompletion
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.agent_tools import AGENT_TOOL_SCHEMAS, execute_agent_tool

logger = logging.getLogger(__name__)
settings = get_settings()


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


def _parse_simple_reminder(message: str) -> dict[str, Any] | None:
    clean_message = " ".join(message.split()).strip()
    lower_message = clean_message.lower()

    if "remind me" not in lower_message:
        return None

    timezone = ZoneInfo(settings.timezone)
    now = datetime.now(timezone)

    day_offset: int | None = None

    if "tomorrow" in lower_message:
        day_offset = 1
    elif "today" in lower_message:
        day_offset = 0

    time_match = re.search(
        r"\b(at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
        lower_message,
    )

    if day_offset is None or not time_match:
        return {
            "response_type": "final",
            "final_response": "What date and time should I set the reminder for?",
            "tool_calls": [],
        }

    hour = int(time_match.group(2))
    minute = int(time_match.group(3) or 0)
    meridiem = time_match.group(4)

    if meridiem == "pm" and hour != 12:
        hour += 12

    if meridiem == "am" and hour == 12:
        hour = 0

    scheduled_time = (now + timedelta(days=day_offset)).replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )

    if scheduled_time <= now:
        return {
            "response_type": "final",
            "final_response": "That reminder time has already passed. What future time should I use?",
            "tool_calls": [],
        }

    message_part = clean_message

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
        r"(?i)\bat\s+\d{1,2}(:\d{2})?\s*(am|pm)\b",
        "",
        message_part,
    ).strip()

    message_part = re.sub(
        r"(?i)^to\s+",
        "",
        message_part,
    ).strip()

    if not message_part:
        message_part = "Reminder"

    return {
        "response_type": "tool_calls",
        "final_response": "",
        "tool_calls": [
            {
                "tool_name": "create_reminder",
                "arguments": {
                    "message": message_part,
                    "scheduled_time_iso": scheduled_time.isoformat(),
                },
            }
        ],
    }


def _deterministic_plan(message: str) -> dict[str, Any] | None:
    clean_message = " ".join((message or "").split()).strip()
    lower_message = clean_message.lower()

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

    reminder_plan = _parse_simple_reminder(clean_message)
    if reminder_plan is not None:
        return reminder_plan

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
        return f"Got it — I saved this memory: {content}"

    if tool_name == "search_memory":
        memories = first_result.get("memories", [])

        if not memories:
            return "I did not find any matching memories."

        memory_lines = [
            f"- {memory.get('content')}"
            for memory in memories
            if memory.get("content")
        ]

        return "Here is what I found in your memory:\n" + "\n".join(memory_lines)

    if tool_name == "create_reminder":
        reminder = first_result.get("reminder", {})
        message = reminder.get("message", "your reminder")
        scheduled_time = reminder.get("scheduled_time", "")
        return f"Done — I created the reminder: {message} at {scheduled_time}"

    if tool_name == "list_reminders":
        reminders = first_result.get("reminders", [])

        if not reminders:
            return "You do not have any pending reminders."

        reminder_lines = [
            f"- {reminder.get('scheduled_time')}: {reminder.get('message')}"
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

    deterministic_plan = _deterministic_plan(clean_message)

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