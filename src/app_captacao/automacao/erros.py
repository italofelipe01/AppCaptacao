"""Erros da automacao e traducao de excecoes do WebDriver para mensagem de usuario."""

from __future__ import annotations

import re

from selenium.common.exceptions import TimeoutException, WebDriverException


class DownloadProcessingError(RuntimeError):
    def __init__(self, etapa, mensagem):
        super().__init__(mensagem)
        self.etapa = etapa


class InteractiveAuthenticationRequired(RuntimeError):
    pass


def mensagem_erro_usuario(exc, fallback="Falha durante a execucao do relatorio."):
    """Remove detalhes internos do WebDriver sem perder o diagnostico nos logs."""
    mensagem = str(exc or "").strip()
    mensagem = re.split(r"\s*Stacktrace:\s*", mensagem, maxsplit=1, flags=re.IGNORECASE)[0]
    mensagem = re.sub(r"^(?:Message:\s*)+", "", mensagem, flags=re.IGNORECASE).strip()
    mensagem = " ".join(mensagem.split())
    if mensagem.lower() in {"none", "null"}:
        mensagem = ""
    if not mensagem:
        if isinstance(exc, TimeoutException):
            return "Tempo esgotado ao localizar ou preencher um campo do relatorio."
        if isinstance(exc, WebDriverException):
            return "O navegador interrompeu a automacao deste relatorio."
        return fallback
    if len(mensagem) > 280:
        mensagem = mensagem[:277].rstrip() + "..."
    return mensagem
