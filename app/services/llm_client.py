from litellm import acompletion

from app.core.config import get_settings

settings = get_settings()


async def generate_chat_response(user_message: str) -> str:
    try:
        response = await acompletion(
            model=f"ollama/{settings.ollama_model}",
            api_base=settings.ollama_base_url,
            messages=[
                {
                    "role": "system",
                    "content": (
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
                    ),
                },
                {
                    "role": "user",
                    "content": user_message,
                },
            ],
            temperature=0.2,
            max_tokens=250,
        )

        return response.choices[0].message.content

    except Exception as exc:
        return (
            "I could not reach the local LLM right now. "
            f"Technical detail: {type(exc).__name__}: {exc}"
        )