"""Shared HTTP request identifiers and safe public error responses."""

from collections.abc import Mapping
from typing import Any
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"


class ErrorDetail(BaseModel):
    """Stable machine code and safe human-readable error information."""

    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """Uniform public error envelope."""

    model_config = ConfigDict(frozen=True)

    error: ErrorDetail
    request_id: str


class ApiError(Exception):
    """Explicit public error raised by application code."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers


def resolve_request_id(candidate: str | None) -> str:
    """Preserve canonical UUIDs and replace all other values."""

    if candidate is not None:
        try:
            parsed = UUID(candidate)
        except ValueError, AttributeError:
            pass
        else:
            if str(parsed) == candidate.lower():
                return candidate

    return str(uuid4())


def get_request_id(request: Request) -> str:
    """Read the request identifier, with a safe fallback for early failures."""

    request_id = getattr(request.state, "request_id", None)
    return request_id if isinstance(request_id, str) else str(uuid4())


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a validated request ID to state and every HTTP response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = resolve_request_id(request.headers.get(REQUEST_ID_HEADER))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Build a safe error response without internal exception details."""

    request_id = get_request_id(request)
    response_headers = dict(headers or {})
    response_headers[REQUEST_ID_HEADER] = request_id
    body = ErrorResponse(
        error=ErrorDetail(code=code, message=message, details=details),
        request_id=request_id,
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(exclude_none=True),
        headers=response_headers,
    )


async def api_error_handler(request: Request, exception: ApiError) -> JSONResponse:
    """Render explicitly safe application errors."""

    return error_response(
        request,
        status_code=exception.status_code,
        code=exception.code,
        message=exception.message,
        details=exception.details,
        headers=exception.headers,
    )


async def validation_error_handler(
    request: Request,
    exception: RequestValidationError,
) -> JSONResponse:
    """Render validation errors without echoing rejected input values."""

    errors = [
        {
            "field": ".".join(str(part) for part in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        }
        for error in exception.errors()
    ]
    return error_response(
        request,
        status_code=422,
        code="validation_error",
        message="The request contains invalid fields.",
        details={"errors": errors},
    )


async def http_error_handler(
    request: Request,
    exception: StarletteHTTPException,
) -> JSONResponse:
    """Replace framework error details with the public envelope."""

    code = "unauthorized" if exception.status_code == 401 else "invalid_request"
    message = (
        "Authentication credentials are missing or invalid."
        if exception.status_code == 401
        else "The request could not be completed."
    )
    return error_response(
        request,
        status_code=exception.status_code,
        code=code,
        message=message,
        headers=exception.headers,
    )


async def unexpected_error_handler(request: Request, _: Exception) -> JSONResponse:
    """Prevent unexpected exception details from reaching clients."""

    return error_response(
        request,
        status_code=500,
        code="internal_error",
        message="An unexpected error occurred.",
    )


def register_error_handlers(application: FastAPI) -> None:
    """Install the application's uniform exception handlers."""

    application.add_exception_handler(ApiError, api_error_handler)
    application.add_exception_handler(RequestValidationError, validation_error_handler)
    application.add_exception_handler(StarletteHTTPException, http_error_handler)
    application.add_exception_handler(Exception, unexpected_error_handler)
