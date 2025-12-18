# Formulação Matemática do Modelo de Programação Linear para Otimização de Viagens

O objetivo deste modelo é **minimizar o custo total** de uma viagem, $C_{total}$, escolhendo a rota mais econômica entre as três opções principais: Aérea Total, Rodoviária Total e Mista (Parcialmente Aérea).

## 1. Conjuntos e Parâmetros

| Símbolo | Descrição | Unidade |
| :--- | :--- | :--- |
| $O$ | Cidade de Origem | - |
| $D$ | Cidade de Destino | - |
| $C_O$ | Conjunto de cidades próximas à Origem $O$ | - |
| $C_D$ | Conjunto de cidades próximas ao Destino $D$ | - |
| $H_O$ | Conjunto de hotéis em $C_O$ | - |
| $H_D$ | Conjunto de hotéis em $C_D$ | - |
| $R_O$ | Conjunto de locadoras de carro em $C_O$ | - |
| $R_D$ | Conjunto de locadoras de carro em $C_D$ | - |
| $N$ | Quantidade de pessoas na viagem | Pessoas |
| $T$ | Duração da viagem (dias) | Dias |
| $C_{voo}(i, j)$ | Custo do voo entre a cidade $i$ e a cidade $j$ (por pessoa) | R\$ |
| $C_{dist}(i, j)$ | Distância rodoviária entre a cidade $i$ e a cidade $j$ | km |
| $C_{comb}$ | Custo por km rodado (combustível + manutenção) | R\$/km |
| $C_{hosp}(h)$ | Custo da diária do hotel $h$ (por noite) | R\$ |
| $C_{aluguel}(r)$ | Custo da diária do aluguel de carro na locadora $r$ | R\$/dia |

## 2. Variáveis de Decisão (Binárias)

As variáveis de decisão são binárias, indicando se uma determinada opção de rota ou sub-opção é escolhida (1) ou não (0).

### Escolha da Rota Principal
| Variável | Descrição |
| :--- | :--- |
| $y_{A}$ | 1 se a rota **Aérea Total** for escolhida. |
| $y_{R}$ | 1 se a rota **Rodoviária Total** for escolhida. |
| $y_{M}$ | 1 se a rota **Mista (Parcialmente Aérea)** for escolhida. |

### Sub-escolhas para a Rota Mista
A rota mista é definida como: Carro $O \to c_O$ + Avião $c_O \to c_D$ + Carro $c_D \to D$.
| Variável | Descrição |
| :--- | :--- |
| $x_{c_O}$ | 1 se a cidade $c_O \in C_O$ for escolhida como ponto de partida aéreo. |
| $x_{c_D}$ | 1 se a cidade $c_D \in C_D$ for escolhida como ponto de chegada aéreo. |

### Escolhas de Hospedagem e Aluguel
| Variável | Descrição |
| :--- | :--- |
| $z_{h_D}$ | 1 se o hotel $h_D \in H_D$ for escolhido para hospedagem no destino. |
| $w_{r_O}$ | 1 se a locadora $r_O \in R_O$ for escolhida para aluguel de carro na origem (para rotas Rodoviária Total ou Mista). |
| $w_{r_D}$ | 1 se a locadora $r_D \in R_D$ for escolhida para aluguel de carro no destino (para rota Mista). |

## 3. Função Objetivo

Minimizar o custo total da viagem, que é a soma dos custos de transporte, hospedagem e aluguel de carro.

$$
\text{Minimizar } C_{total} = C_{transporte} + C_{hospedagem} + C_{aluguel}
$$

### Custo de Transporte ($C_{transporte}$)

$$
C_{transporte} = \left( \sum_{i \in C_O} \sum_{j \in C_D} C_{voo}(i, j) \cdot N \cdot x_{i} \cdot x_{j} \cdot y_{M} \right) + \left( C_{voo}(O, D) \cdot N \cdot y_{A} \right) + \left( C_{dist}(O, D) \cdot C_{comb} \cdot y_{R} \right)
$$

*   **Nota:** Para manter a linearidade, o termo $x_{i} \cdot x_{j} \cdot y_{M}$ deve ser substituído por uma variável auxiliar $v_{i, j}$ e restrições de linearização (Big M), mas para simplificar a demonstração conceitual, vamos assumir que a escolha de $c_O$ e $c_D$ é mutuamente exclusiva e que o custo total da rota mista é pré-calculado ou tratado com restrições de implicação.

### Custo de Hospedagem ($C_{hospedagem}$)

O custo de hospedagem é aplicado apenas no destino $D$ (ou $c_D$) e é o mesmo para todas as rotas.

$$
C_{hospedagem} = \sum_{h_D \in H_D} C_{hosp}(h_D) \cdot T \cdot z_{h_D}
$$

### Custo de Aluguel ($C_{aluguel}$)

O custo de aluguel depende da rota escolhida.

$$
C_{aluguel} = \left( \sum_{r_O \in R_O} C_{aluguel}(r_O) \cdot T \cdot w_{r_O} \cdot y_{R} \right) + \left( \sum_{r_D \in R_D} C_{aluguel}(r_D) \cdot T \cdot w_{r_D} \cdot y_{M} \right)
$$

*   **Nota:** O aluguel de carro na rota Rodoviária Total ($y_R$) é considerado na origem $O$ (ou $c_O$ mais próxima), e na rota Mista ($y_M$) é considerado no destino aéreo $c_D$.

## 4. Restrições

### R1: Escolha de Rota Principal
Apenas uma rota principal pode ser escolhida.
$$
y_{A} + y_{R} + y_{M} = 1
$$

### R2: Escolha de Cidade Próxima (Rota Mista)
Se a rota Mista ($y_M$) for escolhida, exatamente uma cidade $c_O$ e uma cidade $c_D$ devem ser escolhidas como pontos de conexão aérea.
$$
\sum_{c_O \in C_O} x_{c_O} = y_{M}
$$
$$
\sum_{c_D \in C_D} x_{c_D} = y_{M}
$$

### R3: Escolha de Hospedagem
Exatamente um hotel no destino deve ser escolhido.
$$
\sum_{h_D \in H_D} z_{h_D} = 1
$$

### R4: Escolha de Aluguel de Carro (Origem)
Se a rota Rodoviária Total ($y_R$) for escolhida, exatamente uma locadora $r_O$ deve ser escolhida.
$$
\sum_{r_O \in R_O} w_{r_O} = y_{R}
$$

### R5: Escolha de Aluguel de Carro (Destino)
Se a rota Mista ($y_M$) for escolhida, exatamente uma locadora $r_D$ deve ser escolhida no destino aéreo.
$$
\sum_{r_D \in R_D} w_{r_D} = y_{M}
$$

### R6: Restrições de Variáveis Binárias
Todas as variáveis de decisão são binárias.
$$
y_{A}, y_{R}, y_{M}, x_{c_O}, x_{c_D}, z_{h_D}, w_{r_O}, w_{r_D} \in \{0, 1\}
$$

## 5. Linearização do Custo de Transporte (Avançado)

Para garantir a linearidade da Função Objetivo, o termo de custo da Rota Mista deve ser reescrito.

Seja $C_{M}(c_O, c_D)$ o custo total da rota mista que passa por $c_O$ e $c_D$:
$$
C_{M}(c_O, c_D) = \left( C_{dist}(O, c_O) \cdot C_{comb} \right) + \left( C_{voo}(c_O, c_D) \cdot N \right) + \left( C_{dist}(c_D, D) \cdot C_{comb} \right)
$$

Definimos uma nova variável binária $v_{c_O, c_D}$ que é 1 se a rota mista for escolhida **E** passar por $c_O$ e $c_D$.

$$
v_{c_O, c_D} \in \{0, 1\} \quad \forall c_O \in C_O, c_D \in C_D
$$

**Restrições de Implicação (Big M):**
$$
v_{c_O, c_D} \le x_{c_O} \quad \forall c_O, c_D
$$
$$
v_{c_O, c_D} \le x_{c_D} \quad \forall c_O, c_D
$$
$$
v_{c_O, c_D} \ge x_{c_O} + x_{c_D} - 1 \quad \forall c_O, c_D
$$
$$
\sum_{c_O \in C_O} \sum_{c_D \in C_D} v_{c_O, c_D} = y_{M}
$$

**Função Objetivo Linearizada:**
$$
\text{Minimizar } C_{total} = \left( \sum_{c_O \in C_O} \sum_{c_D \in C_D} C_{M}(c_O, c_D) \cdot v_{c_O, c_D} \right) + \left( C_{voo}(O, D) \cdot N \cdot y_{A} \right) + \left( C_{dist}(O, D) \cdot C_{comb} \cdot y_{R} \right) + C_{hospedagem} + C_{aluguel}
$$

Esta formulação garante que o problema seja resolvido como um **Problema de Programação Linear Inteira Mista (MILP)**, encontrando a combinação de rota e sub-opções que minimiza o custo total.
