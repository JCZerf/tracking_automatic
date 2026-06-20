"""Gerenciamento do navegador Firefox usado pelo bot."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)


@dataclass(frozen=True, slots=True)
class BrowserSettings:
    """Configuracoes de inicializacao e navegacao do Firefox."""

    headless: bool = False
    navigation_timeout_ms: int = 30_000
    locale: str = "pt-BR"
    timezone_id: str = "America/Sao_Paulo"
    viewport_width: int = 1366
    viewport_height: int = 768


class FirefoxBrowser:
    """Mantem um Firefox aberto e cria sessoes isoladas para o bot."""

    def __init__(self, settings: BrowserSettings | None = None) -> None:
        self._settings = settings or BrowserSettings()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._lifecycle_lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        return self._browser is not None and self._browser.is_connected()

    async def start(self) -> None:
        """Inicia o Playwright e o Firefox uma unica vez."""
        async with self._lifecycle_lock:
            if self.is_running:
                return

            playwright = await async_playwright().start()
            try:
                browser = await playwright.firefox.launch(
                    headless=self._settings.headless,
                )
            except Exception:
                await playwright.stop()
                raise

            self._playwright = playwright
            self._browser = browser

    async def stop(self) -> None:
        """Encerra o Firefox e libera os recursos do Playwright."""
        async with self._lifecycle_lock:
            browser, self._browser = self._browser, None
            playwright, self._playwright = self._playwright, None

            if browser is not None:
                await browser.close()
            if playwright is not None:
                await playwright.stop()

    @asynccontextmanager
    async def new_context(self) -> AsyncIterator[BrowserContext]:
        """Cria uma sessao temporaria com cookies e cache isolados."""
        await self.start()
        if self._browser is None:
            raise RuntimeError("Firefox nao foi inicializado")

        context = await self._browser.new_context(
            locale=self._settings.locale,
            timezone_id=self._settings.timezone_id,
            viewport={
                "width": self._settings.viewport_width,
                "height": self._settings.viewport_height,
            },
        )
        context.set_default_navigation_timeout(self._settings.navigation_timeout_ms)

        try:
            yield context
        finally:
            await context.close()

    @asynccontextmanager
    async def new_page(self) -> AsyncIterator[Page]:
        """Entrega uma pagina pronta e fecha sua sessao ao final do uso."""
        async with self.new_context() as context:
            page = await context.new_page()
            yield page

    async def __aenter__(self) -> FirefoxBrowser:
        await self.start()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.stop()
