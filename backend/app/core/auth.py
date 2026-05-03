"""
Authentication and authorization middleware for LawChain-AI PDF Chatbot.

Provides JWT verification and session ownership checks.
"""

from __future__ import annotations

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import settings
from app.models.models import UserIdentity

_bearer_scheme = HTTPBearer()


class AuthMiddleware:
    """Handles JWT authentication and session-level authorization."""

    def authenticate(self, token: str) -> UserIdentity:
        """Decode and verify a JWT, returning the authenticated UserIdentity.

        Args:
            token: A raw JWT string (without the 'Bearer ' prefix).

        Returns:
            A UserIdentity populated from the token claims.

        Raises:
            HTTPException (401): If the token is missing, expired, or malformed.
        """
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

        if not token:
            raise credentials_exception

        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
            )
        except JWTError:
            # Covers expired tokens, invalid signatures, and malformed JWTs.
            # The token value is intentionally never logged.
            raise credentials_exception

        user_id: str | None = payload.get("sub")
        email: str | None = payload.get("email")
        roles: list[str] = payload.get("roles", [])

        if user_id is None or email is None:
            raise credentials_exception

        return UserIdentity(user_id=user_id, email=email, roles=roles)

    def authorize_session(
        self,
        user_id: str,
        session_id: str,
        session_registry: dict,
    ) -> bool:
        """Check that the given user owns the given session.

        Args:
            user_id: The ID of the authenticated user.
            session_id: The session to check ownership of.
            session_registry: A mapping of session_id → user_id.

        Returns:
            True if the user owns the session, False otherwise.
        """
        return session_registry.get(session_id) == user_id


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(_bearer_scheme),
) -> UserIdentity:
    """FastAPI dependency that extracts and validates the Bearer token.

    Args:
        credentials: Injected by FastAPI from the Authorization header.

    Returns:
        The authenticated UserIdentity.

    Raises:
        HTTPException (401): If the Authorization header is missing or the
            token is invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthMiddleware().authenticate(credentials.credentials)
