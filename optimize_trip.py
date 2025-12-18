import pandas as pd
import json
import numpy as np

# --- 1. Funções de Carregamento de Dados ---

def load_data():
    """Carrega os dados simulados dos arquivos JSON."""
    try:
        with open('viagem_info.json', 'r') as f:
            viagem_info = json.load(f)
        
        cidades_df = pd.read_json('cidades.json')
        distancias_df = pd.read_json('distancias_carro.json')
        voos_df = pd.read_json('voos.json')
        hoteis_df = pd.read_json('hoteis.json')
        aluguel_carros_df = pd.read_json('aluguel_carros.json')
        
        return viagem_info, cidades_df, distancias_df, voos_df, hoteis_df, aluguel_carros_df
    except FileNotFoundError as e:
        print(f"Erro ao carregar dados: {e}")
        exit()

# --- 2. Funções Auxiliares de Custo ---

def get_distancia(origem, destino, distancias_df):
    """Retorna a distância rodoviária entre duas cidades."""
    try:
        return distancias_df[
            ((distancias_df['origem_id'] == origem) & (distancias_df['destino_id'] == destino)) |
            ((distancias_df['origem_id'] == destino) & (distancias_df['destino_id'] == origem))
        ]['distancia_km'].iloc[0]
    except IndexError:
        return np.inf # Distância infinita se não houver rota

def get_custo_voo(origem, destino, voos_df):
    """Retorna o custo do voo por pessoa entre duas cidades."""
    try:
        return voos_df[
            (voos_df['origem_id'] == origem) & (voos_df['destino_id'] == destino)
        ]['custo_voo_pessoa'].iloc[0]
    except IndexError:
        return np.inf # Custo infinito se não houver voo

def get_custo_hospedagem(hotel_id, hoteis_df, duracao_dias):
    """Retorna o custo total da hospedagem no hotel escolhido."""
    return hoteis_df.loc[hotel_id, 'custo_diaria'] * duracao_dias

def get_custo_aluguel(aluguel_id, aluguel_carros_df, duracao_dias):
    """Retorna o custo total do aluguel de carro escolhido."""
    return aluguel_carros_df.loc[aluguel_id, 'custo_diaria'] * duracao_dias

# --- 3. Função de Otimização (Busca Combinatória) ---

def optimize_trip(viagem_info, cidades_df, distancias_df, voos_df, hoteis_df, aluguel_carros_df):
    """
    Implementa a busca combinatória para encontrar a rota de custo mínimo.
    Esta abordagem simula a solução de um MILP (Programação Linear Inteira Mista)
    para um conjunto discreto e pequeno de opções.
    """
    
    O = viagem_info['origem']
    D = viagem_info['destino']
    N = viagem_info['pessoas']
    T = viagem_info['duracao_dias']
    C_comb = viagem_info['custo_km_rodado']
    
    # Identificar os conjuntos de cidades e serviços
    # Não é necessário setar o index para a busca combinatória, 
    # mas vamos garantir que os IDs de serviço sejam os índices para acesso rápido
    hoteis_df['hotel_id'] = hoteis_df.index
    hoteis_df.set_index('hotel_id', inplace=True)
    aluguel_carros_df['aluguel_id'] = aluguel_carros_df.index
    aluguel_carros_df.set_index('aluguel_id', inplace=True)

    C_O = cidades_df[cidades_df['tipo'] == 'Prox_Origem'].index.tolist()
    C_D = cidades_df[cidades_df['tipo'] == 'Prox_Destino'].index.tolist()
    H_D_ids = hoteis_df[hoteis_df['cidade_id'] == D].index.tolist()
    R_O_ids = aluguel_carros_df[aluguel_carros_df['cidade_id'].isin([O] + C_O)].index.tolist()
    R_D_ids = aluguel_carros_df[aluguel_carros_df['cidade_id'].isin(C_D)].index.tolist()

    melhor_custo = np.inf
    melhor_rota = None
    
    # ----------------------------------------------------------------------
    # 3.1. Rota Aérea Total (y_A = 1)
    # Custo = Custo Voo (O->D) * N + Custo Hospedagem
    # ----------------------------------------------------------------------
    custo_voo_total = get_custo_voo(O, D, voos_df) * N
    
    for h_id in H_D_ids:
        custo_hosp = get_custo_hospedagem(h_id, hoteis_df, T)
        custo_total = custo_voo_total + custo_hosp
        
        if custo_total < melhor_custo:
            melhor_custo = float(custo_total)
            melhor_rota = {
                'tipo': 'Aérea Total',
                'custo_total': float(custo_total),
                'detalhes': {
                    'voo': f'{O} -> {D}',
                    'custo_voo': float(custo_voo_total),
                    'hospedagem': hoteis_df.loc[h_id, 'nome'],
                    'custo_hospedagem': float(custo_hosp)
                }
            }

    # ----------------------------------------------------------------------
    # 3.2. Rota Rodoviária Total (y_R = 1)
    # Custo = Distância (O->D) * C_comb + Custo Hospedagem + Custo Aluguel (O)
    # ----------------------------------------------------------------------
    dist_total = get_distancia(O, D, distancias_df)
    custo_carro_total = dist_total * C_comb
    
    for h_id in H_D_ids:
        for r_id in R_O_ids:
            custo_hosp = get_custo_hospedagem(h_id, hoteis_df, T)
            custo_aluguel = get_custo_aluguel(r_id, aluguel_carros_df, T)
            custo_total = custo_carro_total + custo_hosp + custo_aluguel
            
            if custo_total < melhor_custo:
                melhor_custo = float(custo_total)
                melhor_rota = {
                    'tipo': 'Rodoviária Total',
                    'custo_total': float(custo_total),
                    'detalhes': {
                        'trajeto': f'{O} -> {D}',
                        'custo_carro': float(custo_carro_total),
                        'hospedagem': hoteis_df.loc[h_id, 'nome'],
                        'custo_hospedagem': float(custo_hosp),
                        'aluguel_carro': aluguel_carros_df.loc[r_id, 'nome'],
                        'custo_aluguel': float(custo_aluguel)
                    }
                }

    # ----------------------------------------------------------------------
    # 3.3. Rota Mista (y_M = 1)
    # Custo = Carro (O->c_O) + Voo (c_O->c_D) * N + Carro (c_D->D) + Hospedagem + Aluguel (c_D)
    # ----------------------------------------------------------------------
    for c_O in C_O:
        for c_D in C_D:
            # Custo do Voo (c_O -> c_D)
            custo_voo_misto = get_custo_voo(c_O, c_D, voos_df) * N
            if custo_voo_misto == np.inf:
                continue # Rota aérea mista inviável
            
            # Custo do Carro 1 (O -> c_O)
            dist_carro_1 = get_distancia(O, c_O, distancias_df)
            custo_carro_1 = dist_carro_1 * C_comb
            
            # Custo do Carro 2 (c_D -> D)
            dist_carro_2 = get_distancia(c_D, D, distancias_df)
            custo_carro_2 = dist_carro_2 * C_comb
            
            custo_transporte_misto = custo_voo_misto + custo_carro_1 + custo_carro_2
            
            # Busca por Hospedagem e Aluguel
            for h_id in H_D_ids:
                for r_id in R_D_ids:
                    # Verifica se a locadora é na cidade de chegada aérea (c_D) ou no destino final (D)
                    if aluguel_carros_df.loc[r_id, 'cidade_id'] != c_D:
                        continue
                        
                    custo_hosp = get_custo_hospedagem(h_id, hoteis_df, T)
                    custo_aluguel = get_custo_aluguel(r_id, aluguel_carros_df, T)
                    
                    custo_total = custo_transporte_misto + custo_hosp + custo_aluguel
                    
                    if custo_total < melhor_custo:
                        melhor_custo = float(custo_total)
                        melhor_rota = {
                            'tipo': 'Mista',
                            'custo_total': float(custo_total),
                            'detalhes': {
                                'trajeto_carro_ida': f'{O} -> {c_O}',
                                'trajeto_voo': f'{c_O} -> {c_D}',
                                'trajeto_carro_volta': f'{c_D} -> {D}',
                                'custo_transporte': float(custo_transporte_misto),
                                'hospedagem': hoteis_df.loc[h_id, 'nome'],
                                'custo_hospedagem': float(custo_hosp),
                                'aluguel_carro': aluguel_carros_df.loc[r_id, 'nome'],
                                'custo_aluguel': float(custo_aluguel)
                            }
                        }

    return melhor_rota

# --- 4. Execução Principal ---

if __name__ == '__main__':
    viagem_info, cidades_df, distancias_df, voos_df, hoteis_df, aluguel_carros_df = load_data()
    
    print("--- Dados da Viagem ---")
    print(json.dumps(viagem_info, indent=4))
    print("\n--- Iniciando Otimização ---")
    
    resultado = optimize_trip(viagem_info, cidades_df, distancias_df, voos_df, hoteis_df, aluguel_carros_df)
    
    print("\n--- Resultado da Otimização ---")
    if resultado:
        print(f"Rota Ótima: {resultado['tipo']}")
        print(f"Custo Total Mínimo: R$ {resultado['custo_total']:.2f}")
        print("\nDetalhes:")
        print(json.dumps(resultado['detalhes'], indent=4))
    else:
        print("Nenhuma rota viável encontrada.")
