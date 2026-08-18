"""Audit trail for agent and LLM activity.

Responsible AI requirement (master prompt section 30): every tool call and
every model call is recorded with a redacted summary, latency and status. We
store summaries, never raw prompts and never PII.

Logging must never break a request -- every failure here is swallowed and
reported to the application log instead.

Owner: Member 6 (Responsible AI).
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager, suppress

from sqlalchemy.orm import Session

from app.guardrails.privacy import summarise_for_audit
from app.models.audit import AuditLog

log = logging.getLogger("smartbuy.audit")

STATUS_OK = "ok"
STATUS_FALLBACK = "fallback"
STATUS_BLOCKED = "blocked"
STATUS_ERROR = "error"


def record(db: Session | None, *, action: str, tool: str | None = None,
           session_id: str | None = None, user_id: str | None = None,
           input_summary: str = "", output_summary: str = "",
           model_version: str | None = None, latency_ms: int = 0,
           status: str = STATUS_OK) -> None:
    """Write one audit row. Never raises."""
    if db is None:
        return
    try:
        db.add(AuditLog(
            user_id=user_id,
            session_id=session_id,
            action=action[:64],
            tool=tool[:64] if tool else None,
            input_summary=summarise_for_audit(input_summary),
            output_summary=summarise_for_audit(output_summary),
            model_version=model_version[:64] if model_version else None,
            latency_ms=int(latency_ms),
            status=status[:24],
        ))
        db.flush()
    except Exception:
        log.exception("Failed to write audit row for action=%s", action)
        with suppress(Exception):
            db.rollback()


@contextmanager
def audited(db: Session | None, *, action: str, tool: str | None = None,
            session_id: str | None = None, user_id: str | None = None,
            input_summary: str = "", model_version: str | None = None):
    """Time a block and audit it, whatever the outcome.

    Usage:
        with audited(db, action="llm_call", tool="understand") as entry:
            result = provider.generate_json(...)
            entry["output_summary"] = "intent=GOAL_BASED_SHOPPING"
    """
    entry: dict = {"output_summary": "", "status": STATUS_OK}
    started = time.perf_counter()
    try:
        yield entry
    except Exception as exc:
        entry["status"] = STATUS_ERROR
        entry["output_summary"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        record(
            db,
            action=action,
            tool=tool,
            session_id=session_id,
            user_id=user_id,
            input_summary=input_summary,
            output_summary=str(entry.get("output_summary", "")),
            model_version=model_version,
            latency_ms=int((time.perf_counter() - started) * 1000),
            status=str(entry.get("status", STATUS_OK)),
        )
