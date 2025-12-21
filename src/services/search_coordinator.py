from typing import Dict, Any
from datetime import datetime

from src.models import SearchRequest, SearchResponse, PaginatedResult
from src.scrapers.kayak_flights import scrape_flights
from src.scrapers.kayak_hotels import scrape_hotels
from src.scrapers.kayak_cars import scrape_cars
from src.utils.normalization import cap_results


def run_search(req: SearchRequest) -> SearchResponse:
    flights = cap_results(scrape_flights(req), req.max_items)
    hotels = cap_results(scrape_hotels(req), req.max_items)
    cars = cap_results(scrape_cars(req, []), req.max_items)

    meta: Dict[str, Any] = {
        "currency": req.currency,
        "travelers": [
            {
                "name": t.name,
                "age": t.age,
                "category": t.category,
                "id": t.id,
                "partner_id": t.partner_id,
                "bed_pref": t.bed_pref,
            }
            for t in req.travelers
        ],
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "max_items": req.max_items,
        "rental_blocks": [],
        "trip": {
            "start_location": req.trip_start_location,
            "start_date": req.trip_start_date,
            "end_location": req.trip_end_location,
            "end_date": req.trip_end_date,
        },
        "stops": [
            {
                "location": s.location,
                "constraint_type": s.constraint_type,
                "window_start": s.window_start,
                "window_end": s.window_end,
                "min_days": s.min_days,
                "id": s.id,
            }
            for s in req.stops
        ],
    }

    return SearchResponse(
        flights=PaginatedResult(items=flights, total=len(flights)),
        hotels=PaginatedResult(items=hotels, total=len(hotels)),
        cars=PaginatedResult(items=cars, total=len(cars)),
        meta=meta,
    )
