"""Catalogo de relatorios e filtros (RELATORIO_TABLE e FILTRO_CATALOGO_TABLE).

Monta o relatorio com seus filtros ativos e o payload de execucao a partir dos
valores enviados pela tela.
"""

from contextlib import closing

from app_captacao.catalogo import regras
from app_captacao.core.config.settings import FILTRO_CATALOGO_TABLE as FILTRO_TABLE
from app_captacao.core.config.settings import RELATORIO_TABLE
from app_captacao.core.database import sql
from app_captacao.core.database.connection import get_db_connection
from app_captacao.core.shared.texto import normalize_text

# Relatorio com seus filtros ativos. O filtro de IdAtivo fica no ON: relatorio
# ativo com todos os filtros inativos continua aparecendo (sem filtros).
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
       AND f.IdAtivo = 1
    WHERE r.IdCapRecursoRelatorio = ?
      AND r.IdAtivo = 1
    ORDER BY f.IdFiltro
"""


def buscar_relatorio_com_filtros(relatorio_id):
    """Relatorio ativo com seus filtros ativos (e os de valor fixo ja preenchidos), ou None."""
    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(RELATORIO_COM_FILTROS_QUERY, relatorio_id)
        rows = cursor.fetchall()

    if not rows:
        return None

    primeira_linha = rows[0]
    relatorio = {
        "id": primeira_linha.IdCapRecursoRelatorio,
        "nome": primeira_linha.NomeRelatorio,
        "url": primeira_linha.UrlRelatorio or "",
        "filtros": [],
    }

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

    return regras.aplicar_filtros_fixos(relatorio)


def montar_payload_execucao(relatorio_id, valores_filtros):
    relatorio = buscar_relatorio_com_filtros(relatorio_id)
    if not relatorio:
        return None

    filtros_execucao = []
    for filtro in relatorio["filtros"]:
        filtro_execucao = dict(filtro)
        if not filtro_execucao.get("automatico"):
            valor = valores_filtros.get(f"filtro_{filtro['id']}")
            if valor is None and filtro["nome"]:
                valor = valores_filtros.get(filtro["nome"])
            filtro_execucao["valor"] = valor
        filtros_execucao.append(filtro_execucao)

    relatorio["filtros"] = filtros_execucao
    return relatorio


def load_relatorios_disponiveis() -> list[dict]:
    rows = sql.fetch_all(
        f"""
        SELECT
            IdCapRecursoRelatorio AS id,
            NomeRelatorio AS nome,
            UrlRelatorio AS url
        FROM {RELATORIO_TABLE}
        WHERE IdAtivo = 1
        ORDER BY NomeRelatorio
        """
    )
    return [
        {
            "id": int(row["id"]),
            "nome": normalize_text(row["nome"]),
            "url": normalize_text(row["url"]),
        }
        for row in rows
    ]
