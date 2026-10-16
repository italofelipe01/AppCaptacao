"""Mensagens de erro exibidas ao usuario sem vazar detalhe tecnico."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

MENSAGEM_ERRO_INESPERADO = "erro inesperado; os detalhes ficaram no log técnico"


def mensagem_para_usuario(exc: Exception, contexto: str) -> str:
    """ValueError carrega regra de negocio e e mostrado; o resto vai para o log."""
    if isinstance(exc, ValueError):
        return str(exc)
    logger.error("%s", contexto, exc_info=exc)
    return MENSAGEM_ERRO_INESPERADO
