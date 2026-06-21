"""Consulta rastreamentos dos Correios usando uma sessao HTTP."""

from __future__ import annotations

import asyncio
import logging
import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from urllib.parse import urljoin
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from .exceptions import (
    CaptchaRetriesExhaustedError,
    CorreiosUnavailableError,
    InvalidTrackingCodeError,
    TrackingLimitExceededError,
    TrackingNotFoundError,
    TrackingScraperError,
    UnsupportedDocumentError,
)
from .models import TrackingEvent, TrackingResponse, TrackingResult
from solver.paddle_ocr import PaddleCaptchaOcr


logger = logging.getLogger("tracking_automatic.bot")
DOCUMENT_LENGTHS = {11, 14}
MAX_TRACKING_CODES = 20
TRACKING_CODE_PATTERN = re.compile(r"^[A-Z]{2}\d{9}[A-Z]{2}$")


def normalize_tracking_code(tracking_code: str) -> str:
    return "".join(character for character in tracking_code if character.isalnum()).upper()


def is_cpf_or_cnpj(value: str) -> bool:
    compact_value = "".join(value.split())
    digits = "".join(character for character in compact_value if character.isdigit())
    contains_only_document_characters = all(
        character.isdigit() or character in "./-" for character in compact_value
    )
    return contains_only_document_characters and len(digits) in DOCUMENT_LENGTHS


def parse_tracking_codes(value: str) -> tuple[str, ...]:
    raw_codes = value.split(",")
    normalized_codes = tuple(
        "".join(code.split()).upper() for code in raw_codes
    )

    if not normalized_codes or any(not code for code in normalized_codes):
        raise InvalidTrackingCodeError("Informe ao menos um código de rastreamento válido")
    if len(normalized_codes) > MAX_TRACKING_CODES:
        raise TrackingLimitExceededError(
            f"Informe no máximo {MAX_TRACKING_CODES} códigos de rastreamento por consulta"
        )
    if any(is_cpf_or_cnpj(code) for code in raw_codes):
        raise UnsupportedDocumentError(
            "Não é possível consultar com CPF ou CNPJ. "
            "Informe apenas códigos de rastreamento."
        )
    if any(not TRACKING_CODE_PATTERN.fullmatch(code) for code in normalized_codes):
        raise InvalidTrackingCodeError(
            "Informe códigos de rastreamento válidos separados por vírgula"
        )
    if len(set(normalized_codes)) != len(normalized_codes):
        raise InvalidTrackingCodeError("Não repita códigos na mesma consulta")

    return normalized_codes


def format_address(address: dict[str, Any]) -> str:
    city = address.get("cidade")
    state = address.get("uf")
    city_state = " - ".join(value for value in (city, state) if value)
    return ", ".join(
        value
        for value in (
            address.get("logradouro"),
            address.get("numero"),
            address.get("bairro"),
            city_state,
        )
        if value
    )


def format_unit(unit: dict[str, Any] | None, include_type: bool = True) -> str:
    if not unit:
        return ""

    address = unit.get("endereco") or {}
    location = format_address(address)
    unit_type = unit.get("tipo") if include_type else ""
    return ", ".join(value for value in (unit_type, location) if value)


def build_event_details(event: dict[str, Any]) -> tuple[str, ...]:
    code = event.get("codigo")
    origin = format_unit(event.get("unidade"), include_type=code not in {"LDI", "PO"})
    destination = format_unit(event.get("unidadeDestino"))
    details: list[str] = []

    if origin:
        details.append(f"Pela {origin}" if code == "BDI" else origin)
    if destination:
        details.append(f"Para {destination}")
    if event.get("detalhe"):
        details.append(event["detalhe"])

    return tuple(details)


def parse_event(event: dict[str, Any]) -> TrackingEvent:
    date_data = event.get("dtHrCriado") or {}
    date_value = date_data.get("date")
    if not date_value:
        raise ValueError("Evento dos Correios sem data")

    timezone = ZoneInfo(date_data.get("timezone") or "America/Sao_Paulo")
    occurred_at = datetime.fromisoformat(date_value).replace(tzinfo=timezone)
    return TrackingEvent(
        description=event.get("descricao") or event.get("descricaoFrontEnd") or "",
        details=build_event_details(event),
        occurred_at=occurred_at,
    )


def parse_tracking_result(payload: dict[str, Any]) -> TrackingResult:
    events = tuple(parse_event(event) for event in payload.get("eventos") or [])
    if not events:
        raise CorreiosUnavailableError("A consulta não retornou eventos de rastreamento")

    postal_type = payload.get("tipoPostal") or {}
    return TrackingResult(
        tracking_code=payload.get("codObjeto") or "",
        service=postal_type.get("categoria") or postal_type.get("descricao") or "",
        current_status=events[0].description,
        events=events,
    )


def parse_multiple_tracking_results(
    payload: dict[str, Any],
    requested_codes: tuple[str, ...],
) -> tuple[TrackingResult, ...]:
    objects_by_code: dict[str, dict[str, Any]] = {}

    for group in payload.values():
        if not isinstance(group, list):
            continue
        for item in group:
            if not isinstance(item, dict):
                continue
            tracking_object = item.get("objeto")
            if not isinstance(tracking_object, dict):
                continue
            tracking_code = normalize_tracking_code(
                str(tracking_object.get("codObjeto") or "")
            )
            if tracking_code:
                objects_by_code[tracking_code] = tracking_object

    missing_codes = [code for code in requested_codes if code not in objects_by_code]
    if missing_codes:
        raise TrackingNotFoundError(
            "Um ou mais objetos não foram encontrados"
        )

    return tuple(
        parse_tracking_result(objects_by_code[code]) for code in requested_codes
    )


async def recognize_captcha(
    client: httpx.AsyncClient,
    captcha_url: str,
    recognizer: PaddleCaptchaOcr,
) -> str:
    response = await client.get(captcha_url, params={"_": uuid4().hex})
    response.raise_for_status()

    with TemporaryDirectory(prefix="tracking-captcha-") as temp_dir:
        captcha_path = Path(temp_dir) / "captcha.png"
        captcha_path.write_bytes(response.content)
        ocr_result = await asyncio.to_thread(recognizer.recognize, captcha_path)

    captcha_text = "".join(character for character in ocr_result.text if character.isalnum())
    return captcha_text


def raise_response_error(payload: dict[str, Any]) -> None:
    message = payload.get("mensagem") or "Resposta de erro não identificada dos Correios"
    normalized_message = "".join(
        character
        for character in unicodedata.normalize("NFD", message.lower())
        if unicodedata.category(character) != "Mn"
    )
    if "objeto" in normalized_message and (
        "invalido" in normalized_message or "nao esta valido" in normalized_message
    ):
        raise InvalidTrackingCodeError(message)
    if "objeto nao encontrado" in normalized_message:
        raise TrackingNotFoundError(message)
    raise CorreiosUnavailableError(message)


async def track_package(
    tracking_code: str,
    recognizer: PaddleCaptchaOcr | None = None,
) -> TrackingResponse:
    """Consulta ate vinte objetos e retorna seus historicos estruturados."""
    request_id = uuid4().hex[:8]
    started_at = time.perf_counter()
    logger.info("tracking_started request_id=%s", request_id)

    tracking_url = "https://rastreamento.correios.com.br/app/index.php"
    invalid_captcha_message = "Captcha inválido"
    max_captcha_attempts = 3
    request_timeout_seconds = 30
    http_headers = {
        "Accept-Language": "pt-BR,pt;q=0.9",
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64; rv:146.0) "
            "Gecko/20100101 Firefox/146.0"
        ),
    }

    try:
        tracking_codes = parse_tracking_codes(tracking_code)
        is_multiple = len(tracking_codes) > 1
        recognizer = recognizer or await asyncio.to_thread(PaddleCaptchaOcr)
        async with httpx.AsyncClient(
            headers=http_headers,
            follow_redirects=True,
            timeout=request_timeout_seconds,
        ) as client:
            index_response = await client.get(tracking_url)
            index_response.raise_for_status()
            captcha_element = BeautifulSoup(index_response.text, "html.parser").select_one(
                "#captcha_image"
            )
            if captcha_element is None or not captcha_element.get("src"):
                raise CorreiosUnavailableError("CAPTCHA não encontrado na página dos Correios")

            captcha_url = urljoin(str(index_response.url), str(captcha_element["src"]))
            result_url = urljoin(
                str(index_response.url),
                "rastroMulti.php" if is_multiple else "resultado.php",
            )

            for attempt in range(1, max_captcha_attempts + 1):
                captcha_text = await recognize_captcha(client, captcha_url, recognizer)
                if not captcha_text:
                    logger.warning(
                        "captcha_recognition_empty request_id=%s attempt=%d max_attempts=%d",
                        request_id,
                        attempt,
                        max_captcha_attempts,
                    )
                    continue
                request_params = {
                    "objeto": "".join(tracking_codes),
                    "captcha": captcha_text,
                }
                if not is_multiple:
                    request_params["mqs"] = "S"

                result_response = await client.get(result_url, params=request_params)
                result_response.raise_for_status()
                payload = result_response.json()

                if not isinstance(payload, dict):
                    raise CorreiosUnavailableError(
                        "Os Correios retornaram uma resposta em formato inesperado"
                    )

                if payload.get("mensagem") == invalid_captcha_message:
                    logger.warning(
                        "captcha_rejected request_id=%s attempt=%d max_attempts=%d",
                        request_id,
                        attempt,
                        max_captcha_attempts,
                    )
                    continue
                if payload.get("erro"):
                    raise_response_error(payload)

                results = (
                    parse_multiple_tracking_results(payload, tracking_codes)
                    if is_multiple
                    else (parse_tracking_result(payload),)
                )
                response = TrackingResponse(results=results)
                logger.info(
                    "tracking_completed request_id=%s objects=%d events=%d duration_seconds=%.2f",
                    request_id,
                    len(results),
                    sum(len(result.events) for result in results),
                    time.perf_counter() - started_at,
                )
                return response

    except TrackingScraperError as error:
        logger.warning(
            "tracking_failed request_id=%s error=%s reason=%r duration_seconds=%.2f",
            request_id,
            error.error_code,
            error.message,
            time.perf_counter() - started_at,
        )
        raise
    except (httpx.HTTPError, ValueError) as error:
        logger.exception(
            "tracking_failed request_id=%s error=CORREIOS_UNAVAILABLE duration_seconds=%.2f",
            request_id,
            time.perf_counter() - started_at,
        )
        raise CorreiosUnavailableError(
            "Não foi possível concluir a comunicação com o site dos Correios"
        ) from error
    except Exception:
        logger.exception(
            "tracking_failed request_id=%s error=UNEXPECTED duration_seconds=%.2f",
            request_id,
            time.perf_counter() - started_at,
        )
        raise

    logger.warning(
        "tracking_failed request_id=%s error=CAPTCHA_RETRIES_EXHAUSTED duration_seconds=%.2f",
        request_id,
        time.perf_counter() - started_at,
    )
    raise CaptchaRetriesExhaustedError(
        f"Captcha inválido após {max_captcha_attempts} tentativas"
    )


if __name__ == "__main__":
    raise SystemExit(
        "Este arquivo não deve ser executado diretamente. Use a API ou chame track_package() com um código válido."
    )
