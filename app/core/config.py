from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Personal Assistant"
    app_env: str = "local"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    database_url: str

    # LLM provider
    # Local Docker: LLM_PROVIDER=ollama
    # Render cloud: LLM_PROVIDER=gemini
    llm_provider: str = "ollama"

    # Ollama settings for local development
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2:3b"

    # Gemini settings for Render/cloud deployment
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"

    telegram_bot_token: str | None = None
    authorized_telegram_chat_ids: str | None = None
    api_base_url: str = "http://api:8000"

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    memory_search_top_k: int = 5

    timezone: str = "America/New_York"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()