"""Health check. Public, no auth. Check this first on demo day."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import DbSession
from app.core.config import settings
from app.models.product import Product

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health(db: DbSession) -> dict:
    db_status = "ok"
    catalog_size = 0
    try:
        catalog_size = db.scalar(select(func.count()).select_from(Product)) or 0
    except Exception:
        db_status = "error"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "version": settings.APP_VERSION,
        "db": db_status,
        # "degraded" is honest: the app works, the language is templated.
        "llm": "ok" if settings.llm_enabled else "degraded",
        "llm_model": settings.GEMINI_MODEL if settings.llm_enabled else None,
        "catalog_size": catalog_size,
    }
