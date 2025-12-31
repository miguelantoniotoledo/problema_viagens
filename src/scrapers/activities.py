import random
from typing import List, Dict, Any

def scrape_activities(city_code: str, currency: str) -> List[Dict[str, Any]]:
    """
    Gera sugestões de atividades baseadas no código da cidade (Mock).
    """
    activities = []
    
    # Base de dados Mock de atividades
    mock_db = {
        "MIA": [
            {"name": "Passeio de Barco em Biscayne Bay", "price": 150.0, "duration": 90, "rating": 4.5, "cat": "relax"},
            {"name": "Tour Art Deco em South Beach", "price": 0.0, "duration": 60, "rating": 4.0, "cat": "culture"},
            {"name": "Everglades Airboat Tour", "price": 300.0, "duration": 240, "rating": 4.8, "cat": "adventure"},
            {"name": "Wynwood Walls", "price": 60.0, "duration": 120, "rating": 4.7, "cat": "culture"},
        ],
        "ORL": [
            {"name": "Ingresso Magic Kingdom", "price": 800.0, "duration": 600, "rating": 5.0, "cat": "adventure"},
            {"name": "Universal Studios Park", "price": 750.0, "duration": 600, "rating": 4.9, "cat": "adventure"},
            {"name": "Compras no Premium Outlet", "price": 0.0, "duration": 180, "rating": 4.2, "cat": "relax"},
            {"name": "Icon Park Wheel", "price": 150.0, "duration": 45, "rating": 4.0, "cat": "relax"},
        ],
        "NYC": [
            {"name": "Estátua da Liberdade", "price": 120.0, "duration": 180, "rating": 4.8, "cat": "culture"},
            {"name": "Central Park Bike Rental", "price": 80.0, "duration": 120, "rating": 4.5, "cat": "relax"},
            {"name": "Empire State Building", "price": 200.0, "duration": 90, "rating": 4.6, "cat": "culture"},
        ],
        "GYN": [
            {"name": "Feira da Lua", "price": 0.0, "duration": 120, "rating": 4.5, "cat": "culture"},
            {"name": "Parque Flamboyant", "price": 0.0, "duration": 60, "rating": 4.8, "cat": "relax"},
        ]
    }

    city_data = mock_db.get(city_code, [])
    
    # Se não tiver dados específicos, gera genéricos
    if not city_data:
        city_data = [
            {"name": f"City Tour em {city_code}", "price": 100.0, "duration": 120, "rating": 4.0, "cat": "culture"},
            {"name": f"Museu Local de {city_code}", "price": 50.0, "duration": 90, "rating": 3.8, "cat": "culture"},
        ]

    for item in city_data:
        activities.append({
            "name": item["name"],
            "city": city_code,
            "price": item["price"],
            "duration_minutes": item["duration"],
            "rating": item["rating"],
            "category": item["cat"],
            "currency": currency,
            # Campo auxiliar para exibição
            "display_price": f"R$ {item['price']:.2f}" if item['price'] > 0 else "Grátis"
        })
        
    return activities