from typing import Dict, Any, List


DEFAULT_RATES = {
    ("USD", "USD"): 1.0,
    ("USD", "BRL"): 5.0,
    ("BRL", "USD"): 0.2,
    ("EUR", "USD"): 1.1,
    ("USD", "EUR"): 0.91,
}


def convert_currency(amount: float, source: str, target: str) -> float:
    """Converte valores entre moedas usando tabela estática simplificada.

    Args:
        amount: valor original.
        source: moeda de origem.
        target: moeda de destino.

    Returns:
        Valor convertido.
    """
    if source == target:
        return amount
    rate = DEFAULT_RATES.get((source, target))
    if rate is None:
        # Fallback: assume 1:1 quando não há mapeamento disponível
        return amount
    return amount * rate


def cap_results(items: List[Dict[str, Any]], max_items: int) -> List[Dict[str, Any]]:
    """Corta a lista para o limite máximo configurado (top N).

    Args:
        items: lista de itens.
        max_items: limite de itens.

    Returns:
        Lista limitada ao top N.
    """
    return items[:max_items]
