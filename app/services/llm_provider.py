from typing import Any

from litellm import acompletion as litellm_acompletion

from app.core.config import get_settings

settings = get_settings()


def get_llm_model() -> str:
    """Return the configured cloud model, or preserve the local Ollama default."""
    return settings.llm_model or f"ollama/{settings.ollama_model}"


def is_local_ollama() -> bool:
    return get_llm_model().startswith("ollama/")


async def configured_acompletion(
    *,
    messages: list[dict[str, str]],
    temperature: float | None = None,
    max_tokens: int | None = None,
    **kwargs: Any,
) -> Any:
    """Call LiteLLM using the provider selected by environment variables."""
    model = get_llm_model()

    # Ignore any old hard-coded model/api_base values supplied by callers.
    # This lets existing agent code keep working while environment variables
    # choose Ollama locally or Gemini/Groq on Render.
    call_kwargs = dict(kwargs)
    call_kwargs.pop("model", None)
    call_kwargs.pop("api_base", None)
    call_kwargs.pop("api_key", None)

    call_kwargs["model"] = model
    call_kwargs["messages"] = messages

    if temperature is not None:
        call_kwargs["temperature"] = temperature

    if max_tokens is not None:
        call_kwargs["max_tokens"] = max_tokens

    if model.startswith("ollama/"):
        call_kwargs["api_base"] = settings.ollama_base_url

    elif model.startswith("gemini/"):
        if not settings.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is required when LLM_MODEL uses the gemini/ provider."
            )
        call_kwargs["api_key"] = settings.gemini_api_key

    elif model.startswith("groq/"):
        if not settings.groq_api_key:
            raise RuntimeError(
                "GROQ_API_KEY is required when LLM_MODEL uses the groq/ provider."
            )
        call_kwargs["api_key"] = settings.groq_api_key

    return await litellm_acompletion(**call_kwargs)