import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_embedding_model: Any | None = None


def get_embedding_model() -> Any:
    global _embedding_model

    if _embedding_model is not None:
        return _embedding_model

    logger.info(
        "Loading embedding model %s with backend %s",
        settings.embedding_model,
        settings.embedding_backend,
    )

    if settings.embedding_backend == "fastembed":
        from fastembed import TextEmbedding

        _embedding_model = TextEmbedding(model_name=settings.embedding_model)
        return _embedding_model

    from sentence_transformers import SentenceTransformer

    _embedding_model = SentenceTransformer(settings.embedding_model)
    return _embedding_model


def generate_embedding(text: str) -> list[float]:
    """Generate a normalized embedding for memory search."""
    clean_text = " ".join((text or "").split()).strip()

    if not clean_text:
        raise ValueError("Cannot generate embedding for empty text.")

    model = get_embedding_model()

    if settings.embedding_backend == "fastembed":
        import numpy as np

        embedding = next(model.embed([clean_text]))
        norm = np.linalg.norm(embedding)

        if norm == 0:
            raise ValueError("Embedding model returned a zero-length vector.")

        return (embedding / norm).tolist()

    embedding = model.encode(
        clean_text,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    return embedding.tolist()