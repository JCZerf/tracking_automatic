"""Configuracao da aplicacao FastAPI."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from .exception_handlers import register_exception_handlers
from .routes.tracking import router as tracking_router
from .services.tracking import TrackingService
from solver.paddle_ocr import PaddleCaptchaOcr


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

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url=app.docs_url)

    app.include_router(tracking_router)
    register_exception_handlers(app)
    return app
