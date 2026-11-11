"""Structured error responses: every error body is {"error": {"code", "message", "request_id"}}."""

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
        super().__init__(404, "not_found", f"{what} not found")


class Conflict(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(409, "conflict", message)


class Forbidden(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(403, "forbidden", message)


class BadRequest(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(400, "bad_request", message)


def _body(request: Request, code: str, message: str, details: object | None = None) -> dict:
    err: dict = {"code": code, "message": message, "request_id": getattr(request.state, "request_id", None)}
    if details is not None:
        err["details"] = details
    return {"error": err}


_STATUS_CODES = {401: "unauthorized", 403: "forbidden", 404: "not_found", 405: "method_not_allowed", 409: "conflict"}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_body(request, exc.code, exc.message))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, "http_error")
        headers = getattr(exc, "headers", None)
        return JSONResponse(status_code=exc.status_code, content=_body(request, code, str(exc.detail)), headers=headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"loc": list(e.get("loc", [])), "msg": e.get("msg")} for e in exc.errors()]
        return JSONResponse(status_code=422, content=_body(request, "validation_error", "Invalid request", details))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error", extra={"request_id": getattr(request.state, "request_id", None)})
        return JSONResponse(status_code=500, content=_body(request, "internal_error", "An unexpected error occurred"))


__all__ = ["AppError", "NotFound", "Conflict", "Forbidden", "BadRequest", "HTTPException", "install_error_handlers"]
