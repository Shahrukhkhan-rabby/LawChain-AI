"""
Session management service for LawChain-AI PDF Chatbot.

Sessions are persisted to a local shelve file so they survive backend
restarts. The FAISS vector index is in-memory only — documents must be
re-uploaded after a restart, but the session ID and ownership remain valid.
"""

from __future__ import annotations

import logging
import shelve
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from langchain.memory import ConversationBufferMemory

from app.models.models import AuthorizationError, NotFoundError, Session

logger = logging.getLogger(__name__)

# Persist session registry next to this file so it survives restarts.
_SHELF_PATH = str(Path(__file__).parent / "session_store")

# Sessions older than this are considered expired (default 24 hours).
_SESSION_TTL_HOURS = 24


class SessionManager:
    """Manages the lifecycle of chat sessions with restart-safe persistence."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._session_registry: dict[str, str] = {}
        self._load_persisted_sessions()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load_persisted_sessions(self) -> None:
        """Restore session registry from disk on startup."""
        try:
            with shelve.open(_SHELF_PATH) as db:
                for session_id, record in db.items():
                    # Expire sessions older than TTL
                    created_at: datetime = record.get("created_at", datetime.utcnow())
                    if datetime.utcnow() - created_at > timedelta(hours=_SESSION_TTL_HOURS):
                        continue
                    user_id: str = record["user_id"]
                    memory = ConversationBufferMemory(return_messages=True)
                    session = Session(
                        session_id=session_id,
                        user_id=user_id,
                        created_at=created_at,
                        document_ids=record.get("document_ids", []),
                        memory=memory,
                        is_active=True,
                    )
                    self._sessions[session_id] = session
                    self._session_registry[session_id] = user_id
            logger.info("Restored %d session(s) from disk.", len(self._sessions))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not load persisted sessions: %s", exc)

    def _persist_session(self, session: Session) -> None:
        """Write a session record to disk."""
        try:
            with shelve.open(_SHELF_PATH) as db:
                db[session.session_id] = {
                    "user_id": session.user_id,
                    "created_at": session.created_at,
                    "document_ids": session.document_ids,
                }
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not persist session %s: %s", session.session_id, exc)

    def _delete_persisted_session(self, session_id: str) -> None:
        """Remove a session record from disk."""
        try:
            with shelve.open(_SHELF_PATH) as db:
                db.pop(session_id, None)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not delete persisted session %s: %s", session_id, exc)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def create_session(self, user_id: str) -> Session:
        session_id = str(uuid.uuid4())
        memory = ConversationBufferMemory(return_messages=True)
        session = Session(
            session_id=session_id,
            user_id=user_id,
            created_at=datetime.utcnow(),
            document_ids=[],
            memory=memory,
            is_active=True,
        )
        self._sessions[session_id] = session
        self._session_registry[session_id] = user_id
        self._persist_session(session)
        return session

    def get_session(self, session_id: str, user_id: str) -> Session:
        session = self._sessions.get(session_id)
        if session is None:
            raise NotFoundError(f"Session '{session_id}' not found.")
        if session.user_id != user_id:
            raise AuthorizationError(
                f"User '{user_id}' does not own session '{session_id}'."
            )
        if not session.is_active:
            raise NotFoundError(f"Session '{session_id}' is no longer active.")
        return session

    def end_session(self, session_id: str, user_id: str) -> None:
        session = self.get_session(session_id, user_id)
        session.memory.clear()
        session.is_active = False
        self._sessions.pop(session_id, None)
        self._session_registry.pop(session_id, None)
        self._delete_persisted_session(session_id)
        logger.info(
            "Session ended",
            extra={"session_id": session_id, "user_id": user_id},
        )

    def active_session_count(self) -> int:
        return len(self._sessions)

    def get_session_registry(self) -> dict[str, str]:
        return self._session_registry


# Module-level singleton
session_manager = SessionManager()
