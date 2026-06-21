"""Configuracao da aplicacao FastAPI."""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from .exception_handlers import register_exception_handlers
from .routes.tracking import router as tracking_router
from .services.tracking import TrackingService
from solver.paddle_ocr import PaddleCaptchaOcr


DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://tracking-automatic-web.vercel.app",
)
LOGGER_NAME = "tracking_automatic"
logger = logging.getLogger(f"{LOGGER_NAME}.app")


def configure_logging() -> None:
    """Configura apenas os logs da aplicacao, sem alterar bibliotecas externas."""
    application_logger = logging.getLogger(LOGGER_NAME)
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    if not isinstance(level, int):
        level = logging.INFO

    if not application_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        application_logger.addHandler(handler)

    application_logger.setLevel(level)
    application_logger.propagate = False


def get_cors_origins() -> list[str]:
    configured_origins = os.getenv("CORS_ORIGINS")
    if not configured_origins:
        return list(DEFAULT_CORS_ORIGINS)

    return [
        origin.strip().rstrip("/")
        for origin in configured_origins.split(",")
        if origin.strip()
    ]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    started_at = time.perf_counter()
    logger.info("ocr_initialization_started")
    try:
        recognizer = await asyncio.to_thread(PaddleCaptchaOcr)
    except Exception:
        logger.exception("ocr_initialization_failed")
        raise

    app.state.tracking_service = TrackingService(recognizer)
    logger.info(
        "application_started ocr_initialization_seconds=%.2f",
        time.perf_counter() - started_at,
    )

    try:
        yield
    finally:
        logger.info("application_shutdown_started")
        del app.state.tracking_service
        logger.info("application_shutdown_completed")


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="Tracking API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_origins(),
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url=app.docs_url)

    app.include_router(tracking_router)
    register_exception_handlers(app)
    return app
