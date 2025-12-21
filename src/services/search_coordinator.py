from typing import Dict, Any, List
from datetime import datetime, timedelta

from src import config
from src.models import SearchRequest, SearchResponse, PaginatedResult, Stop
from src.scrapers.kayak_flights import scrape_flights
from src.scrapers.kayak_hotels import scrape_hotels
from src.scrapers.kayak_cars import scrape_cars
from src.utils.normalization import cap_results
from src.utils.autocomplete import search_locations
from src.utils.geo import drive_distance_and_time


def _parse_date(value: str) -> datetime:
    """Converte string ISO em datetime com fallback para hoje."""
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return datetime.today()


def _compute_stop_windows(stops: List[Stop], trip_start: datetime, trip_end: datetime) -> List[Dict[str, Any]]:
    """Calcula janelas efetivas para cada localidade, limitando ao intervalo da viagem."""
    windows = []
    for stop in stops:
        start = _parse_date(stop.window_start) if stop.window_start else trip_start
        end = _parse_date(stop.window_end) if stop.window_end else start + timedelta(days=(stop.min_days or 1))
        if end > trip_end:
            end = trip_end
        windows.append({"start": start, "end": end, "stop": stop})
    return windows


def _build_stays_and_legs(stops: List[Stop], trip_start: datetime, trip_end: datetime, start_loc: str, end_loc: str):
    """Gera estadas sequenciais e pernas alinhadas às datas (fixo depois flex)."""
    # Separar fixos e flexíveis
    fixed = [s for s in stops if s.constraint_type == "fixed_window"]
    flex = [s for s in stops if s.constraint_type != "fixed_window"]
    fixed_sorted = sorted(fixed, key=lambda s: _parse_date(s.window_start) or trip_start)

    stays: List[Dict[str, Any]] = []
    current_date = trip_start

    # Processa stops fixos na ordem
    for stop in fixed_sorted:
        start = _parse_date(stop.window_start)
        end = _parse_date(stop.window_end)
        if start > current_date:
            gap = (start - current_date).days
            if gap > 0 and gap <= config.GAP_FILL_DAYS:
                stays.append(
                    {
                        "location": stop.location.strip().upper(),
                        "checkin": current_date.isoformat(),
                        "checkout": start.isoformat(),
                        "nights": gap,
                        "type": "gap_fill",
                    }
                )
        stays.append(
            {
                "location": stop.location.strip().upper(),
                "checkin": start.isoformat(),
                "checkout": end.isoformat(),
                "nights": max(1, (end - start).days),
                "type": "main",
            }
        )
        current_date = end

    # Flexíveis entram sequencialmente após o último fixo
    for stop in flex:
        min_days = stop.min_days or 1
        start = current_date
        end = start + timedelta(days=min_days)
        stays.append(
            {
                "location": stop.location.strip().upper(),
                "checkin": start.isoformat(),
                "checkout": end.isoformat(),
                "nights": min_days,
                "type": "main",
            }
        )
        current_date = end

    # Ordena stays por checkin
    stays = sorted(stays, key=lambda s: s["checkin"])

    # Monta pernas baseadas em stays e start/end
    legs: List[Dict[str, Any]] = []
    if stays:
        # inicial
        legs.append(
            {
                "origin": (start_loc or stays[0]["location"]).strip().upper(),
                "destination": stays[0]["location"],
                "departure": trip_start.isoformat(),
                "arrival": stays[0]["checkin"],
            }
        )
        # intermediárias
        for idx in range(len(stays) - 1):
            legs.append(
                {
                    "origin": stays[idx]["location"],
                    "destination": stays[idx + 1]["location"],
                    "departure": stays[idx]["checkout"],
                    "arrival": stays[idx + 1]["checkin"],
                }
            )
        # final
        legs.append(
            {
                "origin": stays[-1]["location"],
                "destination": (end_loc or stays[-1]["location"]).strip().upper(),
                "departure": stays[-1]["checkout"],
                "arrival": trip_end.isoformat(),
            }
        )

    # Enriquecer pernas com distância/tempo
    enhanced_legs = []
    for leg in legs:
        leg_copy = dict(leg)
        loc_o = next((l for l in search_locations(leg["origin"], limit=50) if l["code"] == leg["origin"]), None)
        loc_d = next((l for l in search_locations(leg["destination"], limit=50) if l["code"] == leg["destination"]), None)
        if loc_o and loc_d and loc_o.get("lat") and loc_o.get("lng") and loc_d.get("lat") and loc_d.get("lng"):
            try:
                dist_km, time_h = drive_distance_and_time(
                    (float(loc_o["lat"]), float(loc_o["lng"])), (float(loc_d["lat"]), float(loc_d["lng"]))
                )
                leg_copy["drive_distance_km"] = dist_km
                leg_copy["drive_time_hours"] = time_h
            except Exception:
                pass
        enhanced_legs.append(leg_copy)

    return stays, enhanced_legs


def _build_stays(windows: List[Dict[str, Any]], trip_start: datetime, trip_end: datetime) -> List[Dict[str, Any]]:
    """Cria estadas principais e estadas de gap (até GAP_FILL_DAYS)."""
    stays: List[Dict[str, Any]] = []
    prev_end = trip_start
    for w in windows:
        start = w["start"]
        end = w["end"]
        gap = (start - prev_end).days
        if gap > 0 and gap <= config.GAP_FILL_DAYS:
            stays.append(
                {
                    "location": w["stop"].location.strip().upper(),
                    "checkin": prev_end.isoformat(),
                    "checkout": start.isoformat(),
                    "nights": gap,
                    "type": "gap_fill",
                }
            )
        nights = max(1, (end - start).days or (w["stop"].min_days or 1))
        stays.append(
            {
                "location": w["stop"].location.strip().upper(),
                "checkin": start.isoformat(),
                "checkout": end.isoformat(),
                "nights": nights,
                "type": "main",
            }
        )
        prev_end = end

    gap = (trip_end - prev_end).days
    if gap > 0 and gap <= config.GAP_FILL_DAYS and windows:
        last_loc = windows[-1]["stop"].location.strip().upper()
        stays.append(
            {
                "location": last_loc,
                "checkin": prev_end.isoformat(),
                "checkout": trip_end.isoformat(),
                "nights": gap,
                "type": "gap_fill",
            }
        )
    return stays


def _build_rentals(legs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Cria blocos de locação de carro correspondentes às pernas."""
    rentals: List[Dict[str, Any]] = []
    for leg in legs:
        rentals.append(
            {
                "pickup": leg["origin"],
                "dropoff": leg["destination"],
                "pickup_date": leg["departure"],
                "dropoff_date": leg["arrival"],
                "segments": [],
            }
        )
    return rentals


def run_search(req: SearchRequest) -> SearchResponse:
    """Orquestra cálculo de pernas/estadas e chama scrapers mockados."""
    trip_start = _parse_date(req.trip_start_date) if req.trip_start_date else datetime.today()
    trip_end = _parse_date(req.trip_end_date) if req.trip_end_date else trip_start
    stays, legs = _build_stays_and_legs(req.stops, trip_start, trip_end, req.trip_start_location or "", req.trip_end_location or "")
    rentals = _build_rentals(legs)

    flights = cap_results(scrape_flights(req, legs), req.max_items)
    hotels = cap_results(scrape_hotels(req, stays), req.max_items)
    cars = cap_results(scrape_cars(req, rentals), req.max_items)

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
        "gap_fill_days": config.GAP_FILL_DAYS,
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
        "legs": legs,
        "stays": stays,
    }

    return SearchResponse(
        flights=PaginatedResult(items=flights, total=len(flights)),
        hotels=PaginatedResult(items=hotels, total=len(hotels)),
        cars=PaginatedResult(items=cars, total=len(cars)),
        meta=meta,
    )
