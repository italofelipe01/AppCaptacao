r"""Log tecnico em arquivo rotativo, para diagnosticar falhas da automacao.

Grava INFO ou mais grave de todos os modulos app_captacao.* em
%LOCALAPPDATA%\AppCaptacao\logs\appcaptacao.log (o atual e mais 5 de 5 MB). O console
(janela do Iniciar AppCaptacao.bat) mostra as mesmas etapas, com a hora e os
marcadores do checklist.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app_captacao.core.config.environment import get_writable_state_dir

FORMATO = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
FORMATO_CONSOLE = "%(asctime)s %(marcador)s %(message)s"
TAMANHO_MAXIMO_BYTES = 5 * 1024 * 1024
ARQUIVOS_MANTIDOS = 5

_MARCADORES = {logging.INFO: "[INFO ]", logging.WARNING: "[AVISO]"}

_handlers: list[logging.Handler] = []


class _MarcadorDoChecklist(logging.Filter):
    """Troca o nivel do log pelo marcador usado no checklist do run.py."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno >= logging.ERROR:
            record.marcador = "[ERRO ]"
        else:
            record.marcador = _MARCADORES.get(record.levelno, f"[{record.levelname[:5]:<5}]")
        return True


class _FormatoConsole(logging.Formatter):
    """Console sem traceback: so o tipo e a primeira linha do erro. O arquivo guarda o resto."""

    def format(self, record: logging.LogRecord) -> str:
        if not record.exc_info:
            return super().format(record)
        resumo = record.exc_info[1]
        primeira_linha = str(resumo or "").strip().splitlines()[0] if str(resumo or "").strip() else ""
        copia = logging.makeLogRecord(record.__dict__)
        copia.msg = f"{record.getMessage()} ({type(resumo).__name__}: {primeira_linha.removeprefix('Message: ')})"
        copia.args = None
        copia.exc_info = None
        copia.exc_text = None
        return super().format(copia)


def pasta_de_logs() -> Path:
    return get_writable_state_dir().parent / "logs"


def configurar_log_tecnico(console: bool = True) -> Path:
    """Liga o log do pacote app_captacao; chamadas repetidas nao duplicam handlers."""
    arquivo = pasta_de_logs() / "appcaptacao.log"
    if _handlers:
        return arquivo

    arquivo.parent.mkdir(parents=True, exist_ok=True)
    logger_app = logging.getLogger("app_captacao")
    logger_app.setLevel(logging.INFO)
    # O waitress chama logging.basicConfig(): sem isto cada linha sairia duas vezes no console.
    logger_app.propagate = False

    em_arquivo = RotatingFileHandler(
        arquivo, maxBytes=TAMANHO_MAXIMO_BYTES, backupCount=ARQUIVOS_MANTIDOS, encoding="utf-8"
    )
    em_arquivo.setFormatter(logging.Formatter(FORMATO))
    _handlers.append(em_arquivo)

    if console:
        no_console = logging.StreamHandler()
        no_console.setLevel(logging.INFO)
        no_console.addFilter(_MarcadorDoChecklist())
        no_console.setFormatter(_FormatoConsole(FORMATO_CONSOLE, datefmt="%H:%M:%S"))
        _handlers.append(no_console)

    for handler in _handlers:
        logger_app.addHandler(handler)
    return arquivo


def desligar_log_tecnico() -> None:
    logger_app = logging.getLogger("app_captacao")
    for handler in _handlers:
        logger_app.removeHandler(handler)
        handler.close()
    _handlers.clear()
    logger_app.propagate = True
