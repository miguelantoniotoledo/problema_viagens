import json
from pathlib import Path
from typing import List, Dict, Any

from src.models import SearchRequest
from src.utils.normalization import convert_currency
from src.scrapers.playwright_client import open_browser, should_use_live_scraper


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
        try:
            return _scrape_hotels_live(req, stays)
        except Exception:
            pass
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
    with open_browser(headless=True) as (_, context):
        page = context.new_page()
        for stay in stays:
            url = (
                f"https://www.kayak.com/hotels/{stay['location']}/"
                f"{stay['checkin']}?checkout={stay['checkout']}"
            )
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(2000)
            cards = page.query_selector_all('[data-hotelid]')
            for card in cards[: req.max_items]:
                name_el = card.query_selector('[data-test-hotel-name]')
                price_el = card.query_selector('[data-test-hotel-price]')
                price_text = price_el.inner_text().replace("$", "").replace(",", "") if price_el else "0"
                price_source = float(price_text or 0) * len(req.travelers)
                results.append(
                    {
                        "city": stay["location"],
                        "name": name_el.inner_text().strip() if name_el else "hotel",
                        "checkin": stay["checkin"],
                        "checkout": stay["checkout"],
                        "nights": stay["nights"],
                        "price_total": convert_currency(price_source, "USD", req.currency),
                        "currency": req.currency,
                        "details": {
                            "base_currency": "USD",
                            "travelers": [t.name for t in req.travelers],
                            "type": stay["type"],
                        },
                    }
                )
    return results
