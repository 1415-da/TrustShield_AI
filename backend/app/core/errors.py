"""Structured error responses.

Every error body is {"error": {"code", "message", "details", "request_id"}}. Codes are stable, upper-case
identifiers clients can switch on; messages are safe to show to people (no stack traces, SQL, paths or secrets).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("trustshield.errors")


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class NotFound(AppError):
    def __init__(self, what: str = "Resource") -> None:
        super().__init__(404, "NOT_FOUND", f"{what} not found")


class Conflict(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(409, "CONFLICT", message)


class Forbidden(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(403, "AUTHORIZATION_DENIED", message)


class BadRequest(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(400, "BAD_REQUEST", message)


def _body(request: Request, code: str, message: str, details: object | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details if isinstance(details, list) else [],
                      "request_id": getattr(request.state, "request_id", None)}}


_STATUS_CODES = {400: "BAD_REQUEST", 401: "UNAUTHENTICATED", 403: "AUTHORIZATION_DENIED", 404: "NOT_FOUND",
                 405: "METHOD_NOT_ALLOWED", 409: "CONFLICT", 410: "GONE", 413: "PAYLOAD_TOO_LARGE", 422: "VALIDATION_ERROR",
                 429: "RATE_LIMITED"}
_DEFAULT_MESSAGES = {401: "Your session has expired. Please sign in again.",
                     403: "You do not have permission to perform this action.",
                     404: "This item could not be found.", 429: "Too many requests. Please try again shortly."}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_body(request, exc.code, exc.message))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, "HTTP_ERROR")
        headers = getattr(exc, "headers", None)
        detail = exc.detail if isinstance(exc.detail, str) and exc.detail and exc.detail != "Not Found" else None
        message = detail or _DEFAULT_MESSAGES.get(exc.status_code, "The request could not be completed.")
        return JSONResponse(status_code=exc.status_code, content=_body(request, code, message), headers=headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"field": ".".join(str(p) for p in e.get("loc", [])[1:]) or None, "message": e.get("msg")} for e in exc.errors()]
        return JSONResponse(status_code=422, content=_body(request, "VALIDATION_ERROR", "Some fields need attention.", details))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error", extra={"request_id": getattr(request.state, "request_id", None)})
        return JSONResponse(status_code=500, content=_body(request, "INTERNAL_ERROR", "Something went wrong. Please try again."))


__all__ = ["AppError", "NotFound", "Conflict", "Forbidden", "BadRequest", "HTTPException", "install_error_handlers"]
