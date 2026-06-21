"""Orquestracao das consultas de rastreamento."""

import asyncio
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass

from bot.models import TrackingResponse
from bot.scrapper import track_package
from solver.paddle_ocr import PaddleCaptchaOcr


logger = logging.getLogger("tracking_automatic.cache")


@dataclass(frozen=True, slots=True)
class CacheEntry:
    response: TrackingResponse
    expires_at: float


class TrackingService:
    """Serializa consultas que compartilham a mesma instancia de OCR."""

    def __init__(
        self,
        recognizer: PaddleCaptchaOcr,
        cache_ttl_seconds: int = 300,
        cache_max_entries: int = 100,
    ) -> None:
        self._recognizer = recognizer
        self._lock = asyncio.Lock()
        self._cache_ttl_seconds = max(0, cache_ttl_seconds)
        self._cache_max_entries = max(1, cache_max_entries)
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()

    async def track(self, tracking_code: str) -> TrackingResponse:
        cache_key = self._build_cache_key(tracking_code)
        cached_response = self._get_cached(cache_key)
        if cached_response is not None:
            logger.info("tracking_cache_hit objects=%d", len(cached_response.results))
            return cached_response

        async with self._lock:
            cached_response = self._get_cached(cache_key)
            if cached_response is not None:
                logger.info(
                    "tracking_cache_hit_after_wait objects=%d",
                    len(cached_response.results),
                )
                return cached_response

            response = await track_package(tracking_code, self._recognizer)
            self._store(cache_key, response)
            return response

    @staticmethod
    def _build_cache_key(tracking_code: str) -> str:
        return ",".join(
            "".join(code.split()).upper() for code in tracking_code.split(",")
        )

    def _get_cached(self, cache_key: str) -> TrackingResponse | None:
        if self._cache_ttl_seconds == 0:
            return None

        entry = self._cache.get(cache_key)
        if entry is None:
            return None
        if entry.expires_at <= time.monotonic():
            del self._cache[cache_key]
            return None

        self._cache.move_to_end(cache_key)
        return entry.response

    def _store(self, cache_key: str, response: TrackingResponse) -> None:
        if self._cache_ttl_seconds == 0:
            return

        now = time.monotonic()
        expired_keys = [
            key for key, entry in self._cache.items() if entry.expires_at <= now
        ]
        for key in expired_keys:
            del self._cache[key]

        self._cache[cache_key] = CacheEntry(
            response=response,
            expires_at=now + self._cache_ttl_seconds,
        )
        self._cache.move_to_end(cache_key)

        while len(self._cache) > self._cache_max_entries:
            self._cache.popitem(last=False)
