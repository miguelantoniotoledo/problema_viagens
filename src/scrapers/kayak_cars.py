import json
from datetime import datetime
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


def parse_iso_date(value: str) -> datetime:
    """Converte string ISO em datetime com fallback para hoje.

    Args:
        value: data em formato ISO (YYYY-MM-DD).

    Returns:
        Instância de datetime correspondente ou a data atual em fallback.
    """
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return datetime.today()


MOCK_FILE = Path("aluguel_carros.json")


def load_mock() -> List[Dict[str, Any]]:
    """Carrega o JSON mock de aluguel de carros.

    Args:
        None.

    Returns:
        Lista de ofertas mockadas.
    """
    if not MOCK_FILE.exists():
        return []
    with MOCK_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def _days_between(start: str, end: str) -> int:
    """Calcula número de dias entre duas datas ISO (mínimo 1).

    Args:
        start: data inicial em ISO.
        end: data final em ISO.

    Returns:
        Número de dias, sempre ao menos 1.
    """
    d1 = parse_iso_date(start)
    d2 = parse_iso_date(end)
    delta = (d2 - d1).days
    return max(1, delta or 1)


def scrape_cars(req: SearchRequest, rentals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Mock de scraping de carros (Kayak) por blocos de locação.

    Args:
        req: dados globais (moeda, viajantes).
        rentals: blocos {pickup, dropoff, pickup_date, dropoff_date}.

    Returns:
        Lista de ofertas de aluguel com preço total convertido.
    """
    if should_use_live_scraper():
        return _scrape_cars_live(req, rentals)
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
    """Scraping real de carros no Kayak usando Playwright (top 20).

    Args:
        req: dados globais (moeda, viajantes).
        rentals: blocos de locação a pesquisar.

    Returns:
        Lista de carros encontrados com preços convertidos e detalhes.
    """
    results: List[Dict[str, Any]] = []
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    with open_browser(headless=config.PLAYWRIGHT_HEADLESS) as (_, context):
        page = context.new_page()
        page.set_default_timeout(config.PLAYWRIGHT_TIMEOUT_MS)
        for rental in rentals:
            pickup_date = (rental.get("pickup_date") or "").split("T")[0] or rental.get("pickup_date")
            dropoff_date = (rental.get("dropoff_date") or "").split("T")[0] or rental.get("dropoff_date")
            if not pickup_date or not dropoff_date:
                continue
            # Kayak prefere slug de cidade; tentamos manter o código, mas montamos fallback com city
            # Usa código IATA/ID diretamente para evitar issues com acentos
            pickup_slug = quote(rental["pickup"])
            dropoff_slug = quote(rental["dropoff"])
            url = (
                f"{config.KAYAK_BASE}/cars/{pickup_slug}/{dropoff_slug}/{pickup_date}/{dropoff_date}"
                f"?sort=rank_a"
            )
            add_log(f"[cars] URL: {url}")
            final_url = url
            for attempt in range(2):
                try:
                    page.goto(url, wait_until="domcontentloaded")
                    page.wait_for_timeout(6000)
                    final_url = page.url
                    break
                except PlaywrightTimeoutError:
                    add_log(f"[cars] Timeout (tentativa {attempt+1}) ao abrir {url}")
            cards = page.query_selector_all('[data-test-vehicle-card], [data-test*="car-card"]')
            if not cards:
                add_log(f"[cars] Nenhum card encontrado em {final_url}")
                # Fallback com BeautifulSoup
                soup = BeautifulSoup(page.content(), "html.parser")
                price_nodes = soup.select(".c4nz8-price-total, .OcBh-price")
                name_nodes = soup.select("[data-result-id] .js-title, .MseY-title")
                agency_nodes = soup.select(".mR2O-agency-logo, .EuxN-provider")
                for idx, node in enumerate(price_nodes[: req.max_items]):
                    price_text = node.get_text(" ", strip=True)
                    m = re.search(r"([0-9][0-9\\.,]*)", price_text.replace("\u00a0", " "))
                    price_val = m.group(1) if m else "0"
                    price_val = price_val.replace(".", "").replace(",", ".")
                    price_source = float(price_val or 0) * len(req.travelers)
                    name_text = name_nodes[idx].get_text(" ", strip=True) if idx < len(name_nodes) else "locadora"
                    agency_el = agency_nodes[idx] if idx < len(agency_nodes) else None
                    agency = None
                    if agency_el:
                        agency = agency_el.get("alt")
                        if agency:
                            agency = agency.replace("Agência do carro:", "").strip()
                        else:
                            agency = agency_el.get_text(" ", strip=True)
                    results.append(
                        {
                            "rental_block": rental,
                            "city": rental["pickup"],
                            "name": name_text,
                            "price_total": convert_currency(price_source, "BRL", req.currency),
                            "currency": req.currency,
                            "details": {
                                "base_currency": "BRL",
                                "travelers": [t.name for t in req.travelers],
                                "days": _days_between(rental["pickup_date"], rental["dropoff_date"]),
                                "agency": agency,
                            },
                        }
                    )
                add_log(f"[cars] Parse via fallback HTML em {final_url} ({len(results)} itens parciais)")
                continue
            for card in cards[: req.max_items]:
                name_el = card.query_selector('[data-test-vehicle-name]')
                # Tenta capturar a locadora/agência (logo ou texto)
                agency_el = card.query_selector(".mR2O-agency-logo") or card.query_selector(".EuxN-provider")
                price_el = None
                price_selectors = [
                    ".c4nz8-price-total",
                    ".OcBh-price",
                    "[data-test-price]",
                    "[aria-label*='R$']",
                    "[aria-label*='$']",
                    "[class*='price']",
                ]
                for css in price_selectors:
                    price_el = card.query_selector(css)
                    if price_el:
                        break
                if not price_el:
                    price_el = page.query_selector(
                        'xpath=//*[@id="mapListWrapper"]/div/div[1]/div[6]/div[1]/div/div[2]/div/div/div[15]/div/div[3]/div[1]/div'
                    )
                if not price_el:
                    price_el = page.query_selector('xpath=//*[@id="mapListWrapper"]//*[contains(@class,"price")]')
                if not price_el:
                    add_log(f"[cars] Nenhum elemento de preço para {rental['pickup']}->{rental['dropoff']} url={url}")
                price_text = price_el.inner_text() if price_el else "0"
                m = re.search(r"([0-9][0-9\\.,]*)", price_text.replace("\u00a0", " "))
                price_val = m.group(1) if m else "0"
                price_val = price_val.replace(".", "").replace(",", ".")
                price_source = float(price_val or 0) * len(req.travelers)
                results.append(
                    {
                        "rental_block": rental,
                        "city": rental["pickup"],
                        "name": name_el.inner_text().strip() if name_el else "locadora",
                        "price_total": convert_currency(price_source, "BRL", req.currency),
                        "currency": req.currency,
                        "details": {
                            "base_currency": "BRL",
                            "travelers": [t.name for t in req.travelers],
                            "days": _days_between(rental["pickup_date"], rental["dropoff_date"]),
                            "agency": (
                                agency_el.get_attribute("alt").replace("Agência do carro:", "").strip()
                                if agency_el and agency_el.get_attribute("alt")
                                else (agency_el.inner_text().strip() if agency_el else None)
                            ),
                        },
                    }
                )
                if not name_el:
                    add_log(f"[cars] Nome/modelo do veículo não encontrado para {rental['pickup']}->{rental['dropoff']} url={url}")
                if not agency_el:
                    add_log(f"[cars] Agência/locadora não encontrada para {rental['pickup']}->{rental['dropoff']} url={url}")
    return results
