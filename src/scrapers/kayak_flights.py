import json
from pathlib import Path
from typing import List, Dict, Any

from src.models import Segment, SearchRequest, SegmentType
from src.utils.normalization import convert_currency


MOCK_FILE = Path("voos.json")


def load_mock() -> List[Dict[str, Any]]:
    if not MOCK_FILE.exists():
        return []
    with MOCK_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def scrape_flights(req: SearchRequest) -> List[Dict[str, Any]]:
    data = load_mock()
    results: List[Dict[str, Any]] = []
    for seg in req.segments:
        if seg.transport != SegmentType.FLIGHT:
            continue
        for row in data:
            if row.get("origem_id") == seg.origin and row.get("destino_id") == seg.destination:
                price_source = float(row.get("custo_voo_pessoa", 0)) * len(req.travelers)
                results.append(
                    {
                        "segment_id": seg.id,
                        "provider": "mock_kayak",
                        "origin": seg.origin,
                        "destination": seg.destination,
                        "departure": seg.departure,
                        "arrival": seg.arrival,
                        "price": convert_currency(price_source, "BRL", req.currency),
                        "currency": req.currency,
                        "details": {
                            "travelers": [t.name for t in req.travelers],
                            "source_currency": "BRL",
                        },
                    }
                )
    return results

