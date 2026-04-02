from sentence_transformers import SentenceTransformer

# Free local model — no AWS cost for embeddings
_model = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Get embeddings using a free local sentence-transformers model."""
    model = _get_model()
    embeddings = model.encode(texts, show_progress_bar=False)
    return embeddings.tolist()
