"""Confere as bibliotecas do requirements.txt usando so a biblioteca padrao.

Roda antes de qualquer import de terceiros: e o que permite instalar o que
falta e so depois carregar o app.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

_LINHA_REQUISITO = re.compile(r"^(?P<nome>[A-Za-z0-9_.\-]+)\s*(?P<especificador>[^;]*)(?:;\s*(?P<marcador>.+))?$")
_COMPARADORES = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


@dataclass(frozen=True)
class Requisito:
    nome: str
    especificador: str


@dataclass(frozen=True)
class Pendencia:
    requisito: Requisito
    instalada: str | None

    def descrever(self) -> str:
        alvo = f"{self.requisito.nome}{self.requisito.especificador}"
        if self.instalada is None:
            return f"{alvo} (nao instalada)"
        return f"{alvo} (instalada {self.instalada})"


def _versao_em_tupla(versao: str) -> tuple[int, ...]:
    partes = []
    for parte in versao.split("."):
        numero = re.match(r"\d+", parte)
        if not numero:
            break
        partes.append(int(numero.group()))
    return tuple(partes)


def _marcador_atende(marcador: str | None) -> bool:
    """Suporta o unico marcador usado no projeto: sys_platform == '...'."""
    if not marcador:
        return True
    encontrado = re.fullmatch(r"\s*sys_platform\s*(==|!=)\s*['\"]([^'\"]+)['\"]\s*", marcador)
    if not encontrado:
        return True
    operador, plataforma = encontrado.groups()
    return (sys.platform == plataforma) == (operador == "==")


def ler_requisitos(caminho: Path) -> list[Requisito]:
    requisitos = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.split("#", 1)[0].strip()
        if not linha or linha.startswith("-"):
            continue
        encontrado = _LINHA_REQUISITO.match(linha)
        if not encontrado or not _marcador_atende(encontrado.group("marcador")):
            continue
        requisitos.append(Requisito(encontrado.group("nome"), encontrado.group("especificador").strip()))
    return requisitos


def versao_atende(instalada: str, especificador: str) -> bool:
    atual = _versao_em_tupla(instalada)
    for condicao in filter(None, (parte.strip() for parte in especificador.split(","))):
        encontrado = re.match(r"(>=|<=|==|!=|>|<)\s*(.+)", condicao)
        if not encontrado:
            continue
        operador, versao = encontrado.groups()
        if not _COMPARADORES[operador](atual, _versao_em_tupla(versao)):
            return False
    return True


def verificar(requisitos: list[Requisito]) -> list[Pendencia]:
    pendencias = []
    for requisito in requisitos:
        try:
            instalada = metadata.version(requisito.nome)
        except metadata.PackageNotFoundError:
            pendencias.append(Pendencia(requisito, None))
            continue
        if not versao_atende(instalada, requisito.especificador):
            pendencias.append(Pendencia(requisito, instalada))
    return pendencias


def em_ambiente_virtual() -> bool:
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def instalar(caminho_requisitos: Path) -> bool:
    comando = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-r", str(caminho_requisitos)]
    return subprocess.run(comando).returncode == 0
