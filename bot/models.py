"""Modelos de resposta do rastreamento."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


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

    status: Literal["success"] = "success"
    tracking_code: str
    service: str
    current_status: str
    events: tuple[TrackingEvent, ...]


class TrackingNotFoundResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["not_found"] = "not_found"
    tracking_code: str
    message: str


TrackingItem = Annotated[
    TrackingResult | TrackingNotFoundResult,
    Field(discriminator="status"),
]


class TrackingResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    results: tuple[TrackingItem, ...]
