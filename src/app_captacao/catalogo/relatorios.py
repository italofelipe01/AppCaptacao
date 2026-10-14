"""Catalogo de relatorios e filtros (RELATORIO_TABLE e FILTRO_CATALOGO_TABLE).

Monta o relatorio com seus filtros ativos e o payload de execucao a partir dos
valores enviados pela tela.
"""

from contextlib import closing

from app_captacao.core.config.settings import FILTRO_CATALOGO_TABLE as FILTRO_TABLE
from app_captacao.core.config.settings import RELATORIO_TABLE
from app_captacao.core.database import sql
from app_captacao.core.database.connection import get_db_connection
from app_captacao.core.shared.texto import normalize_text

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

UNIDADES_SELECAO_CAMPO = "filter.selecao"
UNIDADES_SELECAO_VALOR = "por Empreendimento"


def aplicar_filtros_fixos_relatorio(relatorio):
    if not relatorio:
        return relatorio

    nome_relatorio = " ".join(str(relatorio.get("nome") or "").strip().lower().split())
    if "unidades" not in nome_relatorio:
        return relatorio

    for filtro in relatorio.get("filtros", []):
        campo = str(filtro.get("campo_identificador") or "").strip().lower()
        if campo != UNIDADES_SELECAO_CAMPO:
            continue

        filtro["valor_fixo"] = UNIDADES_SELECAO_VALOR
        filtro["valor"] = UNIDADES_SELECAO_VALOR
        filtro["opcional"] = True
        filtro["automatico"] = True
        filtro["tipo_campo_valor"] = "CLICK"

    return relatorio


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

    return aplicar_filtros_fixos_relatorio(relatorio)


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
        if str(filtro_execucao.get("campo_identificador") or "").strip().lower() == UNIDADES_SELECAO_CAMPO:
            filtro_execucao["valor"] = UNIDADES_SELECAO_VALOR
            filtro_execucao["valor_fixo"] = UNIDADES_SELECAO_VALOR
            filtro_execucao["opcional"] = True
            filtro_execucao["automatico"] = True
            filtro_execucao["tipo_campo_valor"] = "CLICK"
        else:
            filtro_execucao["valor"] = valor
        filtros_execucao.append(filtro_execucao)

    relatorio["filtros"] = filtros_execucao
    return aplicar_filtros_fixos_relatorio(relatorio)


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
