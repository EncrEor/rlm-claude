"""
RLM Embeddings - Semantic embedding providers for hybrid search.

Phase 8 implementation.

Provides two embedding providers:
- Model2VecProvider: minishlab/potion-multilingual-128M (256 dim, fast)
- FastEmbedProvider: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (384 dim, accurate)

Selection via RLM_EMBEDDING_PROVIDER env var (default: model2vec).
All dependencies are optional — returns None if unavailable.
"""

import os
import time
from abc import ABC, abstractmethod

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    np = None
    NUMPY_AVAILABLE = False


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    def embed(self, texts: list[str]):
        """Embed a list of texts into vectors.

        Args:
            texts: List of text strings to embed

        Returns:
            numpy ndarray of shape (len(texts), dim)
        """

    @abstractmethod
    def dim(self) -> int:
        """Return the embedding dimension."""


class Model2VecProvider(EmbeddingProvider):
    """Embedding provider using Model2Vec (minishlab/potion-multilingual-128M).

    256 dimensions, very fast inference, good multilingual support.
    """

    MODEL_NAME = "minishlab/potion-multilingual-128M"
    DIM = 256

    def __init__(self):
        from model2vec import StaticModel

        self._model = StaticModel.from_pretrained(self.MODEL_NAME)

    def embed(self, texts: list[str]):
        return self._model.encode(texts)

    def dim(self) -> int:
        return self.DIM


class FastEmbedProvider(EmbeddingProvider):
    """Embedding provider using FastEmbed (paraphrase-multilingual-MiniLM-L12-v2).

    384 dimensions, higher accuracy, slightly slower. ONNX-based.
    """

    MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    DIM = 384

    def __init__(self):
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=self.MODEL_NAME)

    def embed(self, texts: list[str]):
        # fastembed returns a generator
        embeddings = list(self._model.embed(texts))
        return np.array(embeddings)

    def dim(self) -> int:
        return self.DIM


# Singleton cache
_cached_provider: EmbeddingProvider | None = None
_provider_permanently_unavailable: bool = False
_last_error: str = ""
_last_attempt: float = 0.0

# A failed load is retried after this cooldown. Model loading is expensive
# (and may hit the network), so we don't retry on every single call — but we
# never give up for good either: a transient failure must not silence
# embeddings for the whole lifetime of the process.
RETRY_COOLDOWN_SECONDS = 300.0


def _get_cached_provider() -> EmbeddingProvider | None:
    """Get or create the cached embedding provider (singleton, lazy).

    Reads RLM_EMBEDDING_PROVIDER env var (default: "model2vec").
    Returns None if the provider cannot be loaded.

    Failure handling is deliberately asymmetric:
    - Missing library (ImportError) is permanent → cached, never retried.
    - Anything else (network, model download, disk) is transient → retried
      after RETRY_COOLDOWN_SECONDS.

    Why: model loading may reach out to the HuggingFace Hub. Caching a
    transient failure forever meant every chunk created by that process was
    stored without a vector, silently, until the server restarted.
    """
    global _cached_provider, _provider_permanently_unavailable, _last_error, _last_attempt

    if _cached_provider is not None:
        return _cached_provider

    if _provider_permanently_unavailable:
        return None

    now = time.monotonic()
    if _last_attempt and (now - _last_attempt) < RETRY_COOLDOWN_SECONDS:
        return None  # Cooling down after a recent transient failure

    _last_attempt = now
    provider_name = os.getenv("RLM_EMBEDDING_PROVIDER", "model2vec").lower()

    try:
        if provider_name == "fastembed":
            _cached_provider = FastEmbedProvider()
        else:
            _cached_provider = Model2VecProvider()
        _last_error = ""
    except ImportError as e:
        # Library not installed: no amount of retrying will help.
        _provider_permanently_unavailable = True
        _cached_provider = None
        _last_error = f"{provider_name} library not installed ({e})"
    except Exception as e:
        # Transient (network, Hub rate limit, disk): retry after cooldown.
        _cached_provider = None
        _last_error = f"{provider_name} failed to load ({type(e).__name__}: {e})"

    return _cached_provider


def get_provider_error() -> str:
    """Return the reason the provider is unavailable ("" if it loaded fine).

    Callers use this to report the failure instead of silently degrading.
    """
    return _last_error


def reset_provider_cache() -> None:
    """Clear the provider cache. Used by tests and after a config change."""
    global _cached_provider, _provider_permanently_unavailable, _last_error, _last_attempt
    _cached_provider = None
    _provider_permanently_unavailable = False
    _last_error = ""
    _last_attempt = 0.0


def get_provider() -> EmbeddingProvider | None:
    """Public API to get the current embedding provider.

    Returns None if the required library is not installed.
    """
    return _get_cached_provider()
