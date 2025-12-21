"""Utilidades geográficas (distância e tempo estimado)."""

import math
from typing import Optional, Tuple

from src import config

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância Haversine em km entre dois pontos (graus decimais).

    Args:
        lat1: latitude ponto 1.
        lon1: longitude ponto 1.
        lat2: latitude ponto 2.
        lon2: longitude ponto 2.
    Returns:
        Distância em quilômetros.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def estimate_drive_time_hours(distance_km: float, avg_speed_kmh: float = 80.0) -> float:
    """Estimativa simples de tempo de carro (horas) dada distância e velocidade média.

    Args:
        distance_km: distância em quilômetros.
        avg_speed_kmh: velocidade média em km/h.
    Returns:
        Tempo estimado em horas.
    """
    if avg_speed_kmh <= 0:
        return 0.0
    return distance_km / avg_speed_kmh


def drive_distance_and_time(latlon1: Tuple[float, float], latlon2: Tuple[float, float], avg_speed_kmh: float = 80.0):
    """Retorna distância (km) e tempo estimado (horas) para um trajeto de carro (Haversine ajustado).

    Args:
        latlon1: (lat, lon) origem.
        latlon2: (lat, lon) destino.
        avg_speed_kmh: velocidade média considerada.
    Returns:
        Tupla (distância km ajustada, tempo horas).
    """
    d_km = haversine_km(latlon1[0], latlon1[1], latlon2[0], latlon2[1]) * config.DRIVE_DISTANCE_FACTOR
    t_h = estimate_drive_time_hours(d_km, avg_speed_kmh)
    return d_km, t_h
