"""Orquestracao das consultas de rastreamento."""

import asyncio

from bot.models import TrackingResult
from bot.scrapper import track_package
from solver.paddle_ocr import PaddleCaptchaOcr


class TrackingService:
    """Serializa consultas que compartilham a mesma instancia de OCR."""

    def __init__(self, recognizer: PaddleCaptchaOcr) -> None:
        self._recognizer = recognizer
        self._lock = asyncio.Lock()

    async def track(self, tracking_code: str) -> TrackingResult:
        async with self._lock:
            return await track_package(tracking_code, self._recognizer)
