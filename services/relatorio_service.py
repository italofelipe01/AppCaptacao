"""
Serviço de Relatórios - Busca e Configuração
=============================================

Módulo responsável por buscar configurações de relatórios
do banco de dados, incluindo filtros disponíveis e suas
respectivas configurações.

Autor: Equipe de Desenvolvimento
Versão: 1.0.0
Data: Abril 2026
"""

import os
from contextlib import closing

from services.database_service import get_db_connection
from services.relatorio_action_service import anexar_botoes_automaticos

# ============================================================
# CONFIGURAÇÃO DE TABELAS
# ============================================================

# Tabelas do banco de dados para relatórios e filtros
RELATORIO_TABLE = os.getenv("RELATORIO_TABLE", "dbo.CapRecursoRelatorio")
FILTRO_TABLE = os.getenv("FILTRO_CATALOGO_TABLE", "dbo.CapRecursoFiltro")

# Query para buscar relatório com seus filtros associados
RELATORIO_COM_FILTROS_QUERY = f"""
    SELECT
        r.IdCapRecursoRelatorio,
        r.NomeRelatorio,
        r.UrlRelatorio,
        f.IdFiltro,
        f.NomeFiltro,
        f.TipoCampo,
        f.TipoCampoValor,
        f.IframeIndex,
        f.CampoIdentificador,
        f.Acao
    FROM {RELATORIO_TABLE} r
    LEFT JOIN {FILTRO_TABLE} f
        ON f.IdCapRecursoRelatorio = r.IdCapRecursoRelatorio
    WHERE r.IdCapRecursoRelatorio = ?
      AND r.IdAtivo = 1
      AND (f.IdFiltro IS NULL OR f.IdAtivo = 1)
    ORDER BY f.IdFiltro
"""


def buscar_relatorio_com_filtros(relatorio_id):
    """
    Busca configuração de relatório e seus filtros no banco.
    
    Args:
        relatorio_id: ID do relatório a buscar
    
    Returns:
        dict ou None: Dicionário com dados do relatório e filtros
    
    Example:
        >>> relatorio = buscar_relatorio_com_filtros(1)
        >>> print(relatorio['nome'])
        >>> for filtro in relatorio['filtros']:
        >>>     print(filtro['nome'])
    """
    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(RELATORIO_COM_FILTROS_QUERY, relatorio_id)
        rows = cursor.fetchall()

    if not rows:
        return None

    # Monta estrutura do relatório
    primeira_linha = rows[0]
    relatorio = {
        "id": primeira_linha.IdCapRecursoRelatorio,
        "nome": primeira_linha.NomeRelatorio,
        "url": primeira_linha.UrlRelatorio or "",
        "filtros": [],
    }

    # Processa filtros encontrados
    for row in rows:
        if row.IdFiltro is None:
            continue

        relatorio["filtros"].append(
            {
                "id": row.IdFiltro,
                "nome": (row.NomeFiltro or "").strip(),
                "tipo_campo": (row.TipoCampo or "").strip().upper(),
                "tipo_campo_valor": (row.TipoCampoValor or "").strip().upper(),
                "iframe_index": int(row.IframeIndex) if row.IframeIndex is not None else 0,
                "campo_identificador": (row.CampoIdentificador or "").strip(),
                "acao": (row.Acao or "").strip().lower(),
            }
        )

    return anexar_botoes_automaticos(relatorio)


def montar_payload_execucao(relatorio_id, valores_filtros):
    relatorio = buscar_relatorio_com_filtros(relatorio_id)
    if not relatorio:
        return None

    filtros_execucao = []
    for filtro in relatorio["filtros"]:
        chave_padrao = f"filtro_{filtro['id']}"
        valor = valores_filtros.get(chave_padrao)

        if valor is None and filtro["nome"]:
            valor = valores_filtros.get(filtro["nome"])

        filtro_execucao = dict(filtro)
        filtro_execucao["valor"] = valor
        filtros_execucao.append(filtro_execucao)

    relatorio["filtros"] = filtros_execucao
    return anexar_botoes_automaticos(relatorio)
