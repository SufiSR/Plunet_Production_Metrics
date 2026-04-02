from __future__ import annotations

import logging
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from app.api.router import api_router
from app.database import SessionLocal
from app.scheduler import start_scheduler, stop_scheduler
from app.schemas.errors import ErrorCode, ErrorResponse
from app.services.config_service import load_runtime_config

logger = logging.getLogger(__name__)


def _session_secret() -> str:
    raw = os.getenv("DORA_SESSION_SECRET", "").strip()
    if len(raw) < 16:
        raise RuntimeError(
            "DORA_SESSION_SECRET is required (minimum 16 characters) for signed admin sessions"
        )
    return raw


def _https_only_session_cookie() -> bool:
    return (os.getenv("DORA_ENVIRONMENT") or "").strip().lower() == "production"


def _cors_config() -> tuple[list[str], bool]:
    raw = (os.getenv("DORA_CORS_ORIGINS") or "").strip()
    if not raw:
        return (["http://localhost:3000", "http://127.0.0.1:3000"], True)
    if raw == "*":
        return (["*"], False)
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return (parts, True)


def _http_error_message(detail: object) -> str:
    if isinstance(detail, str):
        return detail
    return str(detail)


def _configure_application_logging() -> None:
    """Attach a stderr handler for ``app.*`` so logs show in ``docker logs`` (no log files).

    Uvicorn's default dictConfig often leaves the root logger without a handler that
    receives third-party library loggers; setting level alone is not enough.
    """
    level_name = (os.getenv("DORA_LOG_LEVEL") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    app_logger = logging.getLogger("app")
    app_logger.setLevel(level)
    if not app_logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(level)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        )
        app_logger.addHandler(handler)
    app_logger.propagate = False


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    _configure_application_logging()
    with SessionLocal() as db:
        config = load_runtime_config(db=db).settings
    start_scheduler(config)
    try:
        yield
    finally:
        stop_scheduler()


def create_app() -> FastAPI:
    application = FastAPI(title="DORA Metrics Backend", lifespan=lifespan)
    origins, allow_credentials = _cors_config()
    application.add_middleware(
        SessionMiddleware,
        secret_key=_session_secret(),
        session_cookie="dora_session",
        max_age=14 * 24 * 60 * 60,
        same_site="lax",
        https_only=_https_only_session_cookie(),
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_credentials,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @application.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        code_map = {
            400: ErrorCode.BAD_REQUEST,
            401: ErrorCode.UNAUTHORIZED,
            403: ErrorCode.FORBIDDEN,
            404: ErrorCode.NOT_FOUND,
        }
        err = code_map.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
        if exc.status_code >= 500:
            err = ErrorCode.INTERNAL_ERROR
        body = ErrorResponse(
            error=err.value,
            message=_http_error_message(exc.detail),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=body.model_dump(mode="json"),
        )

    @application.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        msgs = exc.errors()
        if msgs:
            message = "; ".join(f"{m.get('loc')}: {m.get('msg')}" for m in msgs)
        else:
            message = "Invalid request"
        body = ErrorResponse(error=ErrorCode.BAD_REQUEST.value, message=message)
        return JSONResponse(status_code=400, content=body.model_dump(mode="json"))

    @application.exception_handler(ValueError)
    async def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
        body = ErrorResponse(error=ErrorCode.BAD_REQUEST.value, message=str(exc))
        return JSONResponse(status_code=400, content=body.model_dump(mode="json"))

    @application.exception_handler(Exception)
    async def unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error", exc_info=exc)
        body = ErrorResponse(error=ErrorCode.INTERNAL_ERROR.value, message="Internal server error")
        return JSONResponse(status_code=500, content=body.model_dump(mode="json"))

    application.include_router(api_router, prefix="/api")

    @application.get("/health")
    def legacy_health() -> dict[str, str]:
        """Backward-compatible liveness path; use GET /api/health for dependency status."""
        return {"status": "ok"}

    return application


app = create_app()
