"""
Utilitários simples para logs efêmeros da execução atual.

Os logs são mantidos em memória e apagados a cada início de busca,
de modo que sempre reflitam apenas a última execução dos scrapers.
"""

_LOG_BUFFER: list[str] = []


def clear_log() -> None:
    """Limpa o buffer de log atual."""
    _LOG_BUFFER.clear()


def add_log(message: str) -> None:
    """Adiciona uma mensagem ao buffer de log."""
    _LOG_BUFFER.append(message)


def get_log() -> list[str]:
    """Retorna uma cópia das mensagens de log."""
    return list(_LOG_BUFFER)
