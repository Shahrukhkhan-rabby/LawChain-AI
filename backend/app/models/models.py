"""
Data models for LawChain-AI PDF Chatbot.

All domain dataclasses and custom exceptions are defined here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class OCRRequiredError(Exception):
    """Raised when a PDF contains only scanned images with no selectable text."""


class AuthorizationError(Exception):
    """Raised when a user attempts to access a resource they do not own."""


class NotFoundError(Exception):
    """Raised when a requested resource (session, document, etc.) does not exist."""


class CitationError(Exception):
    """Raised when the LLM response references a chunk ID not in the retrieved set."""


# ---------------------------------------------------------------------------
# Identity and session models
# ---------------------------------------------------------------------------


@dataclass
class UserIdentity:
    """Represents an authenticated user."""

    user_id: str          # UUID
    email: str
    roles: list[str]      # e.g. ["lawyer", "admin"]


@dataclass
class Session:
    """Represents an active chat session scoped to a set of documents."""

    session_id: str           # UUID
    user_id: str
    created_at: datetime
    document_ids: list[str]   # max 20 documents per session
    memory: Any               # ConversationBufferMemory instance
    is_active: bool


# ---------------------------------------------------------------------------
# Ingestion pipeline models
# ---------------------------------------------------------------------------


@dataclass
class PageText:
    """Text extracted from a single PDF page."""

    page_number: int          # 1-indexed
    text: str                 # extracted plain text; empty string if extraction failed
    extraction_failed: bool


@dataclass
class Chunk:
    """A fixed-size, overlapping segment of text from a document."""

    chunk_id: str             # UUID
    doc_id: str
    session_id: str
    filename: str
    page_number: int
    text: str
    token_count: int          # <= 1000


@dataclass
class EmbeddedChunk:
    """A Chunk paired with its vector embedding."""

    chunk: Chunk
    vector: list[float]       # 1536-dim for text-embedding-3-small


# ---------------------------------------------------------------------------
# QA pipeline models
# ---------------------------------------------------------------------------


@dataclass
class Citation:
    """A reference to the source document passage used in an answer."""

    chunk_id: str
    filename: str
    page_number: int
    chunk_text: str


@dataclass
class AnswerResult:
    """The result of a question-answering request."""

    answer: str
    citations: list[Citation]
    session_id: str
    question: str


# ---------------------------------------------------------------------------
# API response models
# ---------------------------------------------------------------------------


@dataclass
class IngestionResult:
    """Result returned by the ingestion pipeline after processing a document."""

    doc_id: str
    filename: str
    chunk_count: int
    failed_pages: list[int]
    status: Literal["ready", "error"]
    error_message: str | None


@dataclass
class UploadResponse:
    """HTTP response body for the POST /upload endpoint."""

    doc_id: str
    filename: str
    status: Literal["ready", "error"]
    chunk_count: int
    error_message: str | None
