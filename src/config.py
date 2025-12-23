"""
Configuração central da aplicação/scraper.

Parâmetros:
- SCRAPER_MODE: controla fonte de dados dos scrapers ("mock" ou "live"). Em "live", usa Playwright.
- PLAYWRIGHT_HEADLESS: se True, navega em modo headless; útil definir False para depurar.
- PLAYWRIGHT_TIMEOUT_MS: timeout padrão de navegação/seletores do Playwright.
- KAYAK_BASE: domínio base do Kayak (use .com.br para melhor compatibilidade).
- DEFAULT_MAX_ITEMS: limite padrão de itens retornados (top N) por categoria.
- GAP_FILL_DAYS: dias máximos para preencher lacunas de hospedagem antes/depois de janelas fixas.
- LOCATIONS_FILES: lista de arquivos CSV com localidades (IATA/cidades/UF/país).
- DRIVE_DISTANCE_FACTOR: fator multiplicador para estimar distância de estrada a partir do Haversine.
- MAX_CAR_DISTANCE_KM: distância máxima (ajustada) para considerar carro; acima disso, usa apenas voo.
"""

# "mock" (usa JSONs locais) ou "live" (Playwright no Kayak)
SCRAPER_MODE = "live"

# Playwright em modo headless; defina False para ver o navegador em ação
PLAYWRIGHT_HEADLESS = False

# Timeout padrão para navegação/seletores (ms)
PLAYWRIGHT_TIMEOUT_MS = 45000

# Base do Kayak (use .com.br para melhor compatibilidade)
KAYAK_BASE = "https://www.kayak.com.br"

# Top N padrão para voos/hotéis/carros
DEFAULT_MAX_ITEMS = 5

# Dias de preenchimento de hospedagem antes/depois de janelas fixas
GAP_FILL_DAYS = 2

# Arquivos de localidades (IATA/cidade/UF/país) em CSV
LOCATIONS_FILES = [
    "data/br-airports.csv",
    "data/us-airports.csv",
]

# Fator para converter distância Haversine em estimativa de estrada (ex.: 1.2 = +20%)
DRIVE_DISTANCE_FACTOR = 1.2

# Distância máxima para considerar rota de carro (km); acima disso, não cria busca de carros
MAX_CAR_DISTANCE_KM = 800.0
