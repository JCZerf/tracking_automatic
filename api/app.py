"""Configuracao da aplicacao FastAPI."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

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
        lifespan=lifespan,
    )
    app.include_router(tracking_router)
    register_exception_handlers(app)
    return app
