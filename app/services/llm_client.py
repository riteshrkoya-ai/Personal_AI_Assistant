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
                        "You are a helpful AI personal assistant MVP. "
                        "You can answer general questions clearly and simply. "
                        "Memory, reminders, and Future Me planning will be added in later phases."
                    ),
                },
                {
                    "role": "user",
                    "content": user_message,
                },
            ],
        )

        return response.choices[0].message.content

    except Exception as exc:
        return (
            "I could not reach the local LLM right now. "
            f"Technical detail: {type(exc).__name__}: {exc}"
        )