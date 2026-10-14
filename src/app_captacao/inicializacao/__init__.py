"""Verificacao do ambiente antes de abrir o AppCaptacao.

Ordem: bibliotecas (so biblioteca padrao) -> configuracao -> interface ->
navegador -> pasta de downloads -> banco. O app so inicia sem nenhum erro.
"""

from __future__ import annotations

import sys
from pathlib import Path

from app_captacao.inicializacao import dependencias

RAIZ_PROJETO = Path(__file__).resolve().parents[3]
REQUISITOS = RAIZ_PROJETO / "requirements.txt"

_MARCADORES = {"ok": "[ OK  ]", "aviso": "[AVISO]", "erro": "[ERRO ]"}


def _imprimir(status: str, nome: str, mensagem: str, dica: str = "") -> None:
    print(f"  {_MARCADORES[status]} {nome}: {mensagem}")
    if dica:
        print(f"          -> {dica}")


def garantir_dependencias(instalar_automaticamente: bool = True) -> bool:
    requisitos = dependencias.ler_requisitos(REQUISITOS)
    pendencias = dependencias.verificar(requisitos)
    if not pendencias:
        _imprimir("ok", "Bibliotecas", f"{len(requisitos)} bibliotecas instaladas.")
        return True

    lista = ", ".join(pendencia.descrever() for pendencia in pendencias)
    if not (instalar_automaticamente and dependencias.em_ambiente_virtual()):
        _imprimir(
            "erro",
            "Bibliotecas",
            f"Faltando ou fora da versao: {lista}.",
            "Use o 'Iniciar AppCaptacao.bat' (cria o .venv) ou rode: pip install -r requirements.txt",
        )
        return False

    print(f"  Instalando bibliotecas que faltam: {lista}")
    if not dependencias.instalar(REQUISITOS):
        _imprimir(
            "erro",
            "Bibliotecas",
            "A instalacao falhou.",
            "Confira a conexao com a internet/proxy e rode de novo. Detalhes acima.",
        )
        return False

    restantes = dependencias.verificar(requisitos)
    if restantes:
        _imprimir("erro", "Bibliotecas", "Ainda faltando: " + ", ".join(p.descrever() for p in restantes))
        return False
    _imprimir("ok", "Bibliotecas", f"{len(requisitos)} bibliotecas instaladas.")
    return True


def verificar_python() -> bool:
    versao = ".".join(str(parte) for parte in sys.version_info[:3])
    if sys.version_info < (3, 11):
        _imprimir("erro", "Python", f"Versao {versao}; o AppCaptacao precisa do Python 3.11 ou mais novo.")
        return False
    _imprimir("ok", "Python", f"{versao} em {sys.executable}")
    return True


def verificar_configuracao_e_servicos(incluir_banco: bool = True) -> bool:
    from app_captacao.inicializacao.verificacoes import ERRO, executar_verificacoes

    resultados = executar_verificacoes(incluir_banco=incluir_banco)
    for resultado in resultados:
        _imprimir(resultado.status, resultado.nome, resultado.mensagem, resultado.dica)

    if any(resultado.status == ERRO for resultado in resultados):
        print("\nCorrija os itens marcados com [ERRO ] e abra o AppCaptacao novamente.")
        return False
    print("Ambiente pronto.\n")
    return True


def preparar_ambiente(instalar_automaticamente: bool = True, incluir_banco: bool = True) -> bool:
    """Checklist completo; devolve True se o app pode iniciar."""
    print("Verificando o ambiente do AppCaptacao...")
    return (
        verificar_python()
        and garantir_dependencias(instalar_automaticamente)
        and verificar_configuracao_e_servicos(incluir_banco)
    )
