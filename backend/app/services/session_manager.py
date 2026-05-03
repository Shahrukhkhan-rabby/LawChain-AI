"""
Session management service for LawChain-AI PDF Chatbot.

Provides creation, retrieval, and termination of chat sessions.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from langchain.memory import ConversationBufferMemory

from app.models.models import AuthorizationError, NotFoundError, Session

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages the lifecycle of chat sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        # Maps session_id → user_id; consumed by AuthMiddleware.authorize_session
        self._session_registry: dict[str, str] = {}

    def create_session(self, user_id: str) -> Session:
        """Create a new session for the given user.

        Args:
            user_id: The ID of the authenticated user.

        Returns:
            A newly created, active Session.
        """
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
        return session

    def get_session(self, session_id: str, user_id: str) -> Session:
        """Retrieve a session, validating ownership and active status.

        Args:
            session_id: The UUID of the session to retrieve.
            user_id: The ID of the requesting user.

        Returns:
            The matching active Session.

        Raises:
            NotFoundError: If the session does not exist or is no longer active.
            AuthorizationError: If the session belongs to a different user.
        """
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
        """Terminate a session, clearing its memory and removing it from the registry.

        Args:
            session_id: The UUID of the session to end.
            user_id: The ID of the requesting user (must own the session).

        Raises:
            NotFoundError: If the session does not exist or is already inactive.
            AuthorizationError: If the session belongs to a different user.
        """
        session = self.get_session(session_id, user_id)
        session.memory.clear()
        session.is_active = False
        self._sessions.pop(session_id, None)
        self._session_registry.pop(session_id, None)
        logger.info(
            "Session ended",
            extra={"session_id": session_id, "user_id": user_id},
        )

    def active_session_count(self) -> int:
        """Return the number of currently active sessions.

        Returns:
            Count of sessions in the internal registry.
        """
        return len(self._sessions)

    def get_session_registry(self) -> dict[str, str]:
        """Return the session_id → user_id mapping.

        Used by AuthMiddleware.authorize_session to verify session ownership.

        Returns:
            A dict mapping session IDs to their owning user IDs.
        """
        return self._session_registry


# Module-level singleton
session_manager = SessionManager()
