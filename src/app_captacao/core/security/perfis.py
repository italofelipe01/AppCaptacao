"""Perfis de acesso (coluna IdAcesso da tabela de usuarios)."""

from __future__ import annotations

ACESSO_ADMINISTRADOR = 1
ACESSO_CADASTRO_OPERACAO = 2
ACESSO_EXECUCAO = 3

PERFIS_POR_ACESSO = {
    ACESSO_ADMINISTRADOR: "Administrador",
    ACESSO_CADASTRO_OPERACAO: "Usuario com cadastro de operacao",
    ACESSO_EXECUCAO: "Usuario de execucao",
}


def descricao_perfil(access_id: int) -> str:
    return PERFIS_POR_ACESSO.get(access_id, "Usuario")
