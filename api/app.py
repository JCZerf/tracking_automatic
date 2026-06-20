"""Configuracao da aplicacao FastAPI."""

import asyncio
import os
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
    recognizer = await asyncio.to_thread(PaddleCaptchaOcr)
    app.state.tracking_service = TrackingService(recognizer)
    yield
    del app.state.tracking_service


def create_app() -> FastAPI:
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
