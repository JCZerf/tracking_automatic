"""Preenche o codigo de rastreamento no site dos Correios."""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime
from enum import StrEnum
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

from playwright.async_api import Locator, Page

from .browser import FirefoxBrowser
from .exceptions import (
    CaptchaRetriesExhaustedError,
    CorreiosUnavailableError,
    InvalidTrackingCodeError,
    TrackingNotFoundError,
)
from .models import CaptchaValidationArtifact, TrackingEvent, TrackingResult
from solver.paddle_ocr import PaddleCaptchaOcr


TRACKING_URL = "https://rastreamento.correios.com.br/app/index.php"
TRACKING_CODE = "TJ 481 246 775 BR"
TRACKING_INPUT_SELECTOR = "#objeto"
CAPTCHA_IMAGE_SELECTOR = "#captcha_image"
CAPTCHA_INPUT_SELECTOR = "#captcha"
SEARCH_BUTTON_SELECTOR = "#b-pesquisar"
FULL_RESULTS_SELECTOR = "#ver-rastro-unico"
EVENT_SELECTOR = f"{FULL_RESULTS_SELECTOR} .ship-steps > li.step"
RESULT_INSPECTION_DELAY_MS = 5_000
SUBMISSION_TIMEOUT_MS = 15_000
MAX_CAPTCHA_ATTEMPTS = 3
CORREIOS_TIMEZONE = ZoneInfo("America/Sao_Paulo")
CORREIOS_DATETIME_FORMAT = "%d/%m/%Y %H:%M"
INVALID_TRACKING_CODE_MESSAGE = "Código de objeto, CPF ou CNPJ informado não está válido"
TRACKING_NOT_FOUND_MESSAGE = "Objeto não encontrado na base de dados dos Correios"
INVALID_CAPTCHA_MESSAGE = "Captcha inválido"


class SubmissionOutcome(StrEnum):
    SUCCESS = "success"
    INVALID_TRACKING_CODE = "invalid_tracking_code"
    TRACKING_NOT_FOUND = "tracking_not_found"
    INVALID_CAPTCHA = "invalid_captcha"


def normalize_text(value: str) -> str:
    return " ".join(value.split())


async def read_element_text(element: Locator) -> str:
    text = await element.evaluate(
        """element => {
            const clone = element.cloneNode(true);
            clone.querySelectorAll('br').forEach(br => br.replaceWith(' '));
            return clone.textContent || '';
        }"""
    )
    return normalize_text(text)


async def extract_event(event: Locator) -> TrackingEvent:
    paragraphs = [
        text
        for paragraph in await event.locator(".step-content > p").all()
        if (text := await read_element_text(paragraph))
    ]
    if len(paragraphs) < 2:
        raise ValueError("Evento dos Correios sem descricao ou data")

    occurred_at = datetime.strptime(paragraphs[-1], CORREIOS_DATETIME_FORMAT).replace(
        tzinfo=CORREIOS_TIMEZONE
    )
    return TrackingEvent(
        description=paragraphs[0],
        details=tuple(paragraphs[1:-1]),
        occurred_at=occurred_at,
    )


async def extract_tracking_result(
    page: Page,
    tracking_code: str,
    validation_artifact: CaptchaValidationArtifact,
) -> TrackingResult:
    """Converte o HTML de resultado dos Correios em um modelo da API."""
    result = page.locator(FULL_RESULTS_SELECTOR)
    events_locator = page.locator(EVENT_SELECTOR)
    event_count = await events_locator.count()
    if event_count == 0:
        raise RuntimeError("A consulta nao retornou eventos de rastreamento")

    events = tuple(
        [await extract_event(events_locator.nth(index)) for index in range(event_count)]
    )
    service = normalize_text(
        await result.locator(".cabecalho-content .text-content").first.inner_text()
    )

    return TrackingResult(
        tracking_code="".join(tracking_code.split()).upper(),
        service=service,
        current_status=events[0].description,
        events=events,
        validation_artifact=validation_artifact,
    )


async def wait_for_submission_outcome(page: Page) -> SubmissionOutcome:
    """Aguarda o resultado ou uma das mensagens conhecidas do site."""
    locators = {
        SubmissionOutcome.SUCCESS: page.locator(EVENT_SELECTOR).first,
        SubmissionOutcome.INVALID_TRACKING_CODE: page.get_by_text(
            re.compile(re.escape(INVALID_TRACKING_CODE_MESSAGE), re.IGNORECASE)
        ).first,
        SubmissionOutcome.TRACKING_NOT_FOUND: page.get_by_text(
            re.compile(re.escape(TRACKING_NOT_FOUND_MESSAGE), re.IGNORECASE)
        ).first,
        SubmissionOutcome.INVALID_CAPTCHA: page.get_by_text(
            re.compile(re.escape(INVALID_CAPTCHA_MESSAGE), re.IGNORECASE)
        ).first,
    }
    tasks = {
        asyncio.create_task(
            locator.wait_for(
                state="attached" if outcome is SubmissionOutcome.SUCCESS else "visible",
                timeout=SUBMISSION_TIMEOUT_MS,
            )
        ): outcome
        for outcome, locator in locators.items()
    }

    done, pending = await asyncio.wait(
        tasks,
        timeout=SUBMISSION_TIMEOUT_MS / 1_000,
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)

    successful_tasks = [task for task in done if task.exception() is None]
    if not successful_tasks:
        raise CorreiosUnavailableError("Os Correios não responderam no tempo esperado")

    return tasks[successful_tasks[0]]


async def recognize_captcha(
    page: Page,
    recognizer: PaddleCaptchaOcr,
) -> CaptchaValidationArtifact:
    """Captura e reconhece o CAPTCHA exibido na pagina."""
    with TemporaryDirectory(prefix="tracking-captcha-") as temp_dir:
        captcha_path = Path(temp_dir) / "captcha.png"
        await page.locator(CAPTCHA_IMAGE_SELECTOR).screenshot(path=captcha_path)
        ocr_result = await asyncio.to_thread(recognizer.recognize, captcha_path)
        image_base64 = base64.b64encode(captcha_path.read_bytes()).decode("ascii")

    captcha_text = "".join(character for character in ocr_result.text if character.isalnum())
    if not captcha_text:
        raise CaptchaRetriesExhaustedError("PaddleOCR não reconheceu o CAPTCHA")

    return CaptchaValidationArtifact(
        media_type="image/png",
        image_base64=image_base64,
        recognized_text=captcha_text,
        confidence=ocr_result.confidence,
    )


def raise_for_outcome(outcome: SubmissionOutcome) -> None:
    if outcome is SubmissionOutcome.INVALID_TRACKING_CODE:
        raise InvalidTrackingCodeError(INVALID_TRACKING_CODE_MESSAGE)
    if outcome is SubmissionOutcome.TRACKING_NOT_FOUND:
        raise TrackingNotFoundError(TRACKING_NOT_FOUND_MESSAGE)


async def track_package(tracking_code: str) -> TrackingResult:
    """Consulta um objeto nos Correios e retorna seu historico estruturado."""
    recognizer = await asyncio.to_thread(PaddleCaptchaOcr)

    async with FirefoxBrowser() as browser:
        async with browser.new_page() as page:
            await page.goto(TRACKING_URL, wait_until="domcontentloaded")

            tracking_input = page.locator(TRACKING_INPUT_SELECTOR)
            await tracking_input.click()
            await tracking_input.press_sequentially(tracking_code, delay=50)

            captcha_input = page.locator(CAPTCHA_INPUT_SELECTOR)
            for attempt in range(1, MAX_CAPTCHA_ATTEMPTS + 1):
                validation_artifact = await recognize_captcha(page, recognizer)
                await captcha_input.fill(validation_artifact.recognized_text)

                outcome_task = asyncio.create_task(wait_for_submission_outcome(page))
                await asyncio.sleep(0)
                await page.locator(SEARCH_BUTTON_SELECTOR).click()
                await page.wait_for_timeout(RESULT_INSPECTION_DELAY_MS)
                outcome = await outcome_task

                if outcome is SubmissionOutcome.SUCCESS:
                    return await extract_tracking_result(
                        page,
                        tracking_code,
                        validation_artifact,
                    )

                raise_for_outcome(outcome)

            raise CaptchaRetriesExhaustedError(
                f"Captcha inválido após {MAX_CAPTCHA_ATTEMPTS} tentativas"
            )


async def main() -> None:
    result = await track_package(TRACKING_CODE)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
