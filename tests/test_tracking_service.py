from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from api.services.tracking import TrackingService
from bot.exceptions import CorreiosUnavailableError
from bot.models import TrackingResponse, TrackingResult


def build_response(code: str = "TJ481246775BR") -> TrackingResponse:
    return TrackingResponse(
        results=(
            TrackingResult(
                tracking_code=code,
                service="SEDEX",
                current_status="Objeto entregue",
                events=(),
            ),
        )
    )


class TrackingServiceCacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_cached_response_for_equivalent_query(self) -> None:
        expected_response = build_response()
        service = TrackingService(object(), cache_ttl_seconds=300)

        with patch(
            "api.services.tracking.track_package",
            new=AsyncMock(return_value=expected_response),
        ) as track_package:
            first = await service.track("TJ 481 246 775 BR")
            second = await service.track("tj481246775br")

        self.assertIs(first, expected_response)
        self.assertIs(second, expected_response)
        track_package.assert_awaited_once()

    async def test_refreshes_expired_entry(self) -> None:
        first_response = build_response()
        second_response = build_response()
        service = TrackingService(object(), cache_ttl_seconds=300)

        with (
            patch(
                "api.services.tracking.track_package",
                new=AsyncMock(side_effect=[first_response, second_response]),
            ) as track_package,
            patch(
                "api.services.tracking.time.monotonic",
                side_effect=[100.0, 401.0, 401.0],
            ),
        ):
            await service.track("TJ481246775BR")
            refreshed = await service.track("TJ481246775BR")

        self.assertIs(refreshed, second_response)
        self.assertEqual(track_package.await_count, 2)

    async def test_does_not_cache_errors(self) -> None:
        expected_response = build_response()
        service = TrackingService(object(), cache_ttl_seconds=300)

        with patch(
            "api.services.tracking.track_package",
            new=AsyncMock(
                side_effect=[
                    CorreiosUnavailableError("Falha externa"),
                    expected_response,
                ]
            ),
        ) as track_package:
            with self.assertRaises(CorreiosUnavailableError):
                await service.track("TJ481246775BR")
            response = await service.track("TJ481246775BR")

        self.assertIs(response, expected_response)
        self.assertEqual(track_package.await_count, 2)


if __name__ == "__main__":
    unittest.main()
