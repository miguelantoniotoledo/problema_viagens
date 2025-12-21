"""Autocomplete local para cidades/aeroportos (BR/US) a partir de CSVs."""

import csv
from functools import lru_cache
from typing import List, Dict

from src import config


@lru_cache(maxsize=1)
def load_locations() -> List[Dict]:
    """Carrega lista de localidades (IATA/cidade/estado/país) dos CSVs configurados."""
    locations: List[Dict] = []
    for file_path in config.LOCATIONS_FILES:
        try:
            with open(file_path, newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    # Normaliza campos conforme presença
                    code = row.get("IATA") or row.get("iata_code") or row.get("iata")
                    if not code:
                        continue
                    country = row.get("Country_CodeA2") or row.get("iso_country") or ""
                    if country not in ("US", "BR"):
                        continue
                    city = row.get("City_Name") or row.get("municipality") or row.get("city") or ""
                    state = row.get("iso_region", "")
                    if state and "-" in state:
                        state = state.split("-")[-1]
                    state = row.get("region_name") or row.get("local_region") or state
                    lat = row.get("GeoPointLat") or row.get("latitude_deg")
                    lng = row.get("GeoPointLong") or row.get("longitude_deg")
                    loc_type = row.get("type") or row.get("type_airport") or "airport"
                    locations.append(
                        {
                            "code": code.strip().upper(),
                            "name": row.get("AirportName") or row.get("name") or "",
                            "city": city,
                            "state": state,
                            "country": country,
                            "type": loc_type,
                            "lat": lat,
                            "lng": lng,
                        }
                    )
        except FileNotFoundError:
            continue
    return locations


def search_locations(query: str, limit: int = 10) -> List[Dict]:
    """Filtra localidades por código/nome/cidade/UF.

    Args:
        query: termo de busca (case-insensitive).
        limit: quantidade máxima de resultados.
    Returns:
        Lista de dicionários com match.
    """
    q = (query or "").strip().lower()
    if not q:
        return load_locations()[:limit]
    results = []
    for loc in load_locations():
        text = " ".join(
            [
                loc.get("code", ""),
                loc.get("name", ""),
                loc.get("city", ""),
                loc.get("state", ""),
                loc.get("country", ""),
            ]
        ).lower()
        if q in text:
            results.append(loc)
        if len(results) >= limit:
            break
    return results
