"""Modelos de resposta do rastreamento."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TrackingEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    description: str
    details: tuple[str, ...]
    occurred_at: datetime


class CaptchaValidationArtifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    media_type: str
    image_base64: str
    recognized_text: str
    confidence: float


class TrackingResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    tracking_code: str
    service: str
    current_status: str
    events: tuple[TrackingEvent, ...]
    validation_artifact: CaptchaValidationArtifact
