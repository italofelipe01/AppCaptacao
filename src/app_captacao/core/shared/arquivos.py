"""Nomes de arquivo e pasta: os mesmos para o download, a pasta do relatorio e o consolidado."""

from __future__ import annotations

import re
from pathlib import Path


def sanitizar_nome_arquivo(valor) -> str:
    valor = str(valor or "").strip()
    valor = re.sub(r'[<>:"/\\|?*]+', " ", valor)
    valor = re.sub(r"\s+", " ", valor).strip()
    return valor or "sem_nome"


def montar_caminho_unico(pasta, nome_base, extensao) -> Path:
    """Caminho que ainda nao existe: `nome.ext`, `nome_2.ext`, `nome_3.ext`..."""
    pasta = Path(pasta)
    destino = pasta / f"{nome_base}{extensao}"
    contador = 2
    while destino.exists():
        destino = pasta / f"{nome_base}_{contador}{extensao}"
        contador += 1
    return destino
