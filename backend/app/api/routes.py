"""
Router for LawChain-AI PDF Chatbot API endpoints.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.core.config import settings
from app.models.models import (
    AuthorizationError,
    CitationError,
    NotFoundError,
    UserIdentity,
)
from app.services.document_store import document_store
from app.services.ingestion import ingestion_pipeline
from app.services.session_manager import session_manager

# qa_pipeline is imported lazily inside the endpoint to avoid triggering
# OpenAIEmbeddings instantiation at module load time.

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class QueryRequest(BaseModel):
    question: str
    session_id: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/upload")
async def upload_document(
    file: UploadFile,
    session_id: str = Form(...),
    user: UserIdentity = Depends(get_current_user),
) -> dict:
    """Upload a PDF document into a session.

    Validates session ownership, enforces the 20-document cap, checks file
    size (≤ 50 MB) and PDF magic bytes, then delegates to the ingestion
    pipeline.

    Returns:
        JSON body with ``doc_id``, ``filename``, ``status``, and ``chunk_count``.

    Raises:
        HTTPException (404): Session not found.
        HTTPException (403): Session belongs to a different user.
        HTTPException (422): Session document cap exceeded or ingestion error.
        HTTPException (413): File exceeds 50 MB.
        HTTPException (400): File is not a valid PDF.
    """
    # Step 1: Validate session ownership
    try:
        session = session_manager.get_session(session_id, user.user_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))

    # Step 2: Enforce 20-document cap
    if len(session.document_ids) >= settings.MAX_DOCS_PER_SESSION:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "SessionCapExceeded",
                "message": "Sessions are limited to 20 documents.",
            },
        )

    # Step 3: Read file in chunks to check size without loading all into memory
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    chunk_size = 64 * 1024  # 64 KB read buffer
    pdf_bytes = b""
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        pdf_bytes += chunk
        if len(pdf_bytes) > max_bytes:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={
                    "error": "FileTooLarge",
                    "message": f"File '{file.filename}' exceeds the {settings.MAX_FILE_SIZE_MB} MB limit.",
                },
            )

    # Step 4: Validate PDF magic bytes
    if pdf_bytes[:4] != b"%PDF":
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "InvalidFileType",
                "message": f"File '{file.filename}' is not a valid PDF.",
            },
        )

    # Step 5: Generate doc_id
    doc_id = str(uuid.uuid4())

    # Step 6: Run ingestion pipeline
    result = ingestion_pipeline.ingest_document(
        pdf_bytes, doc_id, session_id, file.filename
    )

    # Step 7: Handle ingestion error
    if result.status == "error":
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "IngestionError",
                "message": result.error_message,
            },
        )

    # Step 8: Append doc_id to session
    session.document_ids.append(doc_id)

    # Step 9: Return success response
    return {
        "doc_id": doc_id,
        "filename": file.filename,
        "status": "ready",
        "chunk_count": result.chunk_count,
    }


@router.post("/query")
async def query_document(
    request: QueryRequest,
    user: UserIdentity = Depends(get_current_user),
) -> dict:
    """Submit a natural-language question against uploaded documents.

    Returns:
        JSON body with ``answer``, ``citations``, ``session_id``, and ``question``.

    Raises:
        HTTPException (422): Question exceeds 2000 characters.
        HTTPException (401): Session not found.
        HTTPException (403): Session belongs to a different user.
    """
    # Step 1: Validate question length
    if len(request.question) > settings.MAX_QUESTION_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Question must not exceed {settings.MAX_QUESTION_LENGTH} characters.",
        )

    # Step 2–4: Call QA pipeline, handle errors
    from app.services.qa_pipeline import qa_pipeline  # lazy import
    try:
        result = qa_pipeline.answer(request.question, request.session_id, user.user_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except CitationError:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "error": "CitationUnverifiable",
                "message": "A verifiable answer could not be produced. Please rephrase your question.",
            },
        )

    # Step 5: Return serialized AnswerResult
    return {
        "answer": result.answer,
        "citations": [
            {
                "chunk_id": c.chunk_id,
                "filename": c.filename,
                "page_number": c.page_number,
                "chunk_text": c.chunk_text,
            }
            for c in result.citations
        ],
        "session_id": result.session_id,
        "question": result.question,
    }


@router.post("/session", status_code=201)
async def create_session(user: UserIdentity = Depends(get_current_user)) -> dict:
    """Create a new chat session for the authenticated user.

    Returns:
        JSON body with ``session_id`` and ``created_at`` (ISO-8601).

    Raises:
        HTTPException (401): If the request carries no valid Bearer token.
    """
    session = session_manager.create_session(user.user_id)
    return {
        "session_id": session.session_id,
        "created_at": session.created_at.isoformat(),
    }


@router.delete("/session/{session_id}", status_code=200)
async def end_session(
    session_id: str,
    user: UserIdentity = Depends(get_current_user),
) -> dict:
    """End and delete a chat session, removing all associated documents and memory.

    Returns:
        HTTP 204 No Content on success.

    Raises:
        HTTPException (404): Session not found.
        HTTPException (403): Session belongs to a different user.
    """
    try:
        document_store.delete_session(session_id)
        session_manager.end_session(session_id, user.user_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return {"status": "ended"}
