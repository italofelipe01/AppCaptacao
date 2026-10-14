"""Log de configuracao com o usuario autenticado da requisicao atual."""

from __future__ import annotations

from flask import g

from app_captacao.core.persistence import logs as logs_repo


def log_config(evento: str, detalhe: str, payload: dict | None = None) -> None:
    current_user = g.get("current_user")
    if not current_user:
        return
    logs_repo.registrar_log_configuracao(current_user["login"], evento, detalhe, payload)
