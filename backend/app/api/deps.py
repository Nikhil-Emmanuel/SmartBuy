"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import Unauthorized
from app.db.database import get_db
from app.models.user import User, UserPreference

DbSession = Annotated[Session, Depends(get_db)]


def get_or_create_user(db: Session, session_id: str | None) -> User:
    """Resolve the anonymous user behind a session id (ADR-005: no auth).

    The session id doubles as the anonymous user id, which keeps preferences
    and feedback attached to a browser without asking anyone to sign up.
    """
    if session_id:
        user = db.get(User, session_id)
        if user:
            return user

    user = User(is_anonymous=True)
    if session_id:
        user.id = session_id
    db.add(user)
    db.flush()
    db.add(UserPreference(user_id=user.id))
    db.flush()
    return user


def current_user(
    db: DbSession,
    x_session_id: Annotated[str | None, Header(alias="X-Session-Id")] = None,
) -> User:
    return get_or_create_user(db, x_session_id)


CurrentUser = Annotated[User, Depends(current_user)]


def require_admin(
    x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
) -> None:
    if not x_admin_token or x_admin_token != settings.ADMIN_TOKEN:
        raise Unauthorized("Admin token missing or invalid.")


AdminOnly = Annotated[None, Depends(require_admin)]
