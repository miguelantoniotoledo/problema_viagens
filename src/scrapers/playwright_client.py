"""Utilitários de inicialização do Playwright para scraping."""

import contextlib
import os
from typing import Iterator, Optional

from src import config


def _get_user_agent() -> str:
    # UA simples e atualizável conforme necessidade
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )


@contextlib.contextmanager
def open_browser(headless: bool = True):
    """Abre navegador Playwright (Chromium) com contexto básico.

    Args:
        headless: se False, abre janela para depuração.
    Yields:
        tupla (browser, context)
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError("Playwright não instalado; rode `pip install playwright` e `playwright install`.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(user_agent=_get_user_agent())
        try:
            yield browser, context
        finally:
            context.close()
            browser.close()


def should_use_live_scraper() -> bool:
    """Controla se usamos Playwright ou mocks.

    Variável de ambiente:
        SCRAPER_MODE=live | mock (default mock).
    """
    env_mode = os.getenv("SCRAPER_MODE")
    if env_mode:
        return env_mode.lower() == "live"
    return config.SCRAPER_MODE.lower() == "live"
