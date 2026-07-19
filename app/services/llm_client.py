import logging

from litellm import acompletion

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def warm_up_model() -> None:
    """
    Send a throwaway prompt to Ollama on startup so the model is already
    loaded into memory before the first real user message arrives.
    """
    try:
        await acompletion(
            model=f"ollama/{settings.ollama_model}",
            api_base=settings.ollama_base_url,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=1,
        )
        logger.info("Ollama model %s warmed up successfully", settings.ollama_model)
    except Exception:
        logger.exception("Ollama model warm-up failed")


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
    Generate a general assistant response using the configured Ollama model.

    This is not full document RAG yet. For Phase 3, we can optionally pass
    relevant user memories into the prompt.
    """
    memory_context = build_memory_context(memories)

    system_prompt = (
        "You are a helpful AI personal assistant for a software engineering project. "
        "Answer clearly, accurately, and concisely. "
        "The user may ask about Python, FastAPI, Docker, PostgreSQL, APIs, system design, "
        "AI, ML, LLMs, RAG, vector databases, and software architecture. "
        "When the user asks about RAG in AI, ML, LLM, or software context, "
        "RAG means Retrieval-Augmented Generation. "
        "If an acronym has multiple meanings, choose the meaning that best fits the user's context. "
        "If the context is unclear, briefly mention the likely meaning and ask a clarifying question. "
        "Do not invent technical definitions. If you are unsure, say you are unsure. "
        "Keep Telegram responses readable and not too long."
    )

    if memory_context:
        system_prompt += "\n\n" + memory_context

    try:
        response = await acompletion(
            model=f"ollama/{settings.ollama_model}",
            api_base=settings.ollama_base_url,
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
            max_tokens=250,
        )

        return response.choices[0].message.content or "I could not generate a response."

    except Exception as exc:
        return (
            "I could not reach the local LLM right now. "
            f"Technical detail: {type(exc).__name__}: {exc}"
        )