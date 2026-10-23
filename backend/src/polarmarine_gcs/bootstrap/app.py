from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.responses import Response
from starlette.staticfiles import StaticFiles

from polarmarine_gcs.application.ports.drivers import DriverGateway
from polarmarine_gcs.bootstrap.container import Container
from polarmarine_gcs.bootstrap.settings import Settings
from polarmarine_gcs.bootstrap.static_files import SpaStaticFiles
from polarmarine_gcs.domain.common import (
    ConflictError,
    DomainError,
    NotFoundError,
    UnavailableError,
    ValidationError,
)
from polarmarine_gcs.interfaces.http.router import api_router

LOGGER = logging.getLogger(__name__)


def create_app(
    *, settings: Settings | None = None, drivers: DriverGateway | None = None
) -> FastAPI:
    resolved_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        container = Container(resolved_settings, drivers=drivers)
        application.state.container = container
        await container.start()
        try:
            yield
        finally:
            await container.stop()

    application = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        lifespan=lifespan,
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
        redoc_url=None,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "X-Request-Id"],
    )

    @application.middleware("http")
    async def request_id_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-Id") or str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response

    @application.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        status_code = 400
        if isinstance(exc, NotFoundError):
            status_code = 404
        elif isinstance(exc, ConflictError):
            status_code = 409
        elif isinstance(exc, ValidationError):
            status_code = 422
        elif isinstance(exc, UnavailableError):
            status_code = 503
        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                    "requestId": getattr(request.state, "request_id", str(uuid4())),
                }
            },
        )

    application.include_router(api_router, prefix="/api/v1")
    if resolved_settings.offline_map_root and resolved_settings.offline_map_root.is_dir():
        application.mount(
            "/offline-maps",
            StaticFiles(
                directory=str(resolved_settings.offline_map_root),
                follow_symlink=False,
            ),
            name="offline-maps",
        )
    if (
        resolved_settings.serve_frontend
        and resolved_settings.frontend_dist.is_dir()
        and (resolved_settings.frontend_dist / "index.html").is_file()
    ):
        application.mount("/", SpaStaticFiles(resolved_settings.frontend_dist), name="frontend")
    return application


app = create_app()
