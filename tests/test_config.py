"""Tests for settings defaults.

These assert on the declared field defaults rather than an instantiated
Settings object, so a populated .env or container environment cannot mask a
changed default.
"""

from app.core.config import Settings


def test_database_url_is_the_only_required_setting():
    required = {
        name
        for name, field in Settings.model_fields.items()
        if field.is_required()
    }

    assert required == {"database_url"}


def test_telegram_mode_defaults_to_polling():
    """Startup raises in webhook mode unless URL and secret are also set,
    so polling must stay the default for local runs."""
    assert Settings.model_fields["telegram_mode"].default == "polling"


def test_webhook_settings_default_to_none():
    assert Settings.model_fields["telegram_webhook_url"].default is None
    assert Settings.model_fields["telegram_webhook_secret"].default is None


def test_embedding_dimension_matches_default_embedding_model():
    """all-MiniLM-L6-v2 emits 384-dim vectors and the pgvector column is
    sized from this value; the two must not drift apart."""
    assert Settings.model_fields["embedding_model"].default == (
        "sentence-transformers/all-MiniLM-L6-v2"
    )
    assert Settings.model_fields["embedding_dimension"].default == 384


def test_cloud_credentials_default_to_none():
    """Local runs must work with no cloud keys configured."""
    assert Settings.model_fields["llm_model"].default is None
    assert Settings.model_fields["gemini_api_key"].default is None
    assert Settings.model_fields["groq_api_key"].default is None
