"""Rate limiting em memoria para a rota de rastreamento."""

import asyncio
import logging
import math
import time
from collections import deque

from fastapi import Request

from .exceptions import RateLimitExceededError


logger = logging.getLogger("tracking_automatic.rate_limit")


class InMemoryRateLimiter:
    """Aplica uma janela deslizante de requisicoes por cliente."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self._max_requests = max(0, max_requests)
        self._window_seconds = max(1, window_seconds)
        self._requests: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()
        self._last_cleanup = time.monotonic()

    async def check(self, client_id: str) -> None:
        if self._max_requests == 0:
            return

        now = time.monotonic()
        cutoff = now - self._window_seconds

        async with self._lock:
            self._cleanup(cutoff, now)
            requests = self._requests.setdefault(client_id, deque())
            while requests and requests[0] <= cutoff:
                requests.popleft()

            if len(requests) >= self._max_requests:
                retry_after = max(
                    1,
                    math.ceil(self._window_seconds - (now - requests[0])),
                )
                raise RateLimitExceededError(retry_after)

            requests.append(now)

    def _cleanup(self, cutoff: float, now: float) -> None:
        if now - self._last_cleanup < self._window_seconds:
            return

        expired_clients = [
            client_id
            for client_id, requests in self._requests.items()
            if not requests or requests[-1] <= cutoff
        ]
        for client_id in expired_clients:
            del self._requests[client_id]
        self._last_cleanup = now


def get_client_id(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", maxsplit=1)[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


async def enforce_rate_limit(request: Request) -> None:
    limiter: InMemoryRateLimiter = request.app.state.rate_limiter

    try:
        await limiter.check(get_client_id(request))
    except RateLimitExceededError as error:
        logger.warning(
            "rate_limit_exceeded path=%s retry_after_seconds=%d",
            request.url.path,
            error.retry_after_seconds,
        )
        raise
