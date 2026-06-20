"""Rota de consulta de rastreamento."""

from typing import Annotated

from fastapi import APIRouter, Query, Request

from bot.models import ErrorResponse, TrackingResult
from ..services.tracking import TrackingService


router = APIRouter(prefix="/tracking", tags=["tracking"])


@router.get(
    "",
    response_model=TrackingResult,
    responses={
        404: {"model": ErrorResponse, "description": "Objeto não encontrado"},
        422: {"model": ErrorResponse, "description": "Código inválido"},
        502: {"model": ErrorResponse, "description": "Falha nos Correios ou no CAPTCHA"},
    },
)
async def get_tracking(
    request: Request,
    code: Annotated[
        str,
        Query(
            min_length=1,
            description="Código do objeto, com ou sem espaços.",
            examples=["TJ 481 246 775 BR"],
        ),
    ],
) -> TrackingResult:
    service: TrackingService = request.app.state.tracking_service
    return await service.track(code)
