"""Audit log -- Responsible AI requirement.

Every tool call and every LLM call writes a row. Summaries only: never the raw
prompt, never PII. See docs/ARCHITECTURE.md section 8.
"""

from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base, IdMixin, TimestampMixin


class AuditLog(Base, IdMixin, TimestampMixin):
    __tablename__ = "audit_logs"

    user_id: Mapped[str | None] = mapped_column(String(36), index=True)
    session_id: Mapped[str | None] = mapped_column(String(36), index=True)

    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tool: Mapped[str | None] = mapped_column(String(64))

    input_summary: Mapped[str] = mapped_column(Text, default="")
    output_summary: Mapped[str] = mapped_column(Text, default="")

    model_version: Mapped[str | None] = mapped_column(String(64))
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(24), default="ok", index=True)
