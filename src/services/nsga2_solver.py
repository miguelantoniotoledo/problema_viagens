import json
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

from src import config


def _parse_date(value: str) -> datetime:
    """Converte string ISO em datetime com fallback para hoje.

    Args:
        value: data em formato ISO.

    Returns:
        Objeto datetime correspondente ou data atual.
    """
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return datetime.today()


def _date_key(value: str) -> str:
    """Extrai a parte de data (YYYY-MM-DD) de uma string ISO.

    Args:
        value: data/hora em string ISO.

    Returns:
        String apenas com a data.
    """
    return (value or "").split("T")[0]


def _parse_time_range(value: str) -> float:
    """Converte string 'HH:MM – HH:MM(+1)' em horas aproximadas.

    Args:
        value: faixa de horario com possivel +1.

    Returns:
        Duracao em horas.
    """
    if not value:
        return 0.0
    parts = value.split("–")
    if len(parts) != 2:
        return 0.0
    start_raw = parts[0].strip()
    end_raw = parts[1].strip()
    day_add = 0
    if "+1" in end_raw:
        end_raw = end_raw.replace("+1", "").strip()
        day_add = 1
    try:
        start_h, start_m = [int(x) for x in start_raw.split(":")]
        end_h, end_m = [int(x) for x in end_raw.split(":")]
    except Exception:
        return 0.0
    start = timedelta(hours=start_h, minutes=start_m)
    end = timedelta(days=day_add, hours=end_h, minutes=end_m)
    delta = end - start
    if delta.total_seconds() < 0:
        delta += timedelta(days=1)
    return round(delta.total_seconds() / 3600, 2)


def _build_legs_from_stays(stays: List[Dict[str, Any]], trip: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Gera pernas a partir de estadas e datas de inicio/fim da viagem.

    Args:
        stays: lista de estadas (main/gap).
        trip: dicionario com start/end da viagem.

    Returns:
        Lista de pernas com origem, destino, partida e chegada.
    """
    stays_sorted = sorted(stays, key=lambda s: s["checkin"])
    legs: List[Dict[str, Any]] = []
    if not stays_sorted:
        return legs
    trip_start = _parse_date(trip.get("start_date") or "")
    trip_end = _parse_date(trip.get("end_date") or "")
    if trip.get("start_location"):
        origin = trip.get("start_location")
        destination = stays_sorted[0]["location"]
        if origin != destination:
            first_checkin = stays_sorted[0]["checkin"]
            legs.append(
                {
                    "origin": origin,
                    "destination": destination,
                    "departure": first_checkin,
                    "arrival": first_checkin,
                }
            )
    for idx in range(len(stays_sorted) - 1):
        legs.append(
            {
                "origin": stays_sorted[idx]["location"],
                "destination": stays_sorted[idx + 1]["location"],
                "departure": stays_sorted[idx]["checkout"],
                "arrival": stays_sorted[idx + 1]["checkin"],
            }
        )
    if trip.get("end_location"):
        origin = stays_sorted[-1]["location"]
        destination = trip.get("end_location")
        if origin != destination:
            legs.append(
                {
                    "origin": origin,
                    "destination": destination,
                    "departure": stays_sorted[-1]["checkout"],
                    "arrival": trip_end.isoformat(),
                }
            )
    return [leg for leg in legs if leg["origin"] != leg["destination"]]


def _index_flights(data: Dict[str, Any]) -> Dict[Tuple[str, str, str], List[Dict[str, Any]]]:
    """Indexa voos por (origem, destino, data) para acesso rapido.

    Args:
        data: JSON completo de resultados.

    Returns:
        Dicionario com listas de voos por chave.
    """
    flights = data.get("flights", {}).get("items", [])
    index: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
    for item in flights:
        leg = item.get("leg") or {}
        key = (leg.get("origin"), leg.get("destination"), _date_key(leg.get("departure")))
        if None in key:
            continue
        index.setdefault(key, []).append(item)
    return index


def _index_hotels(data: Dict[str, Any]) -> Dict[Tuple[str, str, str], List[Dict[str, Any]]]:
    """Indexa hoteis por (cidade, checkin, checkout).

    Args:
        data: JSON completo de resultados.

    Returns:
        Dicionario com listas de hoteis por chave.
    """
    hotels = data.get("hotels", {}).get("items", [])
    index: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
    for item in hotels:
        key = (item.get("city"), _date_key(item.get("checkin")), _date_key(item.get("checkout")))
        if None in key:
            continue
        index.setdefault(key, []).append(item)
    return index


def _index_cars(data: Dict[str, Any]) -> Dict[Tuple[str, str, str, str], List[Dict[str, Any]]]:
    """Indexa carros por (pickup, dropoff, data retirada, data devolucao).

    Args:
        data: JSON completo de resultados.

    Returns:
        Dicionario com listas de locacoes por chave.
    """
    cars = data.get("cars", {}).get("items", [])
    index: Dict[Tuple[str, str, str, str], List[Dict[str, Any]]] = {}
    for item in cars:
        block = item.get("rental_block") or {}
        key = (
            block.get("pickup"),
            block.get("dropoff"),
            _date_key(block.get("pickup_date")),
            _date_key(block.get("dropoff_date")),
        )
        if None in key:
            continue
        index.setdefault(key, []).append(item)
    return index


def _fast_nondominated_sort(pop: List[Dict[str, Any]]) -> List[List[int]]:
    """Executa a ordenacao nao-dominada do NSGA-II.

    Args:
        pop: populacao com objetivos avaliados.

    Returns:
        Lista de frentes com indices da populacao.
    """
    fronts: List[List[int]] = []
    dom_count = [0] * len(pop)
    dominated: List[List[int]] = [[] for _ in pop]
    for p in range(len(pop)):
        for q in range(len(pop)):
            if p == q:
                continue
            if _dominates(pop[p]["objectives"], pop[q]["objectives"]):
                dominated[p].append(q)
            elif _dominates(pop[q]["objectives"], pop[p]["objectives"]):
                dom_count[p] += 1
        if dom_count[p] == 0:
            pop[p]["rank"] = 0
            if not fronts:
                fronts.append([])
            fronts[0].append(p)
    i = 0
    while i < len(fronts):
        next_front: List[int] = []
        for p in fronts[i]:
            for q in dominated[p]:
                dom_count[q] -= 1
                if dom_count[q] == 0:
                    pop[q]["rank"] = i + 1
                    next_front.append(q)
        if next_front:
            fronts.append(next_front)
        i += 1
    return fronts


def _dominates(a: Dict[str, float], b: Dict[str, float]) -> bool:
    """Verifica se a solucao A domina a solucao B.

    Args:
        a: objetivos da solucao A.
        b: objetivos da solucao B.

    Returns:
        True se A domina B.
    """
    not_worse = all(a[k] <= b[k] for k in a)
    strictly_better = any(a[k] < b[k] for k in a)
    return not_worse and strictly_better


def _crowding_distance(pop: List[Dict[str, Any]], front: List[int]) -> Dict[int, float]:
    """Calcula a distancia de aglomeracao para uma frente.

    Args:
        pop: populacao com objetivos.
        front: indices da frente.

    Returns:
        Dicionario indice->distancia.
    """
    distance = {i: 0.0 for i in front}
    if not front:
        return distance
    keys = list(pop[0]["objectives"].keys())
    for key in keys:
        sorted_idx = sorted(front, key=lambda i: pop[i]["objectives"][key])
        distance[sorted_idx[0]] = float("inf")
        distance[sorted_idx[-1]] = float("inf")
        min_val = pop[sorted_idx[0]]["objectives"][key]
        max_val = pop[sorted_idx[-1]]["objectives"][key]
        if max_val == min_val:
            continue
        for j in range(1, len(sorted_idx) - 1):
            prev_val = pop[sorted_idx[j - 1]]["objectives"][key]
            next_val = pop[sorted_idx[j + 1]]["objectives"][key]
            distance[sorted_idx[j]] += (next_val - prev_val) / (max_val - min_val)
    return distance


def _tournament(pop: List[Dict[str, Any]], distances: Dict[int, float]) -> Dict[str, Any]:
    """Seleciona um individuo por torneio (rank + crowding).

    Args:
        pop: populacao atual.
        distances: distancias de aglomeracao.

    Returns:
        Solucao vencedora.
    """
    a, b = random.sample(range(len(pop)), 2)
    if pop[a]["rank"] < pop[b]["rank"]:
        return pop[a]
    if pop[b]["rank"] < pop[a]["rank"]:
        return pop[b]
    return pop[a] if distances.get(a, 0) >= distances.get(b, 0) else pop[b]


def _evaluate_solution(groups: List[Dict[str, Any]], choice: List[int]) -> Dict[str, Any]:
    """Avalia uma solucao calculando objetivos e selecoes.

    Args:
        groups: grupos de decisao (transporte/hotel).
        choice: indices escolhidos por grupo.

    Returns:
        Dicionario com selecoes e objetivos.
    """
    flights = []
    hotels = []
    cars = []
    total_cost = 0.0
    total_duration = 0.0
    for idx, group in enumerate(groups):
        option = group["options"][choice[idx]]
        if group["type"] == "transport":
            if option.get("_kind") == "car":
                cars.append(option)
                total_cost += float(option.get("price_total") or 0)
            else:
                flights.append(option)
                total_cost += float(option.get("price") or 0)
                total_duration += _parse_time_range(option.get("details", {}).get("times", ""))
        elif group["type"] == "hotel":
            hotels.append(option)
            total_cost += float(option.get("price_total") or 0)
        else:
            cars.append(option)
            total_cost += float(option.get("price_total") or 0)
    return {
        "choices": choice,
        "selections": {"flights": flights, "hotels": hotels, "cars": cars},
        "objectives": {
            "cost_total": round(total_cost, 2),
            "flight_duration_hours": round(total_duration, 2),
        },
    }


def _build_transport_options(
    leg: Dict[str, Any],
    flight_index: Dict[Tuple[str, str, str], List[Dict[str, Any]]],
    car_index: Dict[Tuple[str, str, str, str], List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Monta opcoes de transporte (voo ou carro) para uma perna.

    Args:
        leg: perna com origem/destino/datas.
        flight_index: indice de voos.
        car_index: indice de carros.

    Returns:
        Lista de opcoes de transporte.
    """
    key_flight = (leg["origin"], leg["destination"], _date_key(leg["departure"]))
    key_car = (
        leg["origin"],
        leg["destination"],
        _date_key(leg["departure"]),
        _date_key(leg["arrival"]),
    )
    options = []
    for item in flight_index.get(key_flight, []):
        copy_item = dict(item)
        copy_item["_kind"] = "flight"
        options.append(copy_item)
    for item in car_index.get(key_car, []):
        copy_item = dict(item)
        copy_item["_kind"] = "car"
        options.append(copy_item)
    return options


def _build_groups_for_scenario(
    scenario: Dict[str, Any],
    trip: Dict[str, Any],
    flight_index: Dict[Tuple[str, str, str], List[Dict[str, Any]]],
    hotel_index: Dict[Tuple[str, str, str], List[Dict[str, Any]]],
    car_index: Dict[Tuple[str, str, str, str], List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Cria grupos de decisao para um cenario.

    Args:
        scenario: cenario com estadas.
        trip: dados de inicio/fim.
        flight_index: indice de voos.
        hotel_index: indice de hoteis.
        car_index: indice de carros.

    Returns:
        Lista de grupos (transporte/hotel); vazia se incompleto.
    """
    groups: List[Dict[str, Any]] = []
    stays = [s for s in scenario.get("stays", []) if s.get("type") == "main"]
    legs = _build_legs_from_stays(scenario.get("stays", []), trip)
    for leg in legs:
        options = _build_transport_options(leg, flight_index, car_index)
        if not options:
            return []
        groups.append({"type": "transport", "key": (leg["origin"], leg["destination"]), "options": options})
    for stay in stays:
        key = (stay.get("location"), _date_key(stay.get("checkin")), _date_key(stay.get("checkout")))
        options = hotel_index.get(key, [])
        if not options:
            return []
        groups.append({"type": "hotel", "key": key, "options": options})
    return groups


def solve_nsga2(
    data: Dict[str, Any],
    max_solutions: int = 3,
    population_size: int = 50,
    generations: int = 40,
    seed: int = 42,
    preference: str = "best",
) -> List[Dict[str, Any]]:
    """Executa o NSGA-II e retorna as melhores solucoes por preferencia.

    Args:
        data: JSON completo com voos/hoteis/carros e meta.
        max_solutions: limite de solucoes retornadas.
        population_size: tamanho da populacao.
        generations: numero de geracoes.
        seed: semente para reproducibilidade.
        preference: "best", "price" ou "duration".

    Returns:
        Lista de solucoes com objetivos e selecoes.
    """
    random.seed(seed)
    scenarios = data.get("meta", {}).get("scenarios", [])
    trip = data.get("meta", {}).get("trip", {})
    flight_index = _index_flights(data)
    hotel_index = _index_hotels(data)
    car_index = _index_cars(data)
    results: List[Dict[str, Any]] = []
    seen_selection_keys = set()

    for scenario in scenarios:
        groups = _build_groups_for_scenario(scenario, trip, flight_index, hotel_index, car_index)
        if not groups:
            continue
        # grupos vazios já foram filtrados na construção

        pop = []
        for _ in range(population_size):
            choice = [random.randrange(len(group["options"])) for group in groups]
            pop.append(_evaluate_solution(groups, choice))

        for _ in range(generations):
            fronts = _fast_nondominated_sort(pop)
            distances: Dict[int, float] = {}
            for front in fronts:
                distances.update(_crowding_distance(pop, front))
            offspring = []
            while len(offspring) < population_size:
                parent_a = _tournament(pop, distances)
                parent_b = _tournament(pop, distances)
                child_choice = []
                for idx in range(len(groups)):
                    if random.random() < 0.5:
                        child_choice.append(parent_a["choices"][idx])
                    else:
                        child_choice.append(parent_b["choices"][idx])
                    if random.random() < 0.1:
                        child_choice[-1] = random.randrange(len(groups[idx]["options"]))
                offspring.append(_evaluate_solution(groups, child_choice))
            pop.extend(offspring)
            fronts = _fast_nondominated_sort(pop)
            new_pop = []
            for front in fronts:
                if len(new_pop) + len(front) > population_size:
                    distances = _crowding_distance(pop, front)
                    sorted_front = sorted(front, key=lambda i: distances.get(i, 0), reverse=True)
                    new_pop.extend([pop[i] for i in sorted_front[: population_size - len(new_pop)]])
                    break
                new_pop.extend([pop[i] for i in front])
            pop = new_pop

        fronts = _fast_nondominated_sort(pop)
        best_front = fronts[0] if fronts else list(range(len(pop)))
        best_candidates = [pop[i] for i in best_front]
        if preference == "price":
            best = sorted(
                best_candidates,
                key=lambda s: (s["objectives"]["cost_total"], s["objectives"]["flight_duration_hours"]),
            )[:max_solutions]
        elif preference == "duration":
            best = sorted(
                best_candidates,
                key=lambda s: (s["objectives"]["flight_duration_hours"], s["objectives"]["cost_total"]),
            )[:max_solutions]
        else:
            weight_cost = getattr(config, "NSGA_WEIGHT_COST", 0.5)
            weight_duration = getattr(config, "NSGA_WEIGHT_DURATION", 0.5)
            min_cost = min(s["objectives"]["cost_total"] for s in best_candidates)
            max_cost = max(s["objectives"]["cost_total"] for s in best_candidates)
            min_dur = min(s["objectives"]["flight_duration_hours"] for s in best_candidates)
            max_dur = max(s["objectives"]["flight_duration_hours"] for s in best_candidates)
            def _score(sol: Dict[str, Any]) -> float:
                """Calcula score ponderado de custo/duracao para ranking.

                Args:
                    sol: solucao com objetivos calculados.

                Returns:
                    Score normalizado ponderado.
                """
                cost = sol["objectives"]["cost_total"]
                dur = sol["objectives"]["flight_duration_hours"]
                norm_cost = 0.0 if max_cost == min_cost else (cost - min_cost) / (max_cost - min_cost)
                norm_dur = 0.0 if max_dur == min_dur else (dur - min_dur) / (max_dur - min_dur)
                return (weight_cost * norm_cost) + (weight_duration * norm_dur)
            best = sorted(best_candidates, key=_score)[:max_solutions]
        for sol in best:
            selection_key = json.dumps(sol["selections"], sort_keys=True)
            if selection_key in seen_selection_keys:
                continue
            seen_selection_keys.add(selection_key)
            results.append(
                {
                    "scenario_order": scenario.get("order", []),
                    "objectives": sol["objectives"],
                    "selections": sol["selections"],
                }
            )
            if len(results) >= max_solutions:
                return results
    return results


def diagnose_missing(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Diagnostica pernas/estadas sem opcoes para cada cenario.

    Args:
        data: JSON completo com voos/hoteis/carros e meta.

    Returns:
        Lista de diagnosticos por cenario com faltas.
    """
    scenarios = data.get("meta", {}).get("scenarios", [])
    trip = data.get("meta", {}).get("trip", {})
    flight_index = _index_flights(data)
    hotel_index = _index_hotels(data)
    car_index = _index_cars(data)
    diagnostics: List[Dict[str, Any]] = []

    for scenario in scenarios:
        missing_legs = []
        missing_hotels = []
        stays = [s for s in scenario.get("stays", []) if s.get("type") == "main"]
        legs = _build_legs_from_stays(scenario.get("stays", []), trip)
        for leg in legs:
            options = _build_transport_options(leg, flight_index, car_index)
            if not options:
                missing_legs.append(
                    {
                        "origin": leg["origin"],
                        "destination": leg["destination"],
                        "date": _date_key(leg["departure"]),
                    }
                )
        for stay in stays:
            key = (stay.get("location"), _date_key(stay.get("checkin")), _date_key(stay.get("checkout")))
            options = hotel_index.get(key, [])
            if not options:
                missing_hotels.append(
                    {
                        "location": stay.get("location"),
                        "checkin": _date_key(stay.get("checkin")),
                        "checkout": _date_key(stay.get("checkout")),
                    }
                )
        if missing_legs or missing_hotels:
            diagnostics.append(
                {
                    "order": scenario.get("order", []),
                    "missing_legs": missing_legs,
                    "missing_hotels": missing_hotels,
                }
            )
    return diagnostics
