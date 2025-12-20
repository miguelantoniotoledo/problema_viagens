import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from src.models import SearchRequest, RentalBlock
from src.utils.normalization import convert_currency
from src.utils.rental_blocks import parse_iso_date


MOCK_FILE = Path("aluguel_carros.json")


def load_mock() -> List[Dict[str, Any]]:
    if not MOCK_FILE.exists():
        return []
    with MOCK_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def _days_between(start: str, end: str) -> int:
    d1 = parse_iso_date(start)
    d2 = parse_iso_date(end)
    delta = (d2 - d1).days
    return max(1, delta or 1)


def scrape_cars(req: SearchRequest, blocks: List[RentalBlock]) -> List[Dict[str, Any]]:
    data = load_mock()
    results: List[Dict[str, Any]] = []
    for block in blocks:
        for row in data:
            city = row.get("cidade_id")
            if city != block.pickup_location:
                continue
            daily = float(row.get("custo_diaria", 0))
            days = _days_between(block.pickup_date, block.dropoff_date)
            price_source = daily * len(req.travelers) * days
            results.append(
                {
                    "rental_block": {
                        "pickup": block.pickup_location,
                        "dropoff": block.dropoff_location,
                        "pickup_date": block.pickup_date,
                        "dropoff_date": block.dropoff_date,
                        "segments": block.linked_segments,
                    },
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
