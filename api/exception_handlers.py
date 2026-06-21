"""Conversao de erros de dominio em respostas HTTP."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from bot.exceptions import TrackingScraperError
from bot.models import ErrorResponse


logger = logging.getLogger("tracking_automatic.api")


async def tracking_error_handler(
    _request: Request,
    error: TrackingScraperError,
) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content=ErrorResponse(**error.as_dict()).model_dump(),
    )


async def request_validation_error_handler(
    request: Request,
    _error: RequestValidationError,
) -> JSONResponse:
    logger.warning("request_validation_failed path=%s", request.url.path)
    error = ErrorResponse(
        code="INVALID_TRACKING_CODE",
        message="Informe um código de rastreamento válido.",
    )
    return JSONResponse(status_code=422, content=error.model_dump())


def register_exception_handlers(app: FastAPI) -> None:
    app.exception_handler(TrackingScraperError)(tracking_error_handler)
    app.exception_handler(RequestValidationError)(request_validation_error_handler)
