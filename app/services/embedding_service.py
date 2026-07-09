import logging

from sentence_transformers import SentenceTransformer

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_embedding_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    global _embedding_model

    if _embedding_model is None:
        logger.info("Loading embedding model: %s", settings.embedding_model)
        _embedding_model = SentenceTransformer(settings.embedding_model)

    return _embedding_model


def generate_embedding(text: str) -> list[float]:
    """
    Generate a normalized embedding for memory search.
    """
    clean_text = " ".join((text or "").split()).strip()

    if not clean_text:
        raise ValueError("Cannot generate embedding for empty text.")

    model = get_embedding_model()

    embedding = model.encode(
        clean_text,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    return embedding.tolist()