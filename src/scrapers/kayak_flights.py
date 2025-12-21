import json
from pathlib import Path
from typing import List, Dict, Any

from src.models import SearchRequest
from src.utils.normalization import convert_currency
from src.scrapers.playwright_client import open_browser, should_use_live_scraper


MOCK_FILE = Path("voos.json")


def load_mock() -> List[Dict[str, Any]]:
    if not MOCK_FILE.exists():
        return []
    with MOCK_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def scrape_flights(req: SearchRequest, legs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Mock de scraping de voos (Kayak), filtrando legs e preços por viajantes.

    Args:
        req: dados globais da busca (moeda, travelers).
        legs: lista de pernas {origin,destination,departure,arrival}.
    Returns:
        Lista de voos candidatos com preço total e metadados.
    """
    if should_use_live_scraper():
        try:
            return _scrape_flights_live(req, legs)
        except Exception:
            # Se der erro, cair para mock para não quebrar a aplicação
            pass
    data = load_mock()
    results: List[Dict[str, Any]] = []
    for leg in legs:
        for row in data:
            if row.get("origem_id") == leg["origin"] and row.get("destino_id") == leg["destination"]:
                price_source = float(row.get("custo_voo_pessoa", 0)) * len(req.travelers)
                results.append(
                    {
                        "leg": leg,
                        "provider": "mock_kayak",
                        "origin": leg["origin"],
                        "destination": leg["destination"],
                        "departure": leg["departure"],
                        "arrival": leg["arrival"],
                        "price": convert_currency(price_source, "BRL", req.currency),
                        "currency": req.currency,
                        "details": {
                            "travelers": [t.name for t in req.travelers],
                            "source_currency": "BRL",
                        },
                    }
                )
    return results


def _scrape_flights_live(req: SearchRequest, legs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Scraping real de voos no Kayak usando Playwright (top 20).

    Observação: seletores podem mudar; ajuste conforme inspeção real.
    """
    results: List[Dict[str, Any]] = []
    with open_browser(headless=True) as (_, context):
        page = context.new_page()
        for leg in legs:
            url = (
                f"https://www.kayak.com/flights/{leg['origin']}-{leg['destination']}/"
                f"{leg['departure']}?sort=price_a"
            )
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(2000)
            cards = page.query_selector_all('[data-resultid]')
            for card in cards[: req.max_items]:
                price_el = card.query_selector('[data-test-price]')
                time_el = card.query_selector('[data-test-leg-times]')
                airline_el = card.query_selector('[data-test-airline-name]')
                price_text = price_el.inner_text().replace("$", "").replace(",", "") if price_el else "0"
                price_source = float(price_text or 0) * len(req.travelers)
                results.append(
                    {
                        "leg": leg,
                        "provider": airline_el.inner_text().strip() if airline_el else "kayak",
                        "origin": leg["origin"],
                        "destination": leg["destination"],
                        "departure": leg["departure"],
                        "arrival": leg["arrival"],
                        "price": convert_currency(price_source, "USD", req.currency),
                        "currency": req.currency,
                        "details": {
                            "travelers": [t.name for t in req.travelers],
                            "source_currency": "USD",
                            "times": time_el.inner_text().strip() if time_el else "",
                        },
                    }
                )
    return results
