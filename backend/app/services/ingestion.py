"""
Ingestion pipeline for LawChain-AI PDF Chatbot.

Provides PDF text extraction, text chunking, and local TF-IDF
embeddings via scikit-learn HashingVectorizer (pure Python, no native
dependencies, no fitting required).
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

import numpy as np
import pdfplumber
import tiktoken
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.preprocessing import normalize

from app.core.config import settings
from app.models.models import (
    Chunk,
    EmbeddedChunk,
    IngestionResult,
    OCRRequiredError,
    PageText,
)

if TYPE_CHECKING:
    from app.services.document_store import DocumentStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

_ENCODING_NAME = "cl100k_base"
_tokenizer = tiktoken.get_encoding(_ENCODING_NAME)


def _token_length(text: str) -> int:
    return len(_tokenizer.encode(text))


# ---------------------------------------------------------------------------
# Hashing vectorizer — stateless, no fitting needed, always works
# ---------------------------------------------------------------------------

_vectorizer = HashingVectorizer(
    n_features=settings.EMBEDDING_DIM,
    norm="l2",
    alternate_sign=False,
    analyzer="word",
    ngram_range=(1, 2),
    strip_accents="unicode",
    token_pattern=r"\w{2,}",
)


def _embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts using hashing vectorizer — returns dense 384-dim vectors."""
    sparse = _vectorizer.transform(texts)
    dense: np.ndarray = sparse.toarray().astype(np.float32)
    # Re-normalise rows (HashingVectorizer norm='l2' handles sparse but
    # toarray() may lose precision — normalise again to be safe)
    norms = np.linalg.norm(dense, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    dense = dense / norms
    return dense.tolist()


# ---------------------------------------------------------------------------
# Task 4.1 — extract_text_by_page
# ---------------------------------------------------------------------------


def extract_text_by_page(pdf_bytes: bytes) -> list[PageText]:
    """Extract text from each page of a PDF document.

    Args:
        pdf_bytes: Raw bytes of the PDF file.

    Returns:
        A list of :class:`PageText` objects ordered by ascending ``page_number``
        (1-indexed).

    Raises:
        OCRRequiredError: If every page fails text extraction (image-only PDF).
    """
    import io

    results: list[PageText] = []

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for idx, page in enumerate(pdf.pages):
                page_number = idx + 1  # 1-indexed
                try:
                    raw_text = page.extract_text()
                    text = raw_text if raw_text is not None else ""
                    results.append(
                        PageText(
                            page_number=page_number,
                            text=text,
                            extraction_failed=False,
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Page extraction failed",
                        extra={"page_number": page_number, "error": str(exc)},
                    )
                    results.append(
                        PageText(
                            page_number=page_number,
                            text="",
                            extraction_failed=True,
                        )
                    )
    except Exception as exc:  # noqa: BLE001
        # If we cannot open the PDF at all, treat it as a single failed page
        logger.warning(
            "Failed to open PDF for text extraction",
            extra={"error": str(exc)},
        )
        results.append(
            PageText(page_number=1, text="", extraction_failed=True)
        )

    # Check whether ALL pages failed (image-only document)
    if results and all(p.extraction_failed for p in results):
        raise OCRRequiredError(
            "Document contains only scanned images and requires OCR processing."
        )

    # Ensure ascending order by page_number (pdfplumber preserves order, but
    # be explicit for correctness)
    results.sort(key=lambda p: p.page_number)
    return results


# ---------------------------------------------------------------------------
# Task 4.3 — chunk_text
# ---------------------------------------------------------------------------


def chunk_text(
    pages: list[PageText],
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    doc_id: str = "",
    session_id: str = "",
    filename: str = "",
) -> list[Chunk]:
    """Split page text into overlapping token-bounded chunks.

    Args:
        pages: List of :class:`PageText` objects (failed pages are skipped).
        chunk_size: Maximum number of tokens per chunk.
        chunk_overlap: Number of tokens to overlap between consecutive chunks.
        doc_id: Document identifier to attach to every :class:`Chunk`.
        session_id: Session identifier to attach to every :class:`Chunk`.
        filename: Source filename to attach to every :class:`Chunk`.

    Returns:
        A non-empty list of :class:`Chunk` objects.

    Raises:
        AssertionError: If no chunks are produced from the provided pages.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=_token_length,
        # Use common separators; fall back to character-level splitting
        separators=["\n\n", "\n", " ", ""],
    )

    result: list[Chunk] = []

    for page in pages:
        if page.extraction_failed:
            continue  # skip failed pages as per spec

        raw_chunks = splitter.split_text(page.text)

        for raw_chunk in raw_chunks:
            token_count = _token_length(raw_chunk)
            chunk = Chunk(
                chunk_id=str(uuid.uuid4()),
                doc_id=doc_id,
                session_id=session_id,
                filename=filename,
                page_number=page.page_number,
                text=raw_chunk,
                token_count=token_count,
            )
            result.append(chunk)

    assert len(result) > 0, (
        "chunk_text produced no chunks — ensure at least one page has extractable text."
    )
    return result


# ---------------------------------------------------------------------------
# Task 5.1 — embed_chunks
# ---------------------------------------------------------------------------


def embed_chunks(chunks: list[Chunk]) -> list[EmbeddedChunk]:
    """Embed chunks using HashingVectorizer (pure Python, no native deps).

    Stateless — no fitting required. Works with any corpus size.
    Produces 384-dimensional L2-normalised vectors.
    """
    texts = [c.text for c in chunks]
    vectors = _embed_texts(texts)

    result: list[EmbeddedChunk] = [
        EmbeddedChunk(chunk=chunk, vector=vector)
        for chunk, vector in zip(chunks, vectors)
    ]

    assert len(result) == len(chunks), (
        f"embed_chunks: expected {len(chunks)} embeddings, got {len(result)}."
    )
    return result


# ---------------------------------------------------------------------------
# Task 5.6 — IngestionPipeline
# ---------------------------------------------------------------------------


class IngestionPipeline:
    """Orchestrates the full document ingestion pipeline.

    Phases:
    1. Validate PDF magic bytes.
    2. Extract text page-by-page via :func:`extract_text_by_page`.
    3. Chunk text via :func:`chunk_text`.
    4. Embed chunks via :func:`embed_chunks`.
    5. Persist to the :class:`~app.services.document_store.DocumentStore`.
    """

    def __init__(self, document_store: "DocumentStore") -> None:
        self._document_store = document_store

    def ingest_document(
        self,
        pdf_bytes: bytes,
        doc_id: str,
        session_id: str,
        filename: str,
    ) -> IngestionResult:
        """Run the full ingestion pipeline for a single PDF document.

        Args:
            pdf_bytes: Raw bytes of the uploaded PDF.
            doc_id: Unique identifier for this document.
            session_id: Session that owns this document.
            filename: Original filename (used for citation metadata).

        Returns:
            An :class:`IngestionResult` with ``status="ready"`` on success or
            ``status="error"`` on failure.
        """
        # ------------------------------------------------------------------
        # Step 1: Validate PDF magic bytes
        # ------------------------------------------------------------------
        if pdf_bytes[:4] != b"%PDF":
            return IngestionResult(
                status="error",
                error_message="Not a valid PDF",
                chunk_count=0,
                failed_pages=[],
                doc_id=doc_id,
                filename=filename,
            )

        # ------------------------------------------------------------------
        # Step 2: Extract text page-by-page
        # ------------------------------------------------------------------
        try:
            pages = extract_text_by_page(pdf_bytes)
        except OCRRequiredError:
            return IngestionResult(
                status="error",
                error_message=(
                    "Document contains only scanned images and requires OCR processing."
                ),
                chunk_count=0,
                failed_pages=[],
                doc_id=doc_id,
                filename=filename,
            )

        # ------------------------------------------------------------------
        # Step 3: Collect failed pages and log each
        # ------------------------------------------------------------------
        failed_pages: list[int] = [
            p.page_number for p in pages if p.extraction_failed
        ]
        for page_number in failed_pages:
            logger.warning(
                "Page extraction failed during ingestion",
                extra={
                    "doc_id": doc_id,
                    "session_id": session_id,
                    "page_number": page_number,
                },
            )

        # ------------------------------------------------------------------
        # Step 4: Chunk valid pages
        # ------------------------------------------------------------------
        valid_pages = [p for p in pages if not p.extraction_failed]
        chunks = chunk_text(
            valid_pages,
            chunk_size=1000,
            chunk_overlap=200,
            doc_id=doc_id,
            session_id=session_id,
            filename=filename,
        )

        # ------------------------------------------------------------------
        # Step 5: Embed chunks
        # ------------------------------------------------------------------
        embedded_chunks = embed_chunks(chunks)

        # ------------------------------------------------------------------
        # Step 6: Persist to document store
        # ------------------------------------------------------------------
        self._document_store.store_chunks(session_id, embedded_chunks)

        # ------------------------------------------------------------------
        # Step 7: Return result
        # ------------------------------------------------------------------
        return IngestionResult(
            status="ready",
            error_message=None,
            chunk_count=len(chunks),
            failed_pages=failed_pages,
            doc_id=doc_id,
            filename=filename,
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

# Import here (after class definition) to avoid circular imports at module load
from app.services.document_store import document_store as _document_store  # noqa: E402

ingestion_pipeline = IngestionPipeline(document_store=_document_store)
