"""Rota de consulta de rastreamento."""

from typing import Annotated

from fastapi import APIRouter, Query, Request

from bot.models import ErrorResponse, TrackingResponse
from ..services.tracking import TrackingService


router = APIRouter(prefix="/tracking", tags=["tracking"])


@router.get(
    "",
    response_model=TrackingResponse,
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
            description="Até 20 códigos de objetos separados por vírgula.",
            examples=["TJ 481 246 775 BR, AP 073 539 958 BR"],
        ),
    ],
) -> TrackingResponse:
    service: TrackingService = request.app.state.tracking_service
    return await service.track(code)
