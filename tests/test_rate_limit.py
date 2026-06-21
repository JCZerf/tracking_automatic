from __future__ import annotations

import unittest
from unittest.mock import patch

from api.exceptions import RateLimitExceededError
from api.rate_limit import InMemoryRateLimiter


class InMemoryRateLimiterTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_request_after_limit(self) -> None:
        with patch(
            "api.rate_limit.time.monotonic",
            side_effect=[0.0, 0.0, 1.0, 2.0],
        ):
            limiter = InMemoryRateLimiter(max_requests=2, window_seconds=60)
            await limiter.check("client")
            await limiter.check("client")

            with self.assertRaises(RateLimitExceededError) as context:
                await limiter.check("client")

        self.assertEqual(context.exception.retry_after_seconds, 58)

    async def test_zero_limit_disables_rate_limiting(self) -> None:
        limiter = InMemoryRateLimiter(max_requests=0, window_seconds=60)

        for _ in range(100):
            await limiter.check("client")


if __name__ == "__main__":
    unittest.main()
