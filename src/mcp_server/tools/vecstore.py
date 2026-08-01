"""
RLM Vector Store - Numpy-based vector storage for semantic search.

Phase 8 implementation.

Stores chunk embeddings in a .npz file for fast cosine similarity search.
All numpy operations are guarded — module degrades gracefully if numpy is absent.
"""

import fcntl
import os
import uuid
from contextlib import contextmanager
from pathlib import Path

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    np = None
    NUMPY_AVAILABLE = False

from .fileutil import CONTEXT_DIR

DEFAULT_EMBEDDINGS_PATH = CONTEXT_DIR / "embeddings.npz"


class VectorStore:
    """Numpy-based vector store for chunk embeddings.

    Stores vectors in a .npz file with two arrays:
    - chunk_ids: 1D array of chunk ID strings
    - vectors: 2D array of float32 vectors

    Search uses brute-force cosine similarity (fast enough for <10k chunks).
    """

    def __init__(self, path: Path | None = None):
        """Initialize the vector store.

        Args:
            path: Path to the .npz file (default: CONTEXT_DIR/embeddings.npz)
        """
        self.path = path or DEFAULT_EMBEDDINGS_PATH
        self.chunk_ids: list[str] = []
        self.vectors = None  # np.ndarray or None

    def load(self) -> bool:
        """Load vectors from .npz file.

        Returns:
            True if loaded successfully, False if file doesn't exist or numpy unavailable
        """
        if not NUMPY_AVAILABLE:
            return False

        if not self.path.exists():
            return False

        try:
            data = np.load(self.path, allow_pickle=True)
            self.chunk_ids = list(data["chunk_ids"])
            self.vectors = data["vectors"].astype(np.float32)
            return True
        except Exception:
            self.chunk_ids = []
            self.vectors = None
            return False

    def save(self) -> None:
        """Persist vectors atomically to .npz file."""
        if not NUMPY_AVAILABLE or self.vectors is None or len(self.chunk_ids) == 0:
            return

        # Ensure parent directory exists
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write: save to temp then rename.
        # np.savez auto-appends .npz if the name doesn't end with it, so the
        # temp file must already carry the extension.
        # The name is per-process: a shared "_tmp.npz" meant two concurrent
        # writers clobbered each other's temp file, and the loser crashed on
        # rename (FileNotFoundError) after its vector was already lost.
        tmp_path = (
            self.path.parent / f"{self.path.stem}_tmp_{os.getpid()}_{uuid.uuid4().hex[:8]}.npz"
        )
        try:
            np.savez(
                tmp_path,
                chunk_ids=np.array(self.chunk_ids, dtype=object),
                vectors=self.vectors.astype(np.float32),
            )
            tmp_path.replace(self.path)
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink()
            raise

    @contextmanager
    def locked(self):
        """Hold an exclusive lock across a read-modify-write of the store.

        Vector writes are read-modify-write (load → add → save). Without a
        lock, two sessions both load N vectors, each adds one, and whichever
        saves last drops the other's — silently, since nothing raises.

        Usage:
            store = VectorStore()
            with store.locked():
                store.load()
                store.add(chunk_id, vec)
                store.save()
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = self.path.with_suffix(".npz.lock")
        lock_fd = open(lock_file, "w")
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            yield self
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
            try:
                lock_file.unlink(missing_ok=True)
            except OSError:
                pass

    def add(self, chunk_id: str, vector) -> None:
        """Add a vector for a chunk.

        If chunk_id already exists, replaces the vector.

        Args:
            chunk_id: The chunk identifier
            vector: 1D numpy array (embedding vector)
        """
        if not NUMPY_AVAILABLE:
            return

        vector = np.asarray(vector, dtype=np.float32).reshape(1, -1)

        # Replace if exists
        if chunk_id in self.chunk_ids:
            idx = self.chunk_ids.index(chunk_id)
            self.vectors[idx] = vector[0]
            return

        # Append
        self.chunk_ids.append(chunk_id)
        if self.vectors is None:
            self.vectors = vector
        else:
            self.vectors = np.vstack([self.vectors, vector])

    def remove(self, chunk_id: str) -> bool:
        """Remove a chunk's vector.

        Args:
            chunk_id: The chunk identifier to remove

        Returns:
            True if found and removed, False if not found
        """
        if not NUMPY_AVAILABLE or chunk_id not in self.chunk_ids:
            return False

        idx = self.chunk_ids.index(chunk_id)
        self.chunk_ids.pop(idx)

        if self.vectors is not None:
            self.vectors = np.delete(self.vectors, idx, axis=0)
            if len(self.chunk_ids) == 0:
                self.vectors = None

        return True

    def search(self, query_vec, top_k: int = 5) -> list[tuple[str, float]]:
        """Search for nearest vectors using cosine similarity.

        Args:
            query_vec: 1D numpy array (query embedding)
            top_k: Maximum number of results

        Returns:
            List of (chunk_id, score) tuples, scores in [0, 1], sorted descending
        """
        if not NUMPY_AVAILABLE or self.vectors is None or len(self.chunk_ids) == 0:
            return []

        query_vec = np.asarray(query_vec, dtype=np.float32).reshape(1, -1)

        # Cosine similarity: dot(q, v) / (||q|| * ||v||)
        q_norm = np.linalg.norm(query_vec)
        if q_norm == 0:
            return []

        v_norms = np.linalg.norm(self.vectors, axis=1)
        # Avoid division by zero
        v_norms = np.where(v_norms == 0, 1e-10, v_norms)

        similarities = (self.vectors @ query_vec.T).flatten() / (v_norms * q_norm)

        # Clamp to [0, 1] (negative similarities treated as 0)
        similarities = np.clip(similarities, 0, 1)

        # Top-k
        k = min(top_k, len(self.chunk_ids))
        top_indices = np.argsort(similarities)[::-1][:k]

        results = []
        for idx in top_indices:
            score = float(similarities[idx])
            if score > 0:
                results.append((self.chunk_ids[idx], score))

        return results
