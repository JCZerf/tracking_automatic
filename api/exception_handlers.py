"""Conversao de erros de dominio em respostas HTTP."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from bot.exceptions import TrackingScraperError
from bot.models import ErrorResponse


async def tracking_error_handler(
    _request: Request,
    error: TrackingScraperError,
) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content=ErrorResponse(**error.as_dict()).model_dump(),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.exception_handler(TrackingScraperError)(tracking_error_handler)
