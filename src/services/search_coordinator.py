from typing import Dict, Any
from datetime import datetime

from src.models import SearchRequest, SearchResponse, PaginatedResult
from src.scrapers.kayak_flights import scrape_flights
from src.scrapers.kayak_hotels import scrape_hotels
from src.scrapers.kayak_cars import scrape_cars
from src.utils.normalization import cap_results
from src.utils.rental_blocks import build_rental_blocks


def run_search(req: SearchRequest) -> SearchResponse:
    traveler_ids = [t.id for t in req.travelers]
    rental_blocks = build_rental_blocks(req.segments, traveler_ids)

    flights = cap_results(scrape_flights(req), req.max_items)
    hotels = cap_results(scrape_hotels(req), req.max_items)
    cars = cap_results(scrape_cars(req, rental_blocks), req.max_items)

    meta: Dict[str, Any] = {
        "currency": req.currency,
        "travelers": [
            {
                "name": t.name,
                "age": t.age,
                "category": t.category,
                "id": t.id,
                "couple_group_id": t.couple_group_id,
                "bed_pref": t.bed_pref,
            }
            for t in req.travelers
        ],
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "max_items": req.max_items,
        "rental_blocks": [
            {
                "pickup": b.pickup_location,
                "dropoff": b.dropoff_location,
                "pickup_date": b.pickup_date,
                "dropoff_date": b.dropoff_date,
                "segments": b.linked_segments,
            }
            for b in rental_blocks
        ],
    }

    return SearchResponse(
        flights=PaginatedResult(items=flights, total=len(flights)),
        hotels=PaginatedResult(items=hotels, total=len(hotels)),
        cars=PaginatedResult(items=cars, total=len(cars)),
        meta=meta,
    )
