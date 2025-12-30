from typing import Dict, Any, List
import itertools
from datetime import datetime, timedelta

from src import config
from src.models import SearchRequest, SearchResponse, PaginatedResult, Stop
from src.scrapers.kayak_flights import scrape_flights
from src.scrapers.kayak_hotels import scrape_hotels
from src.scrapers.kayak_cars import scrape_cars
from src.utils.normalization import cap_results
from src.utils.autocomplete import search_locations
from src.utils.geo import drive_distance_and_time
from src.utils.logs import clear_log, get_log


def _parse_date(value: str) -> datetime:
    """Converte string ISO em datetime com fallback para hoje.

    Args:
        value: data em formato ISO (YYYY-MM-DD ou YYYY-MM-DDTHH:MM:SS).

    Returns:
        Objeto datetime correspondente ou a data/hora atual em fallback.
    """
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return datetime.today()


def _compute_stop_windows(stops: List[Stop], trip_start: datetime, trip_end: datetime) -> List[Dict[str, Any]]:
    """Calcula janelas efetivas para cada localidade, limitando ao intervalo da viagem.

    Args:
        stops: lista de localidades com restrições.
        trip_start: data/hora inicial da viagem.
        trip_end: data/hora final da viagem.

    Returns:
        Lista de janelas normalizadas com início/fim ajustados ao intervalo da viagem.
    """
    windows = []
    for stop in stops:
        start = _parse_date(stop.window_start) if stop.window_start else trip_start
        end = _parse_date(stop.window_end) if stop.window_end else start + timedelta(days=(stop.min_days or 1))
        if end > trip_end:
            end = trip_end
        windows.append({"start": start, "end": end, "stop": stop})
    return windows


def _build_stays_and_legs(stops: List[Stop], trip_start: datetime, trip_end: datetime, start_loc: str, end_loc: str):
    """Gera combinações (permutando flex) com estadas e pernas; sem gap final.

    Args:
        stops: lista de localidades (fixas e flexíveis).
        trip_start: data/hora inicial da viagem.
        trip_end: data/hora final da viagem.
        start_loc: local de partida da viagem.
        end_loc: local de chegada da viagem.

    Returns:
        Tuple (stays, legs, warnings, scenarios) com estadas, pernas, avisos e cenários testados.
    """
    fixed = [s for s in stops if s.constraint_type == "fixed_window"]
    flex = [s for s in stops if s.constraint_type != "fixed_window"]
    fixed_sorted = sorted(fixed, key=lambda s: _parse_date(s.window_start) or trip_start)

    warnings: List[str] = []
    scenarios: List[Dict[str, Any]] = []

    flex_orders = list(itertools.permutations(flex)) if len(flex) <= 6 else [tuple(flex)]
    if len(flex) > 6:
        warnings.append("Stops flexíveis > 6, mantendo ordem de entrada.")

    seen_orders = set()

    for order in flex_orders:
        # Evita combinações onde a mesma cidade fica em sequência (ex.: MIA -> MIA)
        sequence = [s.location for s in fixed_sorted] + [s.location for s in order]
        if any(sequence[i] == sequence[i - 1] for i in range(1, len(sequence))):
            continue
        # Evita duplicar cenários quando há localidades iguais em flex (mesma sequência)
        seq_key = tuple(sequence)
        if seq_key in seen_orders:
            continue
        seen_orders.add(seq_key)
        stays: List[Dict[str, Any]] = []
        current_date = trip_start
        feasible = True

        # Fixos na ordem
        for stop in fixed_sorted:
            start = _parse_date(stop.window_start)
            end = _parse_date(stop.window_end)
            if start > trip_end or end > trip_end:
                feasible = False
                break
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
        if not feasible:
            continue

        # Flex na ordem candidata
        for stop in order:
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

        overrun_days = (current_date - trip_end).days if current_date > trip_end else 0
        scenarios.append(
            {
                "stays": sorted(stays, key=lambda s: s["checkin"]),
                "order": [s.location for s in fixed_sorted] + [s.location for s in order],
                "is_feasible": current_date <= trip_end,
                "overrun_days": max(0, overrun_days),
            }
        )

    # Escolhe a primeira combinação (feasible se houver) para rodar scrapers
    chosen = next((s for s in scenarios if s["is_feasible"]), scenarios[0] if scenarios else {"stays": [], "order": [], "is_feasible": True, "overrun_days": 0})
    stays = chosen["stays"]

    def _legs_from_stays(stays_seq: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        legs_local: List[Dict[str, Any]] = []

        if not stays_seq:
            # return legs_local
            if start_loc and end_loc:
                legs_local.append(
                    {
                        "origin": (start_loc or stays_seq[0]["location"]).strip().upper(),
                        "destination": stays_seq[0]["location"],
                        "departure": trip_start.isoformat(),
                        "arrival": stays_seq[0]["checkin"],
                    }
                )
            return legs_local
        for idx in range(len(stays_seq) - 1):
            legs_local.append(
                {
                    "origin": stays_seq[idx]["location"],
                    "destination": stays_seq[idx + 1]["location"],
                    "departure": stays_seq[idx]["checkout"],
                    "arrival": stays_seq[idx + 1]["checkin"],
                }
            )
        legs_local.append(
            {
                "origin": stays_seq[-1]["location"],
                "destination": (end_loc or stays_seq[-1]["location"]).strip().upper(),
                "departure": stays_seq[-1]["checkout"],
                "arrival": trip_end.isoformat(),
            }
        )
        return legs_local

    # Usa pernas do cenário escolhido, mas busca em todas as pernas únicas de todos os cenários para os scrapers
    legs = _legs_from_stays(stays)
    all_legs = []
    seen_leg_keys = set()
    for sc in scenarios:
        for leg in _legs_from_stays(sc["stays"]):
            key = (leg["origin"], leg["destination"], leg["departure"], leg["arrival"])
            if key in seen_leg_keys:
                continue
            seen_leg_keys.add(key)
            all_legs.append(leg)

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

    return stays, enhanced_legs, warnings, scenarios, all_legs


def _build_stays(windows: List[Dict[str, Any]], trip_start: datetime, trip_end: datetime) -> List[Dict[str, Any]]:
    """Cria estadas principais e estadas de gap (até GAP_FILL_DAYS).

    Args:
        windows: janelas calculadas para cada localidade.
        trip_start: início da viagem.
        trip_end: fim da viagem.

    Returns:
        Lista de estadas ordenadas.
    """
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


def _build_rentals(legs: List[Dict[str, Any]], warnings: List[str]) -> List[Dict[str, Any]]:
    """Cria blocos de locação de carro correspondentes às pernas, respeitando limite de distância.

    Args:
        legs: pernas calculadas da viagem.
        warnings: lista mutável de avisos.

    Returns:
        Lista de blocos de locação para cada perna válida.
    """
    rentals: List[Dict[str, Any]] = []
    for leg in legs:
        dist = leg.get("drive_distance_km")
        # Se n╞o houver dist╞ncia na perna agregada, tenta calcular via geolocaliza├º├úo.
        if dist is None:
            loc_o = next((l for l in search_locations(leg["origin"], limit=50) if l["code"] == leg["origin"]), None)
            loc_d = next((l for l in search_locations(leg["destination"], limit=50) if l["code"] == leg["destination"]), None)
            if loc_o and loc_d and loc_o.get("lat") and loc_o.get("lng") and loc_d.get("lat") and loc_d.get("lng"):
                try:
                    dist, _ = drive_distance_and_time(
                        (float(loc_o["lat"]), float(loc_o["lng"])), (float(loc_d["lat"]), float(loc_d["lng"]))
                    )
                except Exception:
                    dist = None
        if dist and config.MAX_CAR_DISTANCE_KM and dist > config.MAX_CAR_DISTANCE_KM:
            warnings.append(
                f"Perna {leg['origin']} -> {leg['destination']} ({dist:.0f} km) excede limite de carro ({config.MAX_CAR_DISTANCE_KM} km)."
            )
            continue
        # Garante pelo menos 1 dia de locação
        pickup_date = leg["departure"]
        dropoff_date = leg["arrival"]
        try:
            d1 = _parse_date(pickup_date)
            d2 = _parse_date(dropoff_date)
            if d1 == d2:
                d2 = d1 + timedelta(days=1)
                dropoff_date = d2.isoformat()
        except Exception:
            pass
        rentals.append(
            {
                "pickup": leg["origin"],
                "dropoff": leg["destination"],
                "pickup_date": pickup_date,
                "dropoff_date": dropoff_date,
                "segments": [],
            }
        )
    return rentals


def run_search(req: SearchRequest, include_scrapers: bool = True) -> SearchResponse:
    """Orquestra cálculo de pernas/estadas e chama scrapers (ou só planeja).

    Args:
        req: objeto de requisição com viagem, stops e viajantes.
        include_scrapers: se False, retorna apenas o plano/meta sem buscar voos/hotéis/carros.

    Returns:
        SearchResponse com voos, hotéis, carros e metadados.
    """
    clear_log()
    trip_start = _parse_date(req.trip_start_date) if req.trip_start_date else datetime.today()
    # Se não houver data final, sugerir como start + min_days_required
    min_days_required = sum(
        [
            (s.min_days or 0) if s.constraint_type != "fixed_window" else max(0, (_parse_date(s.window_end) - _parse_date(s.window_start)).days)
            for s in req.stops
        ]
    )
    if req.trip_end_date:
        trip_end = _parse_date(req.trip_end_date)
    else:
        trip_end = trip_start + timedelta(days=min_days_required)
    stays, legs, warnings, scenarios, all_legs = _build_stays_and_legs(req.stops, trip_start, trip_end, req.trip_start_location or "", req.trip_end_location or "")
    rentals = _build_rentals(all_legs, warnings)

    if include_scrapers:
        flights = scrape_flights(req, all_legs)  # limite é por perna dentro do scraper
        # Monta stays únicas para buscar hotéis em todas as combinações (limite por estada no scraper)
        unique_stays: List[Dict[str, Any]] = []
        seen_stay = set()
        for sc in scenarios:
            for st in sc["stays"]:
                key = (st["location"], st["checkin"], st["checkout"])
                if key in seen_stay:
                    continue
                seen_stay.add(key)
                unique_stays.append(st)
        hotels = scrape_hotels(req, unique_stays)
        cars = scrape_cars(req, rentals)
    else:
        flights = []
        hotels = []
        cars = []

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
        "min_days_required": sum([(s.min_days or 0) if s.constraint_type != "fixed_window" else max(0, (_parse_date(s.window_end) - _parse_date(s.window_start)).days) for s in req.stops]),
        "trip_span_days": max(0, (trip_end - trip_start).days),
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
        "warnings": warnings,
        "logs": get_log(),
        "scenarios": [
            {
                "order": sc["order"],
                "is_feasible": sc["is_feasible"],
                "overrun_days": sc["overrun_days"],
                "stays": sc["stays"],
            }
            for sc in scenarios
        ],
    }

    return SearchResponse(
        flights=PaginatedResult(items=flights, total=len(flights)),
        hotels=PaginatedResult(items=hotels, total=len(hotels)),
        cars=PaginatedResult(items=cars, total=len(cars)),
        meta=meta,
    )
