"""Aplicação FastAPI."""

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.ai.base import AIAuthError, AIError, AINotConfigured, AIRateLimited, AIUnavailable
from app.api.routers import applications, auth, dashboard, documents, jobs, profile, settings_routes, system
from app.config import get_settings
from app.errors import AppError
from app.logging_setup import configure_logging, request_id_var

log = logging.getLogger("http")

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "candidaturas"


def _error(status: int, code: str, message: str, details: dict | None = None) -> JSONResponse:
    body = {"error": {"code": code, "message": message, "request_id": request_id_var.get()}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status, content=body)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title="Candidaturas API",
        version=__version__,
        description="API do assistente self-hosted de candidaturas.",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["Content-Type", "X-Requested-With", "X-Request-ID"],
            expose_headers=["X-Request-ID"],
        )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = request.headers.get("x-request-id", "")
        if not (0 < len(rid) <= 64 and rid.replace("-", "").isalnum()):
            rid = uuid.uuid4().hex
        token = request_id_var.set(rid)
        started = time.monotonic()
        try:
            # Proteção CSRF: a sessão é um cookie, então toda escrita exige um header que um
            # formulário de outro site não consegue enviar sem passar pelo CORS.
            if (
                request.method in UNSAFE_METHODS
                and request.url.path.startswith("/api/")
                and request.headers.get(CSRF_HEADER) != CSRF_VALUE
            ):
                response = _error(403, "CSRF", "Requisição bloqueada (cabeçalho de proteção ausente).")
            else:
                response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "no-referrer"
            if not request.url.path.startswith("/api/docs") and not request.url.path.startswith("/api/documents"):
                response.headers["X-Frame-Options"] = "DENY"
            if request.url.path != "/api/health":
                log.info(
                    "http request",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "status": response.status_code,
                        "duration_ms": round((time.monotonic() - started) * 1000, 1),
                    },
                )
            return response
        finally:
            request_id_var.reset(token)

    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError):
        return _error(exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(AIError)
    async def ai_error(_: Request, exc: AIError):
        status = {AINotConfigured: 422, AIAuthError: 422, AIRateLimited: 429, AIUnavailable: 503}.get(type(exc), 502)
        return _error(status, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        fields = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
        return _error(422, "VALIDATION_ERROR", "Dados inválidos.", {"fields": fields})

    @app.exception_handler(Exception)
    async def unexpected(_: Request, exc: Exception):
        log.exception("erro inesperado", exc_info=exc)
        return _error(500, "INTERNAL_ERROR", "Erro inesperado. Veja os logs do servidor com o request_id.")

    for router in (
        system.router,
        auth.router,
        profile.router,
        jobs.router,
        documents.router,
        applications.router,
        settings_routes.router,
        dashboard.router,
    ):
        app.include_router(router, prefix="/api")
    return app


app = create_app()
