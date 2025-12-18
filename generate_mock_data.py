import pandas as pd
import numpy as np
import json

def generate_mock_data():
    # --- CENÁRIO 3: Rota Mista é a mais barata ---
    viagem_info = {
        'origem': 'VCP',
        'destino': 'GIG',
        'pessoas': 2,
        'duracao_dias': 4,
        'custo_km_rodado': 0.30 # Custo de carro baixo
    }

    # 2. Cidades e Coordenadas (Simplificadas)
    cidades = {
        'VCP': {'nome': 'Campinas (VCP)', 'lat': -23.00, 'lon': -47.13, 'tipo': 'Origem'},
        'GRU': {'nome': 'São Paulo (GRU)', 'lat': -23.43, 'lon': -46.47, 'tipo': 'Prox_Origem'},
        'CGH': {'nome': 'São Paulo (CGH)', 'lat': -23.62, 'lon': -46.65, 'tipo': 'Prox_Origem'},
        'GIG': {'nome': 'Rio de Janeiro (GIG)', 'lat': -22.81, 'lon': -43.24, 'tipo': 'Destino'},
        'SDU': {'nome': 'Rio de Janeiro (SDU)', 'lat': -22.91, 'lon': -43.16, 'tipo': 'Prox_Destino'},
        'CNF': {'nome': 'Belo Horizonte (CNF)', 'lat': -19.63, 'lon': -43.97, 'tipo': 'Prox_Destino'},
    }
    cidades_df = pd.DataFrame.from_dict(cidades, orient='index').reset_index().rename(columns={'index': 'id'})

    # 3. Distâncias Rodoviárias (em km) - Valores simulados
    distancias_carro = {
        ('VCP', 'GIG'): 600000, # Rota Rodoviária Total (Alto custo)
        ('VCP', 'GRU'): 100,
        ('VCP', 'CGH'): 120,
        ('GIG', 'SDU'): 20,
        ('GIG', 'CNF'): 450,
        ('GRU', 'SDU'): 400, # Distância para rota mista
        ('CGH', 'CNF'): 500, # Distância para rota mista
    }
    distancias_carro.update({(j, i): d for (i, j), d in distancias_carro.items() if i != j})
    distancias_df = pd.DataFrame(distancias_carro.items(), columns=['par', 'distancia_km'])
    distancias_df[['origem_id', 'destino_id']] = pd.DataFrame(distancias_df['par'].tolist(), index=distancias_df.index)
    distancias_df.drop(columns=['par'], inplace=True)

    # 4. Custos de Voo (por pessoa) - Valores simulados
    voos = {
        ('VCP', 'GIG'): 2000, # Rota Aérea Total (Muito Alto custo)
        ('GRU', 'SDU'): 100, # Rota Mista 1 (Voo muito barato)
        ('CGH', 'CNF'): 400, # Rota Mista 2
    }
    voos_df = pd.DataFrame(voos.items(), columns=['par', 'custo_voo_pessoa'])
    voos_df[['origem_id', 'destino_id']] = pd.DataFrame(voos_df['par'].tolist(), index=voos_df.index)
    voos_df.drop(columns=['par'], inplace=True)

    # 5. Hotéis no Destino e Cidades Próximas (Diária) - Valores simulados
    hoteis = [
        {'cidade_id': 'GIG', 'nome': 'Hotel GIG Econômico', 'custo_diaria': 200},
        {'cidade_id': 'GIG', 'nome': 'Hotel GIG Padrão', 'custo_diaria': 350},
    ]
    hoteis_df = pd.DataFrame(hoteis)

    # 6. Aluguel de Carros (Diária) - Valores simulados
    aluguel_carros = [
        {'cidade_id': 'VCP', 'nome': 'Locadora A VCP', 'custo_diaria': 100},
        {'cidade_id': 'GRU', 'nome': 'Locadora B GRU', 'custo_diaria': 110},
        {'cidade_id': 'CGH', 'nome': 'Locadora C CGH', 'custo_diaria': 120},
        {'cidade_id': 'GIG', 'nome': 'Locadora D GIG', 'custo_diaria': 130},
        {'cidade_id': 'SDU', 'nome': 'Locadora E SDU', 'custo_diaria': 140},
        {'cidade_id': 'CNF', 'nome': 'Locadora F CNF', 'custo_diaria': 150},
    ]
    aluguel_carros_df = pd.DataFrame(aluguel_carros)

    # Salvar os dados em arquivos JSON para fácil leitura no modelo
    with open('viagem_info.json', 'w') as f:
        json.dump(viagem_info, f, indent=4)
    
    cidades_df.to_json('cidades.json', orient='records', indent=4)
    distancias_df.to_json('distancias_carro.json', orient='records', indent=4)
    voos_df.to_json('voos.json', orient='records', indent=4)
    hoteis_df.to_json('hoteis.json', orient='records', indent=4)
    aluguel_carros_df.to_json('aluguel_carros.json', orient='records', indent=4)

    print("Mockup data generated and saved to JSON files for Scenario 3.")

if __name__ == '__main__':
    generate_mock_data()
