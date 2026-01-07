# Planejador de Viagens com Scraping (Kayak) e Otimizacao Multiobjetivo

Este documento descreve o estado atual do projeto, o fluxo de dados, e a modelagem
matematica utilizada para selecionar itinerarios viaveis e otimos com base nos
dados coletados (voos, hoteis e carros).

---

## 1. Escopo e fluxo da solucao

1) O usuario informa:
   - Local de inicio e local de termino (IATA)
   - Data minima de inicio e data maxima de termino
   - Localidades intermediarias com:
     - Janela fixa (inicio/fim) ou dias minimos
   - Viajantes (quantidade ou detalhado)

2) O sistema:
   - Gera combinacoes (ordens) para as localidades flexiveis.
   - Gera estadas (stays) e pernas (legs) por cenario.
   - Coleta opcoes em Kayak (voos, hoteis, carros).
   - Monta um JSON de entrada para o solver.
   - Executa um NSGA-II simples (sem dependencias externas).
   - Exibe as melhores solucoes e permite download dos JSONs.

---

## 2. Estrutura dos dados

### 2.1. Legs (pernas)
Cada perna e um deslocamento entre duas localidades:

```
leg = {
  origin, destination, departure, arrival,
  drive_distance_km, drive_time_hours
}
```

### 2.2. Stays (estadas)
Cada estada representa uma permanencia em uma cidade:

```
stay = {
  location, checkin, checkout, nights, type
}
```

### 2.3. Itens coletados

- Voos: associados a uma perna
- Hoteis: associados a uma estada
- Carros: associados a uma perna (pickup -> dropoff)

---

## 3. Modelagem matematica (multiobjetivo)

### 3.1. Conjuntos

L = conjunto de pernas (legs) de um cenario
S = conjunto de estadas (stays) de um cenario
F_l = conjunto de opcoes de voo disponiveis para a perna l
C_l = conjunto de opcoes de carro disponiveis para a perna l
H_s = conjunto de opcoes de hotel disponiveis para a estada s

Observacao: uma perna l possui opcoes de transporte T_l = F_l U C_l.

### 3.2. Variaveis de decisao

Para cada perna l em L e opcao k em T_l:

x_{l,k} in {0,1}  (seleciona transporte k para a perna l)

Para cada estada s em S e opcao h em H_s:

y_{s,h} in {0,1}  (seleciona hotel h para a estada s)

### 3.3. Objetivos

O problema e multiobjetivo. Os principais objetivos sao:

1) Minimizar custo total:

Min Z1 = sum_{l in L} sum_{k in T_l} cost_lk * x_{l,k}
        + sum_{s in S} sum_{h in H_s} cost_sh * y_{s,h}

2) Minimizar duracao total de transporte (voos + carros):

Min Z2 = sum_{l in L} sum_{k in T_l} duration_lk * x_{l,k}

Opcional (quando houver dados):
3) Maximizar qualidade (ex.: rating):

Max Z3 = sum_{s in S} sum_{h in H_s} rating_sh * y_{s,h}

### 3.4. Restricoes

1) Uma opcao por perna:

sum_{k in T_l} x_{l,k} = 1,  para todo l in L

2) Uma opcao por estada:

sum_{h in H_s} y_{s,h} = 1,  para todo s in S

3) Dominio:

x_{l,k} in {0,1}, y_{s,h} in {0,1}

4) Viabilidade do cenario:

Se para algum l: T_l = vazio, ou para algum s: H_s = vazio,
o cenario e inviavel e nao deve ser enviado ao solver.

### 3.5. NSGA-II

O NSGA-II opera sobre vetores de decisao:

V = [x_{l,1}, x_{l,2}, ..., y_{s,1}, y_{s,2}, ...]

Cada individuo representa uma combinacao de escolhas para todas as pernas e estadas.
O algoritmo gera uma populacao inicial, avalia objetivos, aplica selecao por
dominancia e crowding distance, e retorna o conjunto de solucoes nao dominadas.

Para ranking final, aplica-se a preferencia do usuario:
- Menor preco
- Menor duracao
- Melhor custo-beneficio (ponderacao configuravel)

---

## 4. Validacao de viabilidade

Um cenario so e valido se:
- Todas as pernas possuem pelo menos uma opcao de transporte (voo ou carro).
- Todas as estadas possuem pelo menos uma opcao de hotel.

Caso contrario, o sistema informa ausencia de solucao e lista as faltas.

---

## 5. Configuracao

Arquivo: `src/config.py`

- SCRAPER_MODE: "mock" ou "live"
- KAYAK_BASE: dominio base do Kayak
- DEFAULT_MAX_ITEMS: top N
- GAP_FILL_DAYS
- DRIVE_DISTANCE_FACTOR
- MAX_CAR_DISTANCE_KM
- NSGA_WEIGHT_COST / NSGA_WEIGHT_DURATION (custo-beneficio)

---

## 6. Uso (Streamlit)

1) Instale dependencias:
   pip install -r requirements.txt
2) Execute:
   streamlit run src/app.py
   Obs.: pode ser necessaria a instalacao do navegador chrominium para o scrapping. Utilize `playwright install`

O sistema gera:
1) JSON enviado ao solver
2) JSON com solucoes do NSGA-II

---

## 6.1 Como utilizar a aplicacao (tutorial passo-a-passo)
Siga estes passos para operar a interface e exportar resultados:

### 6.1.1. Passo-a-passo na interface
   - Preencha os campos principais:
     - Origem e destino (IATA codes).
     - Datas de inicio e fim (ou janelas flexiveis).
     - Adicione localidades intermediarias se necessario.
     - Configure viajantes (adultos/criancas) e preferencias de ordenacao.
     - Adicione possiveis localidades intermediarias no trajeto na secao Localidades. A opcao por "Janela Fixa" opta por periodo especifico de estadia enquanto que "Dias Minimos" opta por quantidade de dias na localidade. Salve cada localidade em "Salvar Localidade".
   - Clique em "Buscar opcoes" para iniciar a coleta de dados.
   - Aguarde a conclusao (a coleta live pode demorar dependendo do scrapping e do Playwright).

### 6.1.2 Visualizar e exportar resultados
   - Após a execucao, use os controles da UI para filtrar e inspecionar solucoes.
   - Baixe os JSONs gerados (entrada para o solver e solucoes) atraves dos botoes de download disponibilizados.

### 6.1.3 Dicas e solucao de problemas
   - Se o scrapper live falhar por falta de navegador, execute `playwright install` e repita.
   - Para desenvolvimento rapido, altere `src/config.py` para `SCRAPER_MODE = 'mock'` e use os mocks em `voos.json`, `hoteis.json`, `aluguel_carros.json`.
   - Aumente `PLAYWRIGHT_TIMEOUT_MS` em `src/config.py` se paginas demorarem a carregar.

### 6.1.4. Encerrando
   - Para parar a aplicacao, interrompa o processo no terminal (Ctrl+C).


## 7. Observacoes

- A representacao atual substitui o MILP original por uma abordagem multiobjetivo baseada em combinacoes de opcoes reais coletadas.
- A estrutura foi desenhada para ser consumida por um solver externo, quando necessario, mantendo o JSON como ponto de integracao.
