"""
Configuração central da aplicação/scraper.

Parâmetros:
- SCRAPER_MODE: controla fonte de dados dos scrapers ("mock" ou "live"). Em "live", usa Playwright.
- PLAYWRIGHT_HEADLESS: se True, navega em modo headless; útil definir False para depurar.
- DEFAULT_MAX_ITEMS: limite padrão de itens retornados (top N) por categoria.
- GAP_FILL_DAYS: dias máximos para preencher lacunas de hospedagem antes/depois de janelas fixas.
- LOCATIONS_FILES: lista de arquivos CSV com localidades (IATA/cidades/UF/país).
- DRIVE_DISTANCE_FACTOR: fator multiplicador para estimar distância de estrada a partir do Haversine.
"""

# "mock" (usa JSONs locais) ou "live" (Playwright no Kayak)
SCRAPER_MODE = "mock"

# Playwright em modo headless; defina False para ver o navegador em ação
PLAYWRIGHT_HEADLESS = True

# Top N padrão para voos/hotéis/carros
DEFAULT_MAX_ITEMS = 20

# Dias de preenchimento de hospedagem antes/depois de janelas fixas
GAP_FILL_DAYS = 2

# Arquivos de localidades (IATA/cidade/UF/país) em CSV
LOCATIONS_FILES = [
    "data/br-airports.csv",
    "data/us-airports.csv",
]

# Fator para converter distância Haversine em estimativa de estrada (ex.: 1.2 = +20%)
DRIVE_DISTANCE_FACTOR = 1.2
