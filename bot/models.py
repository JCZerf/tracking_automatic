"""Modelos de resposta do rastreamento."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ErrorResponse(BaseModel):
    code: str
    message: str


class TrackingEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    description: str
    details: tuple[str, ...]
    occurred_at: datetime


class TrackingResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    tracking_code: str
    service: str
    current_status: str
    events: tuple[TrackingEvent, ...]


class TrackingResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    results: tuple[TrackingResult, ...]
