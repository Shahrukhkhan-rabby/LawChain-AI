"""
Document store for LawChain-AI PDF Chatbot.

Manages per-session FAISS indexes and chunk metadata, enforcing strict
session isolation for all vector similarity searches.
"""

from __future__ import annotations

import logging

import faiss
import numpy as np

from app.core.config import settings
from app.models.models import Chunk, EmbeddedChunk

logger = logging.getLogger(__name__)

# Dimensionality driven by config (384 for all-MiniLM-L6-v2)
_VECTOR_DIM = settings.EMBEDDING_DIM


class DocumentStore:
    """In-memory, per-session FAISS vector store with chunk metadata.

    Each session gets its own :class:`faiss.IndexFlatL2` instance and a
    parallel list of :class:`Chunk` objects.  Session isolation is enforced
    by design: every lookup is scoped to a single session's index.
    """

    def __init__(self) -> None:
        # session_id → FAISS index
        self._indexes: dict[str, faiss.IndexFlatL2] = {}
        # session_id → list of Chunk objects (parallel to FAISS index vectors)
        self._chunks: dict[str, list[Chunk]] = {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def store_chunks(
        self,
        session_id: str,
        embedded_chunks: list[EmbeddedChunk],
    ) -> None:
        """Add embedded chunks to the session's FAISS index.

        Creates a new index for *session_id* if one does not already exist.

        Args:
            session_id: The session that owns these chunks.
            embedded_chunks: List of :class:`EmbeddedChunk` objects to store.
        """
        if not embedded_chunks:
            return

        # Lazily create the index and metadata list for this session
        if session_id not in self._indexes:
            self._indexes[session_id] = faiss.IndexFlatL2(_VECTOR_DIM)
            self._chunks[session_id] = []

        index = self._indexes[session_id]
        chunk_list = self._chunks[session_id]

        # Build a float32 matrix: shape (n, 1536)
        vectors = np.array(
            [ec.vector for ec in embedded_chunks], dtype=np.float32
        )
        index.add(vectors)  # type: ignore[arg-type]

        # Append chunk metadata in the same order as the vectors
        for ec in embedded_chunks:
            chunk_list.append(ec.chunk)

        logger.debug(
            "Stored %d chunks for session %s (index total: %d)",
            len(embedded_chunks),
            session_id,
            index.ntotal,
        )

    def similarity_search(
        self,
        session_id: str,
        query_vector: list[float],
        k: int = 5,
    ) -> list[Chunk]:
        """Return the *k* most similar chunks for *session_id*.

        Args:
            session_id: The session to search within.
            query_vector: A 1536-dimensional query embedding.
            k: Maximum number of results to return.

        Returns:
            Up to *k* :class:`Chunk` objects ordered by ascending L2 distance.
            Returns an empty list if no index exists for *session_id* or the
            index contains no vectors.
        """
        if session_id not in self._indexes:
            return []

        index = self._indexes[session_id]
        chunk_list = self._chunks[session_id]

        if index.ntotal == 0:
            return []

        # Clamp k to the number of stored vectors
        effective_k = min(k, index.ntotal)

        query = np.array([query_vector], dtype=np.float32)
        _distances, indices = index.search(query, effective_k)  # type: ignore[arg-type]

        results: list[Chunk] = []
        for idx in indices[0]:
            if idx < 0 or idx >= len(chunk_list):
                # FAISS may return -1 for padding when fewer results exist
                continue
            chunk = chunk_list[idx]
            # Enforce session isolation — every returned chunk must belong to
            # the requested session (guaranteed by design, but verified here)
            assert chunk.session_id == session_id, (
                f"Session isolation violation: chunk.session_id={chunk.session_id!r} "
                f"!= requested session_id={session_id!r}"
            )
            results.append(chunk)

        return results

    def delete_session(self, session_id: str) -> None:
        """Remove the FAISS index and all chunk metadata for *session_id*.

        This is a no-op if *session_id* has no associated data.

        Args:
            session_id: The session whose data should be deleted.
        """
        removed_index = self._indexes.pop(session_id, None)
        removed_chunks = self._chunks.pop(session_id, None)

        if removed_index is not None or removed_chunks is not None:
            logger.info(
                "Deleted document store for session %s",
                session_id,
            )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

document_store = DocumentStore()
