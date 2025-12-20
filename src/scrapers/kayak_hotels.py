import json
from pathlib import Path
from typing import List, Dict, Any, Set

from src.models import Segment, SearchRequest
from src.utils.normalization import convert_currency


MOCK_FILE = Path("hoteis.json")


def load_mock() -> List[Dict[str, Any]]:
    if not MOCK_FILE.exists():
        return []
    with MOCK_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def scrape_hotels(req: SearchRequest) -> List[Dict[str, Any]]:
    data = load_mock()
    # collect destinations where a hotel stay might be relevant
    target_cities: Set[str] = {seg.destination for seg in req.segments}
    results: List[Dict[str, Any]] = []
    for row in data:
        city = row.get("cidade_id")
        if city not in target_cities:
            continue
        nightly = float(row.get("custo_diaria", 0))
        price_source = nightly * len(req.travelers)
        results.append(
            {
                "city": city,
                "name": row.get("nome", "hotel"),
                "price_per_night": convert_currency(price_source, "BRL", req.currency),
                "currency": req.currency,
                "details": {
                    "base_currency": "BRL",
                    "travelers": [t.name for t in req.travelers],
                },
            }
        )
    return results

