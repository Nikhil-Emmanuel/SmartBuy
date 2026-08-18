"""Conversation session state.

The agent is stateful across turns and the chat must survive a page refresh
mid-demo, so state lives in the database rather than in memory.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import AgentState
from app.db.database import Base, IdMixin, TimestampMixin, utcnow

if TYPE_CHECKING:
    from app.models.plan import ShoppingPlan


class ChatSession(Base, IdMixin, TimestampMixin):
    __tablename__ = "sessions"

    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    state: Mapped[str] = mapped_column(String(24), default=AgentState.INTAKE, nullable=False)
    intent: Mapped[str | None] = mapped_column(String(32))

    # The full requirement profile. Shape is defined by schemas.agent.Slots.
    slots: Mapped[dict] = mapped_column(JSON, default=dict)

    # Enforces MAX_FOLLOWUP_QUESTIONS. A demo where the agent interrogates the
    # user for six turns is a failed demo.
    question_count: Mapped[int] = mapped_column(Integer, default=0)

    # Slots we inferred rather than asked for, surfaced in the sidebar so the
    # user can correct them: [{"slot", "value", "basis"}]
    assumptions: Mapped[list] = mapped_column(JSON, default=list)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    messages: Mapped[list[ConversationMessage]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.created_at",
    )
    plans: Mapped[list[ShoppingPlan]] = relationship(back_populates="session")


class ConversationMessage(Base, IdMixin, TimestampMixin):
    __tablename__ = "conversation_messages"

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Chips, degraded flag, slots collected on this turn, etc.
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    session: Mapped[ChatSession] = relationship(back_populates="messages")
