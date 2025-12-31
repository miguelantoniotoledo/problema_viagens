from typing import Dict, Any, List
import pulp
from src.models import SearchResponse

def optimize_itinerary(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Otimiza a seleção de voos, hotéis e carros para minimizar o custo total.
    
    Args:
        data: Dicionário contendo as listas de candidatos (flights, hotels, cars) 
              e metadados da busca (estrutura similar ao JSON de SearchResponse).
              
    Returns:
        Um dicionário com os itens selecionados e o custo total.
    """
    
    # 1. Preparação dos dados
    # Recupera a cidade de origem para tratar hospedagem local como opcional
    trip_start_loc = data.get("meta", {}).get("trip", {}).get("start_location", "").strip().upper()

    # Agrupar voos por perna (leg)
    flights_by_leg: Dict[str, List[Dict]] = {}
    for f in data.get("flights", {}).get("items", []):
        leg = f["leg"]
        key = f"{leg['origin']}-{leg['destination']}-{leg['departure']}"
        if key not in flights_by_leg:
            flights_by_leg[key] = []
        flights_by_leg[key].append(f)

    # Agrupar hotéis por estadia
    hotels_by_stay: Dict[str, List[Dict]] = {}
    for h in data.get("hotels", {}).get("items", []):
        key = f"{h['city']}-{h['checkin']}-{h['checkout']}"
        if key not in hotels_by_stay:
            hotels_by_stay[key] = []
        hotels_by_stay[key].append(h)

    # Agrupar carros por bloco de aluguel
    cars_by_block: Dict[str, List[Dict]] = {}
    for c in data.get("cars", {}).get("items", []):
        blk = c["rental_block"]
        key = f"{blk['pickup']}-{blk['dropoff']}-{blk['pickup_date']}"
        if key not in cars_by_block:
            cars_by_block[key] = []
        cars_by_block[key].append(c)

    # 2. Definição do Problema de Otimização
    prob = pulp.LpProblem("Travel_Optimization", pulp.LpMinimize)
    
    flight_vars = {}
    hotel_vars = {}
    car_vars = {}
    
    all_vars = [] # Lista auxiliar para função objetivo

    # Criar variáveis para Voos
    for group_key, options in flights_by_leg.items():
        group_vars = []
        for i, opt in enumerate(options):
            var_name = f"flight_{group_key}_{i}"
            v = pulp.LpVariable(var_name, cat='Binary')
            flight_vars[var_name] = (v, opt)
            group_vars.append(v)
            all_vars.append((v, opt['price']))
        
        # Restrição: Escolher EXATAMENTE UM voo por perna
        prob += pulp.lpSum(group_vars) == 1, f"One_Flight_Per_Leg_{group_key}"

    # Criar variáveis para Hotéis
    for group_key, options in hotels_by_stay.items():
        group_vars = []
        city_code = options[0]['city'].strip().upper() if options else ""
        
        for i, opt in enumerate(options):
            var_name = f"hotel_{group_key}_{i}"
            v = pulp.LpVariable(var_name, cat='Binary')
            hotel_vars[var_name] = (v, opt)
            group_vars.append(v)
            all_vars.append((v, opt['price_total']))
            
        # LÓGICA DE "CASA": Se a cidade do hotel for a mesma da origem da viagem,
        # adicionamos uma opção fantasma "Dormir em casa" com custo 0.
        if trip_start_loc and city_code == trip_start_loc:
            home_stay_var = pulp.LpVariable(f"home_stay_{group_key}", cat='Binary')
            group_vars.append(home_stay_var)
            # Não adicionamos home_stay_var em all_vars pois o custo é 0
            
        # Restrição: Escolher EXATAMENTE UM hotel (ou casa) por estadia
        prob += pulp.lpSum(group_vars) == 1, f"One_Hotel_Per_Stay_{group_key}"

    # Criar variáveis para Carros
    for group_key, options in cars_by_block.items():
        group_vars = []
        for i, opt in enumerate(options):
            var_name = f"car_{group_key}_{i}"
            v = pulp.LpVariable(var_name, cat='Binary')
            car_vars[var_name] = (v, opt)
            group_vars.append(v)
            all_vars.append((v, opt['price_total']))

        # Restrição: Escolher EXATAMENTE UM carro por bloco (se houver opções)
        prob += pulp.lpSum(group_vars) == 1, f"One_Car_Per_Block_{group_key}"

    # 3. Função Objetivo: Minimizar Custo Total
    prob += pulp.lpSum([v * price for v, price in all_vars]), "Total_Cost"

    # 4. Resolver
    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    # 5. Coletar Resultados
    selected_itinerary = {
        "status": pulp.LpStatus[prob.status],
        "total_cost": pulp.value(prob.objective),
        "selected_flights": [],
        "selected_hotels": [],
        "selected_cars": []
    }

    if prob.status == pulp.LpStatusOptimal:
        for v_name, (v, opt) in flight_vars.items():
            if pulp.value(v) == 1:
                selected_itinerary["selected_flights"].append(opt)
        
        for v_name, (v, opt) in hotel_vars.items():
            if pulp.value(v) == 1:
                selected_itinerary["selected_hotels"].append(opt)
                
        for v_name, (v, opt) in car_vars.items():
            if pulp.value(v) == 1:
                selected_itinerary["selected_cars"].append(opt)
                
    return selected_itinerary