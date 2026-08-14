import json
import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from litellm import acompletion
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.agent_tools import AGENT_TOOL_SCHEMAS, execute_agent_tool

logger = logging.getLogger(__name__)
settings = get_settings()

# Design rule for this file: NO natural-language parsing lives here.
# The planner LLM decides which tool to call and with what arguments.
# Deterministic code is allowed in exactly one place: formatting tool
# RESULTS into user-facing text (_format_tool_results). Every regex added
# above the planner makes the "agent" less real.

MAX_HISTORY_MESSAGES = 6


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
        "Do not invent technical definitions, facts, implementation details, or user-specific information. "
        "If you are unsure, say you are unsure. "
        "Prefer direct answers over long explanations. "
        "Keep responses readable and not too long."
    )


def _build_planner_prompt() -> str:
    now = datetime.now(ZoneInfo(settings.timezone))

    return f"""
You are an AI personal assistant agent planner.

Your job is to decide whether the user's latest message needs a tool call.

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
- If the user says remember, save, note, or keep in mind something personal, use save_memory.
- If the user asks what you remember or know about them, use search_memory.
- If creating a reminder, use create_reminder.
- If listing reminders, use list_reminders.
- If the user asks what they should focus on today, use get_daily_summary.
- If the user asks to create a study plan, use create_study_plan.
- If the user asks to create a future goal, use create_future_me_goal.
- If the user asks to complete a study task, use complete_study_task.
- If the user asks to complete a Future Me task, use complete_future_me_task.
- Use the earlier conversation messages for context. If your previous message
  asked a clarifying question (for example, asking for a reminder time), treat
  the user's latest message as the answer and complete the original request.
- If a reminder request is missing a clear future date or time, do not call a
  tool. Return response_type "final" with one short clarification question.
- For create_reminder, scheduled_time_iso must be a future ISO datetime.
  Convert relative times like "tomorrow at 8pm" using the current datetime above.
- The server injects user_id. Never ask for or generate user_id.

Return JSON in exactly one of these formats.

For a normal answer without tools:
{{
  "response_type": "final",
  "final_response": "",
  "tool_calls": []
}}

For a clarification question:
{{
  "response_type": "final",
  "final_response": "your one short question here",
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

You may return multiple tool calls only when the user's message clearly asks
for multiple actions. Keep arguments minimal and accurate.
""".strip()


async def _call_llm(
    messages: list[dict[str, str]],
    temperature: float = 0.1,
    max_tokens: int = 512,
) -> str:
    kwargs: dict[str, Any] = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if settings.llm_model.startswith("ollama/"):
        kwargs["api_base"] = settings.ollama_base_url

    response = await acompletion(**kwargs)

    return _message_content(response)


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

    if tool_name == "complete_study_task":
        task_id = first_result.get("task_id")
        completed = first_result.get("completed") is True

        if completed:
            return f"Done — I marked study task {task_id} as completed."

        return (
            f"I could not mark study task {task_id} as completed. "
            "It may not exist, may not belong to you, or may already be completed."
        )

    if tool_name == "create_future_me_goal":
        goal = first_result.get("goal", {})
        title = goal.get("title", "your goal")
        return f"Done — I created your Future Me goal: {title}"

    if tool_name == "create_future_me_weekly_plan":
        tasks = first_result.get("tasks", [])
        return f"Done — I created your Future Me weekly plan with {len(tasks)} tasks."

    if tool_name == "complete_future_me_task":
        task_id = first_result.get("task_id")
        completed = first_result.get("completed") is True

        if completed:
            return f"Done — I marked Future Me task {task_id} as completed."

        return (
            f"I could not mark Future Me task {task_id} as completed. "
            "It may not exist, may not belong to you, or may already be completed."
        )

    return "Done."


async def _normal_answer(
    user_message: str,
    recent_history: list[dict[str, str]] | None = None,
) -> str:
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": _technical_assistant_prompt(),
        }
    ]

    if recent_history:
        messages.extend(recent_history)

    messages.append(
        {
            "role": "user",
            "content": user_message,
        }
    )

    answer = await _call_llm(
        messages=messages,
        temperature=0.2,
        max_tokens=512,
    )

    return answer.strip()


async def run_agent(
    session: AsyncSession,
    user_id: int,
    user_message: str,
    recent_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """
    One full agent turn.

    recent_history: the last few chat messages for this user, oldest first,
    as [{"role": "user"|"assistant", "content": "..."}]. This is how
    clarification turns work: if the assistant just asked "What time?",
    the planner sees that question and treats the new message as the answer.

    The caller owns the session and the commit.
    """
    clean_message = " ".join((user_message or "").split()).strip()

    if not clean_message:
        return {
            "success": False,
            "final_response": "Please send a message for me to help with.",
            "planner_output": {},
            "tool_results": [],
        }

    planner_messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": _build_planner_prompt(),
        }
    ]

    if recent_history:
        planner_messages.extend(recent_history[-MAX_HISTORY_MESSAGES:])

    planner_messages.append(
        {
            "role": "user",
            "content": clean_message,
        }
    )

    try:
        planner_text = await _call_llm(
            messages=planner_messages,
            temperature=0,
            max_tokens=512,
        )

        planner_output = _extract_json_object(planner_text)

    except Exception:
        logger.exception("Agent planner failed. Falling back to normal answer.")

        fallback_answer = await _normal_answer(clean_message, recent_history)

        return {
            "success": True,
            "final_response": fallback_answer,
            "planner_output": {},
            "tool_results": [],
        }

    response_type = planner_output.get("response_type")

    if response_type == "final":
        planner_final = str(planner_output.get("final_response") or "").strip()

        # If the planner wrote a clarification question, use it directly.
        # Otherwise generate a normal conversational answer.
        if planner_final:
            final_response = planner_final
        else:
            final_response = await _normal_answer(clean_message, recent_history)

        return {
            "success": True,
            "final_response": final_response,
            "planner_output": planner_output,
            "tool_results": [],
        }

    if response_type != "tool_calls":
        fallback_answer = await _normal_answer(clean_message, recent_history)

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

        logger.info(
            "agent tool=%s args=%s user_id=%s",
            tool_name,
            json.dumps(arguments)[:200],
            user_id,
        )

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