"""
Configuracao central da aplicacao/scraper.

Parametros:
- SCRAPER_MODE: controla fonte de dados dos scrapers ("mock" ou "live"). Em "live", usa Playwright.
- PLAYWRIGHT_HEADLESS: se True, navega em modo headless; util definir False para depurar.
- PLAYWRIGHT_TIMEOUT_MS: timeout padrao de navegacao/seletores do Playwright.
- KAYAK_BASE: dominio base do Kayak (use .com.br para melhor compatibilidade).
- DEFAULT_MAX_ITEMS: limite padrao de itens retornados (top N) por categoria.
- GAP_FILL_DAYS: dias maximos para preencher lacunas de hospedagem antes/depois de janelas fixas.
- LOCATIONS_FILES: lista de arquivos CSV com localidades (IATA/cidades/UF/pais).
- DRIVE_DISTANCE_FACTOR: fator multiplicador para estimar distancia de estrada a partir do Haversine.
- MAX_CAR_DISTANCE_KM: distancia maxima (ajustada) para considerar carro; acima disso, usa apenas voo.
- AVG_DRIVE_SPEED_KMH: velocidade media para estimar tempo de carro.
- CAR_FUEL_COST_PER_KM: custo de combustivel por km para estimar custo total do carro.
- NSGA_MAX_SOLUTIONS: numero maximo de solucoes retornadas pelo NSGA-II.
"""

# "mock" (usa JSONs locais) ou "live" (Playwright no Kayak)
SCRAPER_MODE = "live"

# Playwright em modo headless; defina False para ver o navegador em acao
PLAYWRIGHT_HEADLESS = False

# Timeout padrao para navegacao/seletores (ms)
PLAYWRIGHT_TIMEOUT_MS = 60000

# Base do Kayak (use .com.br para melhor compatibilidade)
KAYAK_BASE = "https://www.kayak.com.br"

# Top N padrao para voos/hoteis/carros
DEFAULT_MAX_ITEMS = 5

# Dias de preenchimento de hospedagem antes/depois de janelas fixas
GAP_FILL_DAYS = 2

# Arquivos de localidades (IATA/cidade/UF/pais) em CSV
LOCATIONS_FILES = [
    "data/br-airports.csv",
    "data/us-airports.csv",
]

# Fator para converter distancia Haversine em estimativa de estrada (ex.: 1.2 = +20%)
DRIVE_DISTANCE_FACTOR = 1.2

# Distancia maxima para considerar rota de carro (km); acima disso, nao cria busca de carros
MAX_CAR_DISTANCE_KM = 800.0

# Pesos para ranking 'Melhor Custo-Beneficio' do NSGA-II (somatorio deve ser 1.0)
NSGA_WEIGHT_COST = 0.5
NSGA_WEIGHT_DURATION = 0.5

# Velocidade media para estimar tempo de carro (km/h)
AVG_DRIVE_SPEED_KMH = 80.0

# Custo de combustivel por km (BRL)
CAR_FUEL_COST_PER_KM = 0.5

# Numero maximo de solucoes retornadas pelo NSGA-II
NSGA_MAX_SOLUTIONS = 3
