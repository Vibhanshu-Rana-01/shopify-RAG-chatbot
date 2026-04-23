"""
embeddings.py
─────────────
Local embedding function using sentence-transformers.

Why local embeddings?
  - Zero cost, no API key required for embeddings
  - No rate limits — embed all 28 products instantly
  - Works offline
  - Gemini is still used for the smart response generation

Model: all-MiniLM-L6-v2
  - ~80 MB, downloads once and is cached automatically
  - Fast inference, excellent semantic search quality
  - Well tested with ChromaDB
"""

from sentence_transformers import SentenceTransformer
from chromadb import EmbeddingFunction, Documents, Embeddings

MODEL_NAME = "all-MiniLM-L6-v2"

# Singleton — model is loaded once per process, not on every call
_model_instance: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model_instance
    if _model_instance is None:
        print(f"  [LOAD] Loading embedding model '{MODEL_NAME}' (one-time ~80 MB download)...")
        _model_instance = SentenceTransformer(MODEL_NAME)
        print("  [OK] Embedding model ready.")
    return _model_instance


class LocalEmbeddingFunction(EmbeddingFunction):
    """
    ChromaDB-compatible embedding function using a local sentence-transformers model.
    No API keys. No rate limits. Works offline.
    """

    def __call__(self, input: Documents) -> Embeddings:
        model = _get_model()
        embeddings = model.encode(
            list(input),
            show_progress_bar=True,
            convert_to_numpy=True,
        )
        return embeddings.tolist()


# Alias — keeps ingest.py and rag.py imports unchanged
AppEmbeddingFunction = LocalEmbeddingFunction
