from typing import Dict, Any, List


DEFAULT_RATES = {
    ("USD", "USD"): 1.0,
    ("USD", "BRL"): 5.0,
    ("BRL", "USD"): 0.2,
    ("EUR", "USD"): 1.1,
    ("USD", "EUR"): 0.91,
}


def convert_currency(amount: float, source: str, target: str) -> float:
    if source == target:
        return amount
    rate = DEFAULT_RATES.get((source, target))
    if rate is None:
        # Fallback: assume 1:1 when no mapping is available
        return amount
    return amount * rate


def cap_results(items: List[Dict[str, Any]], max_items: int) -> List[Dict[str, Any]]:
    return items[:max_items]

