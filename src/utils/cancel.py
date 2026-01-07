"""Controle simples de cancelamento para buscas longas."""

_cancel_requested = False


def request_cancel() -> None:
    """Solicita o cancelamento da busca atual."""
    global _cancel_requested
    _cancel_requested = True


def clear_cancel() -> None:
    """Limpa a solicitacao de cancelamento."""
    global _cancel_requested
    _cancel_requested = False


def is_cancelled() -> bool:
    """Indica se houve solicitacao de cancelamento."""
    return _cancel_requested
