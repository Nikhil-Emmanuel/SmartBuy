"""Error types and the single error envelope defined in docs/API_CONTRACT.md.

    {"error": {"code": "...", "message": "...", "details": {}}}
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.constants import ErrorCode


class AppError(Exception):
    """Base for every expected failure. Unexpected ones become INTERNAL_ERROR."""

    status_code: int = 400
    code: ErrorCode = ErrorCode.INTERNAL_ERROR

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_response(self) -> JSONResponse:
        return JSONResponse(
            status_code=self.status_code,
            content={
                "error": {
                    "code": self.code.value,
                    "message": self.message,
                    "details": self.details,
                }
            },
        )


class NotFoundError(AppError):
    status_code = 404
    code = ErrorCode.INTERNAL_ERROR


class SessionNotFound(NotFoundError):
    code = ErrorCode.SESSION_NOT_FOUND


class PlanNotFound(NotFoundError):
    code = ErrorCode.PLAN_NOT_FOUND


class ProductNotFound(NotFoundError):
    code = ErrorCode.PRODUCT_NOT_FOUND


class RequirementNotFound(NotFoundError):
    code = ErrorCode.REQUIREMENT_NOT_FOUND


class ValidationError(AppError):
    status_code = 422
    code = ErrorCode.VALIDATION_ERROR


class NoProductsFound(AppError):
    status_code = 404
    code = ErrorCode.NO_PRODUCTS_FOUND


class BudgetInfeasible(AppError):
    """Raised only when we cannot return anything useful.

    The normal infeasible case is *not* an error: /api/bundle/optimize returns
    200 with infeasible=true plus an essentials-only bundle, because the user
    still needs to see something actionable.
    """

    status_code = 200
    code = ErrorCode.BUDGET_INFEASIBLE


class Unauthorized(AppError):
    status_code = 401
    code = ErrorCode.UNAUTHORIZED


class RateLimited(AppError):
    status_code = 429
    code = ErrorCode.RATE_LIMITED


class LLMUnavailable(AppError):
    """Raised inside the LLM layer and caught by the orchestrator, which falls
    back to deterministic handling. It must never reach the client on a chat
    turn -- the response carries degraded=true instead."""

    status_code = 503
    code = ErrorCode.LLM_UNAVAILABLE


def error_payload(code: str, message: str, details: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}}}


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return exc.to_response()


async def unhandled_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    import logging

    logging.getLogger("smartbuy").exception("Unhandled error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=error_payload(
            ErrorCode.INTERNAL_ERROR.value,
            "Something went wrong on our side. Please try again.",
        ),
    )
