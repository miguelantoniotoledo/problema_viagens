"""Utilitários de inicialização do Playwright para scraping."""

import contextlib
import os
import asyncio
from typing import Iterator, Optional

from src import config


def _get_user_agent() -> str:
    """Retorna um User-Agent padrão para navegação do Playwright.

    Args:
        None.

    Returns:
        String com User-Agent.
    """
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )


_PLAYWRIGHT_AVAILABLE: Optional[bool] = None


def _has_playwright_installed() -> bool:
    """Verifica se o Playwright e os binarios estao disponiveis.

    Args:
        None.

    Returns:
        True se Playwright estiver instalado.
    """
    global _PLAYWRIGHT_AVAILABLE
    if _PLAYWRIGHT_AVAILABLE is not None:
        return _PLAYWRIGHT_AVAILABLE
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except Exception:
        _PLAYWRIGHT_AVAILABLE = False
        return False
    _PLAYWRIGHT_AVAILABLE = True
    return True


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

    try:
        # Em Windows, garante uso do ProactorEventLoop para subprocessos
        if os.name == "nt":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(user_agent=_get_user_agent())
            try:
                yield browser, context
            finally:
                context.close()
                browser.close()
    except NotImplementedError as exc:
        # Ambientes restritos (ex.: alguns Windows) podem não suportar subprocessos do Playwright
        raise RuntimeError("Playwright não conseguiu iniciar neste ambiente (subprocesso não suportado).") from exc


def should_use_live_scraper() -> bool:
    """Controla se usamos Playwright ou mocks.

    Args:
        None.

    Returns:
        True se deve usar scraper live.
    """
    env_mode = os.getenv("SCRAPER_MODE")
    mode_live = env_mode.lower() == "live" if env_mode else config.SCRAPER_MODE.lower() == "live"
    if not mode_live:
        return False
    # Se playwright não estiver instalado, falha explicitamente
    if not _has_playwright_installed():
        raise RuntimeError("SCRAPER_MODE=live, mas o Playwright/Chromium não está instalado. Rode `pip install playwright` e `python -m playwright install chromium`.")
    return True
