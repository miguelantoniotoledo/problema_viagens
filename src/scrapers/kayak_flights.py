import json
from pathlib import Path
from typing import List, Dict, Any
import re
from bs4 import BeautifulSoup

from src.models import SearchRequest
from src.utils.normalization import convert_currency
from src.scrapers.playwright_client import open_browser, should_use_live_scraper
from src import config
from src.utils.logs import add_log
from src.utils.cancel import is_cancelled


MOCK_FILE = Path("voos.json")


def load_mock() -> List[Dict[str, Any]]:
    """Carrega o JSON mock de voos.

    Args:
        None.

    Returns:
        Lista de registros de voos mockados.
    """
    if not MOCK_FILE.exists():
        return []
    with MOCK_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def scrape_flights(req: SearchRequest, legs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Mock de scraping de voos (Kayak), filtrando pernas e preços por viajantes.

    Args:
        req: dados globais da busca (moeda, viajantes).
        legs: lista de pernas {origin, destination, departure, arrival}.

    Returns:
        Lista de voos candidatos com preço total convertido e metadados.
    """
    if should_use_live_scraper():
        return _scrape_flights_live(req, legs)
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

    Args:
        req: dados globais da busca (moeda, viajantes).
        legs: lista de pernas a pesquisar.

    Returns:
        Lista de voos encontrados com preços convertidos e detalhes.

    Nota:
        Seletores podem mudar; ajuste conforme inspeção real.
    """
    results: List[Dict[str, Any]] = []
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    sort_param = "bestflight_a"
    if req.flight_sort_criteria == "price":
        sort_param = "price_a"
    elif req.flight_sort_criteria == "duration":
        sort_param = "duration_a"

    with open_browser(headless=config.PLAYWRIGHT_HEADLESS) as (_, context):
        page = context.new_page()
        page.set_default_timeout(config.PLAYWRIGHT_TIMEOUT_MS)
        for leg in legs:
            if is_cancelled():
                add_log("[flights] Busca cancelada pelo usuario.")
                break
            dep_date = (leg.get("departure") or "").split("T")[0] or leg.get("departure")
            adults = max(1, len([t for t in req.travelers if t.category == "adult"]))

            # url = (
            #     f"{config.KAYAK_BASE}/flights/{leg['origin']}-{leg['destination']}/"
            #     f"{dep_date}/{adults}adults?sort=bestflight_a"
            # )
            url = (
                f"{config.KAYAK_BASE}/flights/{leg['origin']}-{leg['destination']}/"
                f"{dep_date}/{adults}adults?sort={sort_param}"
            )

            add_log(f"[flights] URL: {url}")
            final_url = url
            # Tenta carregar; se der timeout, ainda assim tenta ler os cards renderizados
            for attempt in range(2):
                try:
                    page.goto(url, wait_until="domcontentloaded")
                    page.wait_for_timeout(6000)
                    final_url = page.url
                    break
                except PlaywrightTimeoutError:
                    add_log(f"[flights] Timeout (tentativa {attempt+1}) ao abrir {url}")
            cards = page.query_selector_all('[data-resultid], [data-test*="result-card"]')
            if not cards:
                add_log(f"[flights] Nenhum card encontrado em {final_url}")
                # Fallback: parse via BeautifulSoup
                soup = BeautifulSoup(page.content(), "html.parser")
                price_nodes = soup.select(".e2GB-price-text")
                for node in price_nodes[: req.max_items]:
                    text = node.get_text(" ", strip=True)
                    m = re.search(r"([0-9][0-9\\.,]*)", text.replace("\u00a0", " "))
                    price_val = m.group(1) if m else "0"
                    price_val = price_val.replace(".", "").replace(",", ".")
                    price_source = float(price_val or 0) * len(req.travelers)
                    results.append(
                        {
                            "leg": leg,
                            "provider": "kayak",
                            "origin": leg["origin"],
                            "destination": leg["destination"],
                            "departure": leg["departure"],
                            "arrival": leg["arrival"],
                            "price": convert_currency(price_source, "BRL", req.currency),
                            "currency": req.currency,
                            "details": {
                                "travelers": [t.name for t in req.travelers],
                                "source_currency": "BRL",
                                "times": "",
                            },
                        }
                    )
                continue
            for card in cards[: req.max_items]:
                price_el = None
                # Seletores observados na pбgina .com.br (ex.: div.e2GB-price-text)
                price_selectors = [
                    ".e2GB-price-text",
                    "[data-test-price]",
                    "[aria-label*='$']",
                    "[aria-label*='R$']",
                    "[class*='price']",
                ]
                for css in price_selectors:
                    price_el = card.query_selector(css)
                    if price_el:
                        break
                if not price_el:
                    # Fallback baseado em XPath capturado
                    price_el = page.query_selector(
                        'xpath=//*[@id="flight-results-list-wrapper"]/div[3]/div[2]/div/div[1]/div[2]/div/div[2]/div/div[2]/div/div[2]/div/div[1]/div[1]/a/div/div/div[1]/div/div[1]'
                    )
                if not price_el:
                    price_el = page.query_selector(
                        'xpath=//*[@id="flight-results-list-wrapper"]//*[contains(@class,"price")]'
                    )
                if not price_el:
                    add_log(f"[flights] Nenhum elemento de preço encontrado para {leg['origin']}->{leg['destination']} url={url}")
                price_text = price_el.inner_text() if price_el else "0"
                m = re.search(r"([0-9][0-9\\.,]*)", price_text.replace("\u00a0", " "))
                price_val = m.group(1) if m else "0"
                price_val = price_val.replace(".", "").replace(",", ".")
                price_source = float(price_val or 0) * len(req.travelers)
                time_el = card.query_selector('[data-test-leg-times]') or card.query_selector(".vmXl-mod-variant-large")
                provider_name = ""
                operator_el = card.query_selector(".J0g6-operator-text")
                if operator_el:
                    provider_name = (operator_el.inner_text() or "").strip()
                if not provider_name:
                    airline_imgs = card.query_selector_all(".c5iUd-leg-carrier img[alt]")
                    airline_names = []
                    for img in airline_imgs:
                        name = (img.get_attribute("alt") or "").strip()
                        if name and name not in airline_names:
                            airline_names.append(name)
                    provider_name = ", ".join(airline_names)
                if not provider_name:
                    add_log(f"[flights] Companhia aerea nao encontrada para {leg['origin']}->{leg['destination']} url={url}")
                if not time_el:
                    add_log(f"[flights] Horário não encontrado para {leg['origin']}->{leg['destination']} url={url}")
                results.append(
                    {
                        "leg": leg,
                        "provider": provider_name or "kayak",
                        "origin": leg["origin"],
                        "destination": leg["destination"],
                        "departure": leg["departure"],
                        "arrival": leg["arrival"],
                        "price": convert_currency(price_source, "BRL", req.currency),
                        "currency": req.currency,
                        "details": {
                            "travelers": [t.name for t in req.travelers],
                            "source_currency": "BRL",
                            "times": time_el.inner_text().strip() if time_el else "",
                        },
                    }
                )
    return results
