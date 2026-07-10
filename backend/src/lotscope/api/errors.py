from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from lotscope.core.config import get_settings
from lotscope.core.errors import (
    AuthError,
    ConfigurationError,
    ConflictError,
    ForbiddenError,
    LotScopeError,
    NotFoundError,
    QuotaExceededError,
    UpstreamError,
    ValidationError,
)
from lotscope.core.logging import get_logger

_logger = get_logger("api.errors")


class ErrorResponse(BaseModel):
    error: str
    detail: str


_STATUS_BY_EXCEPTION: dict[type[LotScopeError], int] = {
    NotFoundError: 404,
    ValidationError: 422,
    AuthError: 401,
    ForbiddenError: 403,
    QuotaExceededError: 429,
    ConflictError: 409,
    UpstreamError: 502,
    ConfigurationError: 503,
}


def _status_for(exc: LotScopeError) -> int:
    for exc_type, status in _STATUS_BY_EXCEPTION.items():
        if isinstance(exc, exc_type):
            return status
    return 500


async def _handle_lotscope_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, LotScopeError)
    payload = ErrorResponse(error=type(exc).__name__, detail=exc.message)
    return JSONResponse(status_code=_status_for(exc), content=payload.model_dump())


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    payload = ErrorResponse(error="ValidationError", detail="Request validation failed.")
    return JSONResponse(status_code=422, content=payload.model_dump())


def _apply_cors_headers(request: Request, response: JSONResponse) -> None:
    origin = request.headers.get("origin")
    if origin and origin in get_settings().cors_origins:
        response.headers["access-control-allow-origin"] = origin
        response.headers["access-control-allow-credentials"] = "true"
        response.headers["vary"] = "Origin"


async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    _logger.error(
        "unhandled_error",
        path=request.url.path,
        error=str(exc),
        error_type=type(exc).__name__,
    )
    payload = ErrorResponse(error="InternalError", detail="An unexpected error occurred.")
    response = JSONResponse(status_code=500, content=payload.model_dump())
    _apply_cors_headers(request, response)
    return response


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(LotScopeError, _handle_lotscope_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(Exception, _handle_unexpected_error)
