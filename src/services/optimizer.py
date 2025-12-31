from typing import Dict, Any, List
import pulp
import re
from src.models import SearchResponse

def _extract_duration_minutes(details: Dict[str, Any], leg: Dict[str, Any]) -> int:
    """Tenta extrair a duração do voo em minutos."""
    try:
        from datetime import datetime
        dep_str = leg.get('departure', '')
        arr_str = leg.get('arrival', '')
        
        if not dep_str or not arr_str:
            return 600

        d1 = datetime.fromisoformat(dep_str)
        d2 = datetime.fromisoformat(arr_str)
        diff = (d2 - d1).total_seconds() / 60
        return int(diff) if diff > 0 else 600
    except:
        return 600

def optimize_itinerary(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Otimiza a seleção de itens minimizando custo, duração ou ponderação.
    """
    
    trip_start_loc = data.get("meta", {}).get("trip", {}).get("start_location", "").strip().upper()
    criteria = data.get("meta", {}).get("criteria", "best")

    # --- 1. Agrupamento de Dados ---
    
    flights_by_leg: Dict[str, List[Dict]] = {}
    for f in data.get("flights", {}).get("items", []):
        leg = f["leg"]
        key = f"{leg['origin']}-{leg['destination']}-{leg['departure']}"
        if key not in flights_by_leg:
            flights_by_leg[key] = []
        flights_by_leg[key].append(f)

    hotels_by_stay: Dict[str, List[Dict]] = {}
    for h in data.get("hotels", {}).get("items", []):
        key = f"{h['city']}-{h['checkin']}-{h['checkout']}"
        if key not in hotels_by_stay:
            hotels_by_stay[key] = []
        hotels_by_stay[key].append(h)

    cars_by_block: Dict[str, List[Dict]] = {}
    for c in data.get("cars", {}).get("items", []):
        blk = c["rental_block"]
        key = f"{blk['pickup']}-{blk['dropoff']}-{blk['pickup_date']}"
        if key not in cars_by_block:
            cars_by_block[key] = []
        cars_by_block[key].append(c)

    activities_by_city: Dict[str, List[Dict]] = {}
    for act in data.get("activities", {}).get("items", []):
        c = act["city"]
        if c not in activities_by_city:
            activities_by_city[c] = []
        activities_by_city[c].append(act)

    # --- 2. Variáveis e Configuração do Solver ---
    prob = pulp.LpProblem("Travel_Optimization", pulp.LpMinimize)
    
    all_vars = [] 
    
    flight_vars = {}
    hotel_vars = {}
    car_vars = {}
    activity_vars = {}

    TIME_VALUE_PER_MINUTE = 0.50

    # --- VOOS ---
    for group_key, options in flights_by_leg.items():
        group_vars = []
        for i, opt in enumerate(options):
            var_name = f"flight_{group_key}_{i}"
            v = pulp.LpVariable(var_name, cat='Binary')
            flight_vars[var_name] = (v, opt)
            group_vars.append(v)
            
            price = opt['price']
            duration = _extract_duration_minutes(opt['details'], opt['leg'])
            
            obj_cost = 0
            if criteria == "price":
                obj_cost = price
            elif criteria == "duration":
                obj_cost = duration + (price * 0.0001)
            else: # best
                obj_cost = price + (duration * TIME_VALUE_PER_MINUTE)

            all_vars.append((v, obj_cost))
        
        prob += pulp.lpSum(group_vars) == 1, f"One_Flight_Per_Leg_{group_key}"

    # --- HOTÉIS ---
    for group_key, options in hotels_by_stay.items():
        group_vars = []
        city_code = options[0]['city'].strip().upper() if options else ""
        
        for i, opt in enumerate(options):
            var_name = f"hotel_{group_key}_{i}"
            v = pulp.LpVariable(var_name, cat='Binary')
            hotel_vars[var_name] = (v, opt)
            group_vars.append(v)
            
            all_vars.append((v, opt['price_total']))
            
        if trip_start_loc and city_code == trip_start_loc:
            home_stay_var = pulp.LpVariable(f"home_stay_{group_key}", cat='Binary')
            group_vars.append(home_stay_var)
        
        prob += pulp.lpSum(group_vars) == 1, f"One_Hotel_Per_Stay_{group_key}"

    # --- CARROS ---
    for group_key, options in cars_by_block.items():
        group_vars = []
        for i, opt in enumerate(options):
            var_name = f"car_{group_key}_{i}"
            v = pulp.LpVariable(var_name, cat='Binary')
            car_vars[var_name] = (v, opt)
            group_vars.append(v)
            all_vars.append((v, opt['price_total']))

        prob += pulp.lpSum(group_vars) == 1, f"One_Car_Per_Block_{group_key}"

    # --- ATIVIDADES ---
    for city, options in activities_by_city.items():
        group_vars = []
        for i, opt in enumerate(options):
            var_name = f"activity_{city}_{i}"
            v = pulp.LpVariable(var_name, cat='Binary')
            activity_vars[var_name] = (v, opt)
            group_vars.append(v)
            
            price = opt['price']
            duration = opt['duration_minutes']
            
            obj_cost = 0
            if criteria == "price":
                obj_cost = price
            elif criteria == "duration":
                obj_cost = duration 
            else: # best
                rating = opt.get('rating', 3.0)
                obj_cost = price - (rating * 20) 

            all_vars.append((v, obj_cost))
        
        if group_vars:
            prob += pulp.lpSum(group_vars) >= 1, f"At_Least_One_Activity_{city}"
            prob += pulp.lpSum(group_vars) <= 2, f"Max_Two_Activity_{city}"

    # --- 3. Resolver ---
    prob += pulp.lpSum([v * cost for v, cost in all_vars]), "Objective_Function"
    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    # --- 4. Coletar Resultados ---
    selected_itinerary = {
        "status": pulp.LpStatus[prob.status],
        "total_cost": 0.0, # <--- CORREÇÃO AQUI: Renomeado de total_financial_cost para total_cost
        "selected_flights": [],
        "selected_hotels": [],
        "selected_cars": [],
        "selected_activities": []
    }

    if prob.status == pulp.LpStatusOptimal:
        for v_name, (v, opt) in flight_vars.items():
            if pulp.value(v) == 1:
                selected_itinerary["selected_flights"].append(opt)
                selected_itinerary["total_cost"] += opt['price']
        
        for v_name, (v, opt) in hotel_vars.items():
            if pulp.value(v) == 1:
                selected_itinerary["selected_hotels"].append(opt)
                selected_itinerary["total_cost"] += opt['price_total']
                
        for v_name, (v, opt) in car_vars.items():
            if pulp.value(v) == 1:
                selected_itinerary["selected_cars"].append(opt)
                selected_itinerary["total_cost"] += opt['price_total']

        for v_name, (v, opt) in activity_vars.items():
            if pulp.value(v) == 1:
                selected_itinerary["selected_activities"].append(opt)
                selected_itinerary["total_cost"] += opt['price']
                
    return selected_itinerary