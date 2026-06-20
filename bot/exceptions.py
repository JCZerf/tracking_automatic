"""Erros de dominio produzidos pela consulta aos Correios."""

from __future__ import annotations

from typing import Any


class TrackingScraperError(Exception):
    error_code = "TRACKING_ERROR"
    status_code = 502

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.error_code, "message": self.message}


class InvalidTrackingCodeError(TrackingScraperError):
    error_code = "INVALID_TRACKING_CODE"
    status_code = 422


class TrackingNotFoundError(TrackingScraperError):
    error_code = "TRACKING_NOT_FOUND"
    status_code = 404


class CaptchaRetriesExhaustedError(TrackingScraperError):
    error_code = "CAPTCHA_RETRIES_EXHAUSTED"


class CorreiosUnavailableError(TrackingScraperError):
    error_code = "CORREIOS_UNAVAILABLE"
