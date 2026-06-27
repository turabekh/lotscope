from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from lotscope.core.errors import (
    AuthError,
    ForbiddenError,
    LotScopeError,
    NotFoundError,
    UpstreamError,
    ValidationError,
)


class ErrorResponse(BaseModel):
    error: str
    detail: str


_STATUS_BY_EXCEPTION: dict[type[LotScopeError], int] = {
    NotFoundError: 404,
    ValidationError: 422,
    AuthError: 401,
    ForbiddenError: 403,
    UpstreamError: 502,
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


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(LotScopeError, _handle_lotscope_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
