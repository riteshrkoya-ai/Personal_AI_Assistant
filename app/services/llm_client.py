import logging

from litellm import acompletion

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


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


def get_llm_request_config() -> tuple[str, dict]:
    """
    Return the LiteLLM model name and provider-specific keyword arguments.

    Local Docker uses Ollama:
        LLM_PROVIDER=ollama
        OLLAMA_MODEL=llama3.2:3b
        OLLAMA_BASE_URL=http://ollama:11434

    Render/cloud uses Gemini:
        LLM_PROVIDER=gemini
        GEMINI_API_KEY=...
        GEMINI_MODEL=gemini-2.5-flash
    """
    provider = settings.llm_provider.strip().lower()

    if provider == "ollama":
        return (
            f"ollama/{settings.ollama_model}",
            {
                "api_base": settings.ollama_base_url,
            },
        )

    if provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")

        gemini_model = settings.gemini_model.strip()

        if not gemini_model.startswith("gemini/"):
            gemini_model = f"gemini/{gemini_model}"

        return (
            gemini_model,
            {
                "api_key": settings.gemini_api_key,
            },
        )

    raise ValueError(
        f"Unsupported LLM_PROVIDER='{settings.llm_provider}'. "
        "Supported values are: ollama, gemini."
    )


async def generate_chat_response(
    user_message: str,
    memories: list[str] | None = None,
) -> str:
    """
    Generate a general assistant response using the configured LLM provider.

    Local development can use Ollama.
    Render/cloud deployment can use Gemini.
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
        model, provider_kwargs = get_llm_request_config()

        response = await acompletion(
            model=model,
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
            **provider_kwargs,
        )

        return response.choices[0].message.content or "I could not generate a response."

    except Exception as exc:
        logger.exception("LLM response generation failed.")
        return (
            "I could not reach the configured LLM right now. "
            f"Technical detail: {type(exc).__name__}: {exc}"
        )


async def warm_up_model() -> None:
    """
    Warm up the local Ollama model during local Docker startup.

    For Gemini/cloud providers, we skip warm-up to avoid unnecessary API calls.
    """
    provider = settings.llm_provider.strip().lower()

    if provider != "ollama":
        logger.info("LLM warm-up skipped because provider is '%s'.", provider)
        return

    try:
        model, provider_kwargs = get_llm_request_config()

        await acompletion(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": "hi",
                }
            ],
            temperature=0,
            max_tokens=1,
            **provider_kwargs,
        )
        logger.info("Ollama model warm-up completed.")
    except Exception:
        logger.exception("Ollama model warm-up failed.")