import json
from pathlib import Path
from typing import List, Dict, Any
from urllib.parse import quote
import re
from bs4 import BeautifulSoup

from src.models import SearchRequest
from src.utils.normalization import convert_currency
from src.scrapers.playwright_client import open_browser, should_use_live_scraper
from src import config
from src.utils.autocomplete import search_locations
from src.utils.logs import add_log


MOCK_FILE = Path("hoteis.json")


def load_mock() -> List[Dict[str, Any]]:
    """Carrega o JSON mock de hotéis.

    Returns:
        Lista de hotéis mockados.
    """
    if not MOCK_FILE.exists():
        return []
    with MOCK_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def scrape_hotels(req: SearchRequest, stays: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Mock de scraping de hotéis (Kayak), gerando opções por estada.

    Args:
        req: dados globais da busca (moeda, viajantes).
        stays: lista de estadas {location, checkin, checkout, nights, type}.

    Returns:
        Lista de hotéis candidatos com preço total e metadados.
    """
    if should_use_live_scraper():
        return _scrape_hotels_live(req, stays)
    data = load_mock()
    results: List[Dict[str, Any]] = []
    for stay in stays:
        city = stay["location"]
        for row in data:
            if row.get("cidade_id") != city:
                continue
            nightly = float(row.get("custo_diaria", 0))
            nights = stay["nights"]
            price_source = nightly * len(req.travelers) * max(1, nights)
            results.append(
                {
                    "city": city,
                    "name": row.get("nome", "hotel"),
                    "checkin": stay["checkin"],
                    "checkout": stay["checkout"],
                    "nights": nights,
                    "price_total": convert_currency(price_source, "BRL", req.currency),
                    "currency": req.currency,
                    "details": {
                        "base_currency": "BRL",
                        "travelers": [t.name for t in req.travelers],
                    },
                }
            )
    return results


def _scrape_hotels_live(req: SearchRequest, stays: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Scraping real de hotéis no Kayak usando Playwright (top 20).

    Args:
        req: dados globais da busca (moeda, viajantes).
        stays: estadas a pesquisar.

    Returns:
        Lista de hotéis encontrados com preços convertidos e detalhes.
    """
    results: List[Dict[str, Any]] = []
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    with open_browser(headless=config.PLAYWRIGHT_HEADLESS) as (_, context):
        page = context.new_page()
        page.set_default_timeout(config.PLAYWRIGHT_TIMEOUT_MS)
        for stay in stays:
            checkin = (stay.get("checkin") or "").split("T")[0] or stay.get("checkin")
            checkout = (stay.get("checkout") or "").split("T")[0] or stay.get("checkout")
            # Usa código IATA como slug para hotéis (ex.: MIA)
            slug = quote(stay["location"])
            # Usa domínio configurável e inclui adultos na URL
            adults = max(1, len([t for t in req.travelers if t.category == "adult"]))
            url = f"{config.KAYAK_BASE}/hotels/{slug}/{checkin}/{checkout}/{adults}adults"
            add_log(f"[hotels] URL: {url}")
            final_url = url
            # Tenta carregar e mesmo com timeout tenta seguir
            for attempt in range(2):
                try:
                    page.goto(url, wait_until="domcontentloaded")
                    page.wait_for_timeout(6000)
                    final_url = page.url
                    break
                except PlaywrightTimeoutError:
                    add_log(f"[hotels] Timeout (tentativa {attempt+1}) ao abrir {url}")
            cards = page.query_selector_all('[data-hotelid], [data-test*="hotel-card"]')
            if not cards:
                add_log(f"[hotels] Nenhum card encontrado em {final_url}")
                # Fallback: parse via BeautifulSoup
                soup = BeautifulSoup(page.content(), "html.parser")
                price_nodes = soup.select(".c1XBO, .Ptt7-price")
                name_nodes = soup.select(".c9Hnq-big-name")
                for idx, node in enumerate(price_nodes[: req.max_items]):
                    price_text = node.get_text(" ", strip=True)
                    m = re.search(r"([0-9][0-9\\.,]*)", price_text.replace("\u00a0", " "))
                    price_val = m.group(1) if m else "0"
                    price_val = price_val.replace(".", "").replace(",", ".")
                    price_source = float(price_val or 0) * len(req.travelers)
                    name_text = name_nodes[idx].get_text(" ", strip=True) if idx < len(name_nodes) else "hotel"
                    results.append(
                        {
                            "city": stay["location"],
                            "name": name_text,
                            "checkin": stay["checkin"],
                            "checkout": stay["checkout"],
                            "nights": stay["nights"],
                            "price_total": convert_currency(price_source, "BRL", req.currency),
                            "currency": req.currency,
                            "details": {
                                "base_currency": "BRL",
                                "travelers": [t.name for t in req.travelers],
                                "type": stay["type"],
                            },
                        }
                    )
                add_log(f"[hotels] Parse via fallback HTML em {final_url} ({len(results)} itens parciais)")
                continue
            for card in cards[: req.max_items]:
                name_el = card.query_selector('[data-test-hotel-name]')
                price_el = None
                price_selectors = [
                    ".c1XBO",  # bloco principal de preСo
                    ".Ptt7-price",
                    "[data-test-hotel-price]",
                    "[aria-label*='R$']",
                    "[aria-label*='$']",
                    "[class*='price']",
                ]
                for css in price_selectors:
                    price_el = card.query_selector(css)
                    if price_el:
                        break
                if not price_el:
                    # Fallback baseado em XPath capturado
                    price_el = page.query_selector(
                        'xpath=//*[@id="resultWrapper"]/div[4]/div[1]/div/div/div[3]/div[3]/div/div/div[1]/div[1]/div[2]'
                    )
                if not price_el:
                    price_el = page.query_selector('xpath=//*[@id="resultWrapper"]//div[contains(@class,"price")]')
                if not price_el:
                    add_log(f"[hotels] Nenhum elemento de preço para {stay['location']} url={url}")
                price_text = price_el.inner_text() if price_el else "0"
                m = re.search(r"([0-9][0-9\\.,]*)", price_text.replace("\u00a0", " "))
                price_val = m.group(1) if m else "0"
                price_val = price_val.replace(".", "").replace(",", ".")
                price_source = float(price_val or 0) * len(req.travelers)
                if not name_el:
                    add_log(f"[hotels] Nome do hotel não encontrado para {stay['location']} url={url}")
                results.append(
                    {
                        "city": stay["location"],
                        "name": name_el.inner_text().strip() if name_el else "hotel",
                        "checkin": stay["checkin"],
                        "checkout": stay["checkout"],
                        "nights": stay["nights"],
                        "price_total": convert_currency(price_source, "BRL", req.currency),
                        "currency": req.currency,
                        "details": {
                            "base_currency": "BRL",
                            "travelers": [t.name for t in req.travelers],
                            "type": stay["type"],
                        },
                    }
                )
    return results
