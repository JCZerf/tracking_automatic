"""Preenche o codigo de rastreamento no site dos Correios."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from .browser import FirefoxBrowser
from solver.paddle_ocr import PaddleCaptchaOcr


TRACKING_URL = "https://rastreamento.correios.com.br/app/index.php"
TRACKING_CODE = "TJ 481 246 775 BR"
TRACKING_INPUT_SELECTOR = "#objeto"
CAPTCHA_IMAGE_SELECTOR = "#captcha_image"
CAPTCHA_INPUT_SELECTOR = "#captcha"
SEARCH_BUTTON_SELECTOR = "#b-pesquisar"
RESULT_INSPECTION_DELAY_MS = 5_000


@dataclass(frozen=True, slots=True)
class FilledForm:
    tracking_code: str
    captcha_text: str
    captcha_confidence: float


async def fill_tracking_form(tracking_code: str) -> FilledForm:
    """Preenche o codigo de rastreamento e o CAPTCHA reconhecido."""
    recognizer = await asyncio.to_thread(PaddleCaptchaOcr)

    async with FirefoxBrowser() as browser:
        async with browser.new_page() as page:
            await page.goto(TRACKING_URL, wait_until="domcontentloaded")

            tracking_input = page.locator(TRACKING_INPUT_SELECTOR)
            await tracking_input.click()
            await tracking_input.press_sequentially(tracking_code, delay=50)

            with TemporaryDirectory(prefix="tracking-captcha-") as temp_dir:
                captcha_path = Path(temp_dir) / "captcha.png"
                await page.locator(CAPTCHA_IMAGE_SELECTOR).screenshot(path=captcha_path)
                ocr_result = await asyncio.to_thread(recognizer.recognize, captcha_path)

            captcha_text = "".join(character for character in ocr_result.text if character.isalnum())
            if not captcha_text:
                raise RuntimeError("PaddleOCR nao reconheceu o CAPTCHA")

            captcha_input = page.locator(CAPTCHA_INPUT_SELECTOR)
            await captcha_input.click()
            await captcha_input.fill(captcha_text)

            await page.locator(SEARCH_BUTTON_SELECTOR).click()
            await page.wait_for_timeout(RESULT_INSPECTION_DELAY_MS)

            return FilledForm(
                tracking_code=await tracking_input.input_value(),
                captcha_text=await captcha_input.input_value(),
                captcha_confidence=ocr_result.confidence,
            )


async def main() -> None:
    form = await fill_tracking_form(TRACKING_CODE)
    print(f"Codigo preenchido: {form.tracking_code}")
    print(
        f"CAPTCHA preenchido: {form.captcha_text} "
        f"(confianca: {form.captcha_confidence:.2%})"
    )


if __name__ == "__main__":
    asyncio.run(main())
