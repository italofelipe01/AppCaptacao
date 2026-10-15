"""Vinculos operacao x relatorio e valores de filtro por operacao.

Tabelas: RELATORIO_X_OPERACAO_TABLE e FILTRO_X_OPERACAO_TABLE. Colunas opcionais
(IdLoginCriacao, DataAlteracao, IdCapRecursoRelatorio...) sao detectadas no banco
para manter compatibilidade com schemas antigos.
"""

from __future__ import annotations

from contextlib import closing
from datetime import date

from app_captacao.catalogo import regras
from app_captacao.catalogo import relatorios as relatorios_repo
from app_captacao.core.config.settings import (
    FILTRO_CATALOGO_TABLE,
    FILTRO_X_OPERACAO_TABLE,
    RELATORIO_TABLE,
    RELATORIO_X_OPERACAO_TABLE,
)
from app_captacao.core.database import sql
from app_captacao.core.database.connection import DbConnection
from app_captacao.core.shared.texto import normalize_text


def get_filter_value_column(connection: DbConnection) -> str | None:
    for column_name in ("Valor", "ValorPadrao", "ValorFiltro"):
        if sql.column_exists(connection, FILTRO_X_OPERACAO_TABLE, column_name):
            return column_name
    return None


def format_filter_value(value: object, tipo_campo_valor: str = "") -> str:
    if value is None:
        return ""
    if str(tipo_campo_valor or "").strip().upper() == "CLICK":
        return ""
    if isinstance(value, date) and str(tipo_campo_valor or "").strip().upper() == "DATE":
        return value.strftime("%Y-%m-%d")
    return str(value)


def load_relatorios_operacao(operacao_id: int) -> list[dict]:
    with closing(sql.db_connection()) as connection:
        coluna_valor = get_filter_value_column(connection)
        coluna_relatorio_existe = sql.column_exists(connection, FILTRO_X_OPERACAO_TABLE, "IdCapRecursoRelatorio")
        valor_select = f"fo.{coluna_valor} AS valor" if coluna_valor else "CAST('' AS varchar(255)) AS valor"
        filtro_relatorio_sql = "AND fo.IdCapRecursoRelatorio = ?" if coluna_relatorio_existe else ""

        rows = sql.execute(
            f"""
            SELECT
                rxo.IdCapRecursoRelatorioOperacao AS id_relatorio_operacao,
                rxo.IdCapRecursoRelatorio AS id_relatorio,
                r.NomeRelatorio AS nome_relatorio,
                r.UrlRelatorio AS url_relatorio
            FROM {RELATORIO_X_OPERACAO_TABLE} rxo
            INNER JOIN {RELATORIO_TABLE} r
                ON r.IdCapRecursoRelatorio = rxo.IdCapRecursoRelatorio
            WHERE rxo.IdCapRecursoOperacoes = ?
              AND rxo.IdAtivo = 1
              AND r.IdAtivo = 1
            ORDER BY rxo.IdCapRecursoRelatorioOperacao
            """,
            (operacao_id,),
            fetch=True,
        )

        relatorios = []
        for ordem_execucao, row in enumerate(rows, start=1):
            relatorio_id = int(row["id_relatorio"])
            relatorio_nome = normalize_text(row["nome_relatorio"])
            executor = regras.executor_do_relatorio(
                {"id": relatorio_id, "nome": relatorio_nome, "url": normalize_text(row["url_relatorio"])}
            )
            params = [operacao_id]
            if coluna_relatorio_existe:
                params.append(relatorio_id)
            params.append(relatorio_id)
            filtros = sql.execute(
                f"""
                SELECT
                    fo.IdFiltro AS id_filtro,
                    f.NomeFiltro AS nome_filtro,
                    f.CampoIdentificador AS campo_identificador,
                    f.TipoCampoValor AS tipo_campo_valor,
                    {valor_select}
                FROM {FILTRO_X_OPERACAO_TABLE} fo
                INNER JOIN {FILTRO_CATALOGO_TABLE} f
                    ON f.IdFiltro = fo.IdFiltro
                WHERE fo.IdCapRecursoOperacoes = ?
                  {filtro_relatorio_sql}
                  AND f.IdCapRecursoRelatorio = ?
                  AND fo.IdAtivo = 1
                  AND f.IdAtivo = 1
                ORDER BY fo.OrdemVisual, f.NomeFiltro
                """,
                tuple(params),
                fetch=True,
            )
            relatorios.append(
                {
                    "id_relatorio_operacao": int(row["id_relatorio_operacao"]),
                    "id_relatorio": relatorio_id,
                    "nome_relatorio": relatorio_nome,
                    "ordem_execucao": ordem_execucao,
                    "filtros": [_filtro_da_operacao(executor, filtro) for filtro in filtros],
                }
            )
        return relatorios


def _filtro_da_operacao(executor: str, filtro: dict) -> dict:
    campo_identificador = normalize_text(filtro["campo_identificador"])
    valor_fixo = regras.valor_fixo_do_filtro(executor, {"campo_identificador": campo_identificador})
    return {
        "id_filtro": int(filtro["id_filtro"]),
        "nome_filtro": normalize_text(filtro["nome_filtro"]),
        "campo_identificador": campo_identificador,
        "valor": valor_fixo or format_filter_value(filtro["valor"], filtro["tipo_campo_valor"]),
        "automatico": bool(valor_fixo),
        "valor_fixo": valor_fixo,
        "tipo_campo_valor": "CLICK" if valor_fixo else normalize_text(filtro["tipo_campo_valor"]),
    }


def load_relatorio_operacao_payload(operacao_id: int) -> list[dict]:
    rows = sql.fetch_all(
        f"""
        SELECT
            rxo.IdCapRecursoRelatorioOperacao AS id_relatorio_operacao,
            r.IdCapRecursoRelatorio AS id_relatorio,
            r.NomeRelatorio AS nome_relatorio,
            r.UrlRelatorio AS url_relatorio
        FROM {RELATORIO_X_OPERACAO_TABLE} rxo
        INNER JOIN {RELATORIO_TABLE} r
            ON r.IdCapRecursoRelatorio = rxo.IdCapRecursoRelatorio
        WHERE rxo.IdCapRecursoOperacoes = ?
          AND rxo.IdAtivo = 1
          AND r.IdAtivo = 1
        ORDER BY rxo.IdCapRecursoRelatorioOperacao
        """,
        (operacao_id,),
    )

    relatorios_execucao = []
    with closing(sql.db_connection()) as connection:
        coluna_valor = get_filter_value_column(connection)
        coluna_relatorio_existe = sql.column_exists(connection, FILTRO_X_OPERACAO_TABLE, "IdCapRecursoRelatorio")
        valor_select = f"{coluna_valor} AS valor" if coluna_valor else "CAST('' AS varchar(255)) AS valor"
        for row in rows:
            relatorio = relatorios_repo.buscar_relatorio_com_filtros(int(row["id_relatorio"])) or {
            "id": int(row["id_relatorio"]),
            "nome": normalize_text(row["nome_relatorio"]),
            "url": normalize_text(row["url_relatorio"]),
            "filtros": [],
        }

            where_relatorio = "AND IdCapRecursoRelatorio = ?" if coluna_relatorio_existe else ""
            params = [operacao_id]
            if coluna_relatorio_existe:
                params.append(int(row["id_relatorio"]))
            filtro_rows = sql.execute(
                f"""
                SELECT IdFiltro AS id_filtro, {valor_select}
                FROM {FILTRO_X_OPERACAO_TABLE}
                WHERE IdCapRecursoOperacoes = ?
                  {where_relatorio}
                  AND IdAtivo = 1
                """,
                tuple(params),
                fetch=True,
            )
            valores = {
                int(filtro_row["id_filtro"]): normalize_text(filtro_row["valor"])
                for filtro_row in filtro_rows
            }

            filtros_execucao = []
            for filtro in relatorio.get("filtros", []):
                clone = dict(filtro)
                valor_fixo = normalize_text(clone.get("valor_fixo"))
                if clone.get("automatico") and valor_fixo:
                    clone["valor"] = valor_fixo
                else:
                    clone["valor"] = valores.get(int(clone.get("id") or 0), "")
                filtros_execucao.append(clone)

            relatorio["id_relatorio"] = int(row["id_relatorio"])
            relatorio["id_relatorio_operacao"] = int(row["id_relatorio_operacao"])
            relatorio["filtros"] = filtros_execucao
            relatorios_execucao.append(relatorio)
    return relatorios_execucao


def insert_operation_report_link(
    connection: DbConnection,
    operacao_id: int,
    relatorio_id: int,
    usuario_id: int | None = None,
) -> int:
    cursor = connection.cursor()
    cursor.execute(
        f"""
        SELECT COUNT(1) AS Total
        FROM {RELATORIO_X_OPERACAO_TABLE}
        WHERE IdCapRecursoOperacoes = ?
          AND IdCapRecursoRelatorio = ?
          AND IdAtivo = 1
        """,
        (operacao_id, relatorio_id),
    )
    vinculo_existente = cursor.fetchone()
    if vinculo_existente and vinculo_existente.Total:
        raise ValueError("Este relatorio ja esta vinculado a operacao.")

    relatorio = relatorios_repo.buscar_relatorio_com_filtros(relatorio_id)
    if not relatorio:
        raise ValueError(f"Relatorio {relatorio_id} nao encontrado ou inativo.")

    proximo_id = sql.get_next_id(connection, RELATORIO_X_OPERACAO_TABLE, "IdCapRecursoRelatorioOperacao")
    possui_login_criacao = sql.column_exists(connection, RELATORIO_X_OPERACAO_TABLE, "IdLoginCriacao")
    colunas = [
        "IdCapRecursoRelatorioOperacao",
        "IdCapRecursoRelatorio",
        "IdCapRecursoOperacoes",
        "IdAtivo",
        "DataCriacao",
    ]
    valores_sql = ["?", "?", "?", "1", "GETDATE()"]
    params: list[object] = [proximo_id, relatorio_id, operacao_id]
    if possui_login_criacao and usuario_id is not None:
        colunas.append("IdLoginCriacao")
        valores_sql.append("?")
        params.append(usuario_id)
    cursor.execute(
        f"INSERT INTO {RELATORIO_X_OPERACAO_TABLE} ({', '.join(colunas)}) "
        f"VALUES ({', '.join(valores_sql)})",
        tuple(params),
    )

    coluna_valor = get_filter_value_column(connection)
    coluna_relatorio_existe = sql.column_exists(connection, FILTRO_X_OPERACAO_TABLE, "IdCapRecursoRelatorio")
    coluna_vinculo_existe = sql.column_exists(
        connection, FILTRO_X_OPERACAO_TABLE, "IdCapRecursoRelatorioOperacao"
    )
    possui_login_criacao_filtro = sql.column_exists(connection, FILTRO_X_OPERACAO_TABLE, "IdLoginCriacao")

    for ordem_visual, filtro in enumerate(relatorio.get("filtros", []), start=1):
        colunas_filtro = ["IdCapRecursoOperacoes", "IdFiltro", "Obrigatorio", "OrdemVisual", "IdAtivo", "DataCriacao"]
        valores_filtro_sql = ["?", "?", "0", "?", "1", "GETDATE()"]
        params_filtro: list[object] = [operacao_id, int(filtro["id"]), ordem_visual]
        if coluna_relatorio_existe:
            colunas_filtro.insert(2, "IdCapRecursoRelatorio")
            valores_filtro_sql.insert(2, "?")
            params_filtro.insert(2, relatorio_id)
        if coluna_vinculo_existe:
            colunas_filtro.insert(2, "IdCapRecursoRelatorioOperacao")
            valores_filtro_sql.insert(2, "?")
            params_filtro.insert(2, proximo_id)
        if coluna_valor:
            colunas_filtro.append(coluna_valor)
            valores_filtro_sql.append("?")
            params_filtro.append("")
        if possui_login_criacao_filtro and usuario_id is not None:
            colunas_filtro.append("IdLoginCriacao")
            valores_filtro_sql.append("?")
            params_filtro.append(usuario_id)
        cursor.execute(
            f"INSERT INTO {FILTRO_X_OPERACAO_TABLE} ({', '.join(colunas_filtro)}) "
            f"VALUES ({', '.join(valores_filtro_sql)})",
            tuple(params_filtro),
        )
    return proximo_id


def inativar_relatorio_operacao(
    connection: DbConnection,
    operacao_id: int,
    relatorio_id: int,
    usuario_id: int | None = None,
) -> bool:
    cursor = connection.cursor()

    set_relatorio = []
    params_relatorio: list[object] = []
    if sql.column_exists(connection, RELATORIO_X_OPERACAO_TABLE, "DataAlteracao"):
        set_relatorio.append("DataAlteracao = GETDATE()")
    if sql.column_exists(connection, RELATORIO_X_OPERACAO_TABLE, "IdLoginAlteracao") and usuario_id is not None:
        set_relatorio.append("IdLoginAlteracao = ?")
        params_relatorio.append(usuario_id)
    params_relatorio.extend([operacao_id, relatorio_id])

    cursor.execute(
        f"""
        UPDATE {RELATORIO_X_OPERACAO_TABLE}
        SET IdAtivo = 0{", " + ", ".join(set_relatorio) if set_relatorio else ""}
        WHERE IdCapRecursoOperacoes = ?
          AND IdCapRecursoRelatorio = ?
          AND IdAtivo = 1
        """,
        tuple(params_relatorio),
    )
    removidos = cursor.rowcount

    set_filtros = []
    params_filtros: list[object] = []
    if sql.column_exists(connection, FILTRO_X_OPERACAO_TABLE, "DataAlteracao"):
        set_filtros.append("DataAlteracao = GETDATE()")
    if sql.column_exists(connection, FILTRO_X_OPERACAO_TABLE, "IdLoginAlteracao") and usuario_id is not None:
        set_filtros.append("IdLoginAlteracao = ?")
        params_filtros.append(usuario_id)
    params_filtros.append(operacao_id)

    if sql.column_exists(connection, FILTRO_X_OPERACAO_TABLE, "IdCapRecursoRelatorioOperacao"):
        where_filtros = f"""
          AND IdCapRecursoRelatorioOperacao IN (
              SELECT IdCapRecursoRelatorioOperacao
              FROM {RELATORIO_X_OPERACAO_TABLE}
              WHERE IdCapRecursoOperacoes = ?
                AND IdCapRecursoRelatorio = ?
          )
        """
        params_filtros.extend([operacao_id, relatorio_id])
    elif sql.column_exists(connection, FILTRO_X_OPERACAO_TABLE, "IdCapRecursoRelatorio"):
        where_filtros = "AND IdCapRecursoRelatorio = ?"
        params_filtros.append(relatorio_id)
    else:
        where_filtros = f"""
          AND IdFiltro IN (
              SELECT IdFiltro
              FROM {FILTRO_CATALOGO_TABLE}
              WHERE IdCapRecursoRelatorio = ?
                AND IdAtivo = 1
          )
        """
        params_filtros.append(relatorio_id)

    cursor.execute(
        f"""
        UPDATE {FILTRO_X_OPERACAO_TABLE}
        SET IdAtivo = 0{", " + ", ".join(set_filtros) if set_filtros else ""}
        WHERE IdCapRecursoOperacoes = ?
          {where_filtros}
          AND IdAtivo = 1
        """,
        tuple(params_filtros),
    )

    return bool(removidos)


class OperacaoSemRelatorioError(ValueError):
    """A operacao precisa manter pelo menos um relatorio ativo."""


def vincular_relatorio(operacao_id: int, relatorio_id: int, usuario_id: int | None) -> int:
    with closing(sql.db_connection()) as connection:
        vinculo_id = insert_operation_report_link(connection, operacao_id, relatorio_id, usuario_id)
        connection.commit()
    return vinculo_id


def atualizar_valores_filtros(
    operacao_id: int,
    relatorio_id: int,
    ids_filtro: list[str],
    valores: list[str],
    usuario_id: int | None,
) -> None:
    """Grava o valor de cada filtro do relatorio dentro da operacao."""
    with closing(sql.db_connection()) as connection:
        coluna_valor = get_filter_value_column(connection)
        if not coluna_valor:
            raise ValueError("A tabela de filtros da operacao nao possui coluna de valor configurada.")
        coluna_relatorio_existe = sql.column_exists(connection, FILTRO_X_OPERACAO_TABLE, "IdCapRecursoRelatorio")
        possui_login_alteracao = sql.column_exists(connection, FILTRO_X_OPERACAO_TABLE, "IdLoginAlteracao")
        possui_data_alteracao = sql.column_exists(connection, FILTRO_X_OPERACAO_TABLE, "DataAlteracao")

        for filtro_id, valor in zip(ids_filtro, valores):
            params: list[object] = [normalize_text(valor)]
            set_extra = ""
            if possui_data_alteracao:
                set_extra += ", DataAlteracao = GETDATE()"
            if possui_login_alteracao and usuario_id is not None:
                set_extra += ", IdLoginAlteracao = ?"
                params.append(usuario_id)
            params.extend([operacao_id, int(filtro_id)])
            where_relatorio = ""
            if coluna_relatorio_existe:
                where_relatorio = "AND IdCapRecursoRelatorio = ?"
                params.append(relatorio_id)

            connection.cursor().execute(
                f"""
                UPDATE {FILTRO_X_OPERACAO_TABLE}
                SET {coluna_valor} = ?{set_extra}
                WHERE IdCapRecursoOperacoes = ?
                  AND IdFiltro = ?
                  {where_relatorio}
                """,
                tuple(params),
            )
        connection.commit()


def desvincular_relatorio(operacao_id: int, relatorio_id: int, usuario_id: int | None) -> bool:
    """Inativa o vinculo e seus filtros; retorna False se o vinculo ja nao existia."""
    with closing(sql.db_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"SELECT COUNT(1) AS Total FROM {RELATORIO_X_OPERACAO_TABLE} "
            "WHERE IdCapRecursoOperacoes = ? AND IdAtivo = 1",
            (operacao_id,),
        )
        row = cursor.fetchone()
        if int((row.Total if row else 0) or 0) <= 1:
            raise OperacaoSemRelatorioError("A operacao deve manter pelo menos um relatorio ativo.")
        removido = inativar_relatorio_operacao(connection, operacao_id, relatorio_id, usuario_id)
        connection.commit()
    return removido
