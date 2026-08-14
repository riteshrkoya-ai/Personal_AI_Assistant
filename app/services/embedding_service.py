import logging

import numpy as np
from fastembed import TextEmbedding

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_embedding_model: TextEmbedding | None = None


def get_embedding_model() -> TextEmbedding:
    global _embedding_model

    if _embedding_model is None:
        logger.info("Loading embedding model: %s", settings.embedding_model)
        _embedding_model = TextEmbedding(model_name=settings.embedding_model)

    return _embedding_model


def generate_embedding(text: str) -> list[float]:
    """
    Generate a normalized embedding for memory search.
    """
    clean_text = " ".join((text or "").split()).strip()

    if not clean_text:
        raise ValueError("Cannot generate embedding for empty text.")

    model = get_embedding_model()

    embedding = next(model.embed([clean_text]))
    normalized = embedding / np.linalg.norm(embedding)

    return normalized.tolist()
