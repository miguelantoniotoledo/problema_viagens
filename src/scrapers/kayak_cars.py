import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from src.models import SearchRequest
from src.utils.normalization import convert_currency
from src.scrapers.playwright_client import open_browser, should_use_live_scraper


def parse_iso_date(value: str) -> datetime:
    """Converte string ISO em datetime com fallback para hoje."""
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return datetime.today()


MOCK_FILE = Path("aluguel_carros.json")


def load_mock() -> List[Dict[str, Any]]:
    if not MOCK_FILE.exists():
        return []
    with MOCK_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def _days_between(start: str, end: str) -> int:
    """Calcula número de dias entre duas datas ISO (mínimo 1)."""
    d1 = parse_iso_date(start)
    d2 = parse_iso_date(end)
    delta = (d2 - d1).days
    return max(1, delta or 1)


def scrape_cars(req: SearchRequest, rentals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Mock de scraping de carros (Kayak) por blocos de locação.

    Args:
        req: dados globais (moeda, travelers).
        rentals: blocos {pickup, dropoff, pickup_date, dropoff_date}.
    Returns:
        Lista de ofertas de aluguel com preço total.
    """
    if should_use_live_scraper():
        try:
            return _scrape_cars_live(req, rentals)
        except Exception:
            pass
    data = load_mock()
    results: List[Dict[str, Any]] = []
    for rental in rentals:
        city = rental["pickup"]
        for row in data:
            if row.get("cidade_id") != city:
                continue
            daily = float(row.get("custo_diaria", 0))
            days = _days_between(rental["pickup_date"], rental["dropoff_date"])
            price_source = daily * len(req.travelers) * days
            results.append(
                {
                    "rental_block": rental,
                    "city": city,
                    "name": row.get("nome", "locadora"),
                    "price_total": convert_currency(price_source, "BRL", req.currency),
                    "currency": req.currency,
                    "details": {
                        "base_currency": "BRL",
                        "travelers": [t.name for t in req.travelers],
                        "days": days,
                    },
                }
            )
    return results


def _scrape_cars_live(req: SearchRequest, rentals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Scraping real de carros no Kayak usando Playwright (top 20)."""
    results: List[Dict[str, Any]] = []
    with open_browser(headless=True) as (_, context):
        page = context.new_page()
        for rental in rentals:
            url = (
                f"https://www.kayak.com/cars/{rental['pickup']}"
                f"?dropoff={rental['dropoff']}"
                f"&pickup={rental['pickup_date']}"
                f"&dropoff={rental['dropoff_date']}"
            )
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(2000)
            cards = page.query_selector_all('[data-test-vehicle-card]')
            for card in cards[: req.max_items]:
                name_el = card.query_selector('[data-test-vehicle-name]')
                price_el = card.query_selector('[data-test-price]')
                price_text = price_el.inner_text().replace("$", "").replace(",", "") if price_el else "0"
                price_source = float(price_text or 0) * len(req.travelers)
                results.append(
                    {
                        "rental_block": rental,
                        "city": rental["pickup"],
                        "name": name_el.inner_text().strip() if name_el else "locadora",
                        "price_total": convert_currency(price_source, "USD", req.currency),
                        "currency": req.currency,
                        "details": {
                            "base_currency": "USD",
                            "travelers": [t.name for t in req.travelers],
                            "days": _days_between(rental["pickup_date"], rental["dropoff_date"]),
                        },
                    }
                )
    return results
