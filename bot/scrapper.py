"""Consulta rastreamentos dos Correios usando uma sessao HTTP."""

from __future__ import annotations

import asyncio
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
    TrackingNotFoundError,
    TrackingScraperError,
)
from .models import TrackingEvent, TrackingResult
from solver.paddle_ocr import PaddleCaptchaOcr


TRACKING_URL = "https://rastreamento.correios.com.br/app/index.php"
TRACKING_CODE = "TJ 481 246 775 BR"
MAX_CAPTCHA_ATTEMPTS = 3
REQUEST_TIMEOUT_SECONDS = 30
INVALID_TRACKING_CODE_MESSAGE = "Código de objeto, CPF ou CNPJ informado não está válido"
INVALID_CAPTCHA_MESSAGE = "Captcha inválido"
HTTP_HEADERS = {
    "Accept-Language": "pt-BR,pt;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64; rv:146.0) "
        "Gecko/20100101 Firefox/146.0"
    ),
}


def normalize_tracking_code(tracking_code: str) -> str:
    return "".join(character for character in tracking_code if character.isalnum()).upper()


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
) -> TrackingResult:
    """Consulta um objeto e retorna seu historico estruturado."""
    normalized_code = normalize_tracking_code(tracking_code)
    if not normalized_code:
        raise InvalidTrackingCodeError(INVALID_TRACKING_CODE_MESSAGE)

    recognizer = recognizer or await asyncio.to_thread(PaddleCaptchaOcr)
    try:
        async with httpx.AsyncClient(
            headers=HTTP_HEADERS,
            follow_redirects=True,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as client:
            index_response = await client.get(TRACKING_URL)
            index_response.raise_for_status()
            captcha_element = BeautifulSoup(index_response.text, "html.parser").select_one(
                "#captcha_image"
            )
            if captcha_element is None or not captcha_element.get("src"):
                raise CorreiosUnavailableError("CAPTCHA não encontrado na página dos Correios")

            captcha_url = urljoin(str(index_response.url), str(captcha_element["src"]))
            result_url = urljoin(str(index_response.url), "resultado.php")

            for _attempt in range(MAX_CAPTCHA_ATTEMPTS):
                captcha_text = await recognize_captcha(client, captcha_url, recognizer)
                if not captcha_text:
                    continue
                result_response = await client.get(
                    result_url,
                    params={"objeto": normalized_code, "captcha": captcha_text, "mqs": "S"},
                )
                result_response.raise_for_status()
                payload = result_response.json()

                if payload.get("mensagem") == INVALID_CAPTCHA_MESSAGE:
                    continue
                if payload.get("erro"):
                    raise_response_error(payload)
                return parse_tracking_result(payload)

    except TrackingScraperError:
        raise
    except (httpx.HTTPError, ValueError) as error:
        raise CorreiosUnavailableError(
            "Não foi possível concluir a comunicação com o site dos Correios"
        ) from error

    raise CaptchaRetriesExhaustedError(
        f"Captcha inválido após {MAX_CAPTCHA_ATTEMPTS} tentativas"
    )


async def main() -> None:
    result = await track_package(TRACKING_CODE)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
