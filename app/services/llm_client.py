import logging

from app.services.llm_provider import (
    configured_acompletion,
    get_llm_model,
    is_local_ollama,
)

logger = logging.getLogger(__name__)


def build_memory_context(memories: list[str] | None) -> str:
    if not memories:
        return ""

    memory_lines = "\n".join(f"- {memory}" for memory in memories)

    return (
        "Relevant saved user memories:\n"
        f"{memory_lines}\n\n"
        "Use these memories only if they are relevant to the user's question. "
        "Do not mention memory unless it helps answer the question."
    )


async def generate_chat_response(
    user_message: str,
    memories: list[str] | None = None,
) -> str:
    """
    Generate a general assistant response using the configured LiteLLM provider.

    Local development defaults to Ollama. Render can override LLM_MODEL and
    provide a Gemini or Groq API key without changing local configuration.
    """
    memory_context = build_memory_context(memories)

    system_prompt = (
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
        "If relevant memories are provided, use them only when they clearly help answer the user's question. "
        "If memories are irrelevant, ignore them. "
        "Do not mention memories unless they help the answer. "
        "Do not claim to have completed actions, changed settings, saved data, or sent reminders unless explicitly confirmed by the system. "
        "Prefer direct answers over long explanations. "
        "For simple questions, answer in a few sentences. "
        "For comparisons, debugging, or design advice, use short bullets when helpful. "
        "Keep Telegram responses readable and not too long."
    )

    if memory_context:
        system_prompt += "\n\n" + memory_context

    try:
        response = await configured_acompletion(
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_message,
                },
            ],
            temperature=0.2,
            max_tokens=256,
        )

        return response.choices[0].message.content or "I could not generate a response."

    except Exception as exc:
        logger.exception("LLM request failed for model %s", get_llm_model())
        return (
            "I could not reach the configured LLM right now. "
            f"Technical detail: {type(exc).__name__}: {exc}"
        )


async def warm_up_model() -> None:
    if not is_local_ollama():
        logger.info("Skipping LLM warm-up for cloud model %s.", get_llm_model())
        return

    try:
        await configured_acompletion(
            messages=[
                {
                    "role": "user",
                    "content": "hi",
                }
            ],
            temperature=0,
            max_tokens=1,
        )
        logger.info("Ollama model warm-up completed.")
    except Exception:
        logger.exception("Ollama model warm-up failed.")