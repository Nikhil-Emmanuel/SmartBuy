"""SmartBuy AI -- FastAPI application entrypoint.

Routers are thin. All business logic lives in app/services and app/agent.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.constants import ErrorCode
from app.core.errors import (
    AppError,
    app_error_handler,
    error_payload,
    unhandled_error_handler,
)
from app.db.database import init_db

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
log = logging.getLogger("smartbuy")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    log.info("Database ready (%s)", "sqlite" if settings.is_sqlite else "postgres")

    if not settings.llm_enabled:
        log.warning(
            "No GEMINI_API_KEY configured -- running in DETERMINISTIC FALLBACK mode. "
            "The full user journey still works; language will be templated."
        )

    # Warm the retrieval index so the first user request is not the slow one.
    try:
        from app.db.database import SessionLocal
        from app.services.product_search import get_search_service

        with SessionLocal() as db:
            size = get_search_service().warm(db)
        log.info("Search index warm: %d products", size)
    except Exception:  # pragma: no cover - startup must never hard-fail
        log.exception("Search index warm-up failed; it will build on first request")

    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "AI-Powered Goal-Based Shopping & Deal Discovery Agent. "
        "The LLM reads and writes language; every number is computed in Python."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time-Ms"] = f"{(time.perf_counter() - started) * 1000:.1f}"
    return response


app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError):
    """Reshape FastAPI's default 422 into our single error envelope."""
    return JSONResponse(
        status_code=422,
        content=error_payload(
            ErrorCode.VALIDATION_ERROR.value,
            "Request validation failed.",
            {"errors": exc.errors()[:10]},
        ),
    )


# --------------------------------------------------------------------------
# Routers -- registered in the build order from docs/API_CONTRACT.md
# --------------------------------------------------------------------------
from app.api import (
    admin,
    bundles,
    chat,
    comparison,
    demo,
    feedback,
    health,
    personalization,
    products,
    recommendations,
    requirements,
    suggestions,
    users,
)

app.include_router(health.router)
app.include_router(products.router)
app.include_router(products.offers_router)
app.include_router(chat.router)
app.include_router(requirements.router)
app.include_router(recommendations.router)
app.include_router(comparison.router)
app.include_router(bundles.router)
app.include_router(feedback.router)
app.include_router(personalization.router)
app.include_router(suggestions.router)
app.include_router(demo.router)
app.include_router(users.router)
app.include_router(admin.router)


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/api/health",
    }
