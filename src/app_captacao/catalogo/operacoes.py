"""Operacoes: agrupamentos de relatorios executados em sequencia (OPERACAO_TABLE)."""

from __future__ import annotations

from contextlib import closing

from app_captacao.catalogo import operacao_relatorios as vinculos_repo
from app_captacao.core.config.settings import OPERACAO_TABLE, RELATORIO_TABLE, RELATORIO_X_OPERACAO_TABLE
from app_captacao.core.database import sql
from app_captacao.core.database.connection import DbConnection
from app_captacao.core.shared.texto import format_datetime, normalize_text, to_bool


def load_operacoes(filtro_nome: str = "") -> list[dict]:
    if filtro_nome:
        rows = sql.fetch_all(
            f"""
            SELECT
                o.IdCapRecursoOperacoes AS id,
                o.NomeOperacao AS nome,
                o.IdAtivo AS ativo,
                o.DataCriacao AS data_criacao,
                (SELECT COUNT(1) FROM {RELATORIO_X_OPERACAO_TABLE} rxo
                 WHERE rxo.IdCapRecursoOperacoes = o.IdCapRecursoOperacoes AND rxo.IdAtivo = 1) AS quantidade_relatorios
            FROM {OPERACAO_TABLE} o
            WHERE o.IdAtivo = 1 AND o.NomeOperacao LIKE ?
            ORDER BY o.NomeOperacao
            """,
            (f"%{filtro_nome}%",),
        )
    else:
        rows = sql.fetch_all(
            f"""
            SELECT
                o.IdCapRecursoOperacoes AS id,
                o.NomeOperacao AS nome,
                o.IdAtivo AS ativo,
                o.DataCriacao AS data_criacao,
                (SELECT COUNT(1) FROM {RELATORIO_X_OPERACAO_TABLE} rxo
                 WHERE rxo.IdCapRecursoOperacoes = o.IdCapRecursoOperacoes AND rxo.IdAtivo = 1) AS quantidade_relatorios
            FROM {OPERACAO_TABLE} o
            WHERE o.IdAtivo = 1
            ORDER BY o.NomeOperacao
            """
        )
    return [
        {
            "id": int(row["id"]),
            "nome": normalize_text(row["nome"]),
            "ativo": to_bool(row["ativo"]),
            "status": "Ativo" if to_bool(row["ativo"]) else "Inativo",
            "data_criacao": format_datetime(row.get("data_criacao")),
            "quantidade_relatorios": int(row.get("quantidade_relatorios") or 0),
        }
        for row in rows
    ]


def load_operation_report_summaries() -> dict[int, list[dict]]:
    rows = sql.fetch_all(
        f"""
        SELECT
            rxo.IdCapRecursoOperacoes AS operacao_id,
            r.IdCapRecursoRelatorio AS relatorio_id,
            r.NomeRelatorio AS relatorio_nome
        FROM {RELATORIO_X_OPERACAO_TABLE} rxo
        INNER JOIN {OPERACAO_TABLE} o
            ON o.IdCapRecursoOperacoes = rxo.IdCapRecursoOperacoes
        INNER JOIN {RELATORIO_TABLE} r
            ON r.IdCapRecursoRelatorio = rxo.IdCapRecursoRelatorio
        WHERE rxo.IdAtivo = 1 AND o.IdAtivo = 1 AND r.IdAtivo = 1
        ORDER BY rxo.IdCapRecursoOperacoes, rxo.IdCapRecursoRelatorioOperacao
        """
    )
    summaries: dict[int, list[dict]] = {}
    for row in rows:
        summaries.setdefault(int(row["operacao_id"]), []).append(
            {
                "id": int(row["relatorio_id"]),
                "nome": normalize_text(row["relatorio_nome"]),
            }
        )
    return summaries


def operation_name_exists(connection: DbConnection, nome_operacao: str, exclude_id: int | None = None) -> bool:
    cursor = connection.cursor()
    params: list[object] = [nome_operacao]
    exclude_sql = ""
    if exclude_id is not None:
        exclude_sql = "AND IdCapRecursoOperacoes <> ?"
        params.append(exclude_id)
    cursor.execute(
        f"""
        SELECT COUNT(1) AS Total
        FROM {OPERACAO_TABLE}
        WHERE LOWER(LTRIM(RTRIM(NomeOperacao))) = LOWER(LTRIM(RTRIM(?)))
          AND IdAtivo = 1
          {exclude_sql}
        """,
        tuple(params),
    )
    row = cursor.fetchone()
    return bool(row and row.Total)


def buscar_operacao_ativa(operacao_id: int) -> dict | None:
    return sql.fetch_one(
        f"SELECT NomeOperacao AS nome FROM {OPERACAO_TABLE} "
        "WHERE IdCapRecursoOperacoes = ? AND IdAtivo = 1",
        (operacao_id,),
    )


def criar_operacao(nome_operacao: str, relatorios_ids: list[int], usuario_id: int | None) -> int:
    """Cria a operacao e vincula os relatorios na ordem recebida, em uma unica transacao."""
    with closing(sql.db_connection()) as connection:
        if operation_name_exists(connection, nome_operacao):
            raise ValueError("Ja existe uma operacao ativa com este nome.")
        operacao_id = sql.get_next_id(connection, OPERACAO_TABLE, "IdCapRecursoOperacoes")
        colunas = ["IdCapRecursoOperacoes", "NomeOperacao", "IdAtivo", "DataCriacao"]
        valores = ["?", "?", "1", "GETDATE()"]
        params: list[object] = [operacao_id, nome_operacao]
        if sql.column_exists(connection, OPERACAO_TABLE, "IdLoginCriacao") and usuario_id is not None:
            colunas.append("IdLoginCriacao")
            valores.append("?")
            params.append(usuario_id)
        connection.cursor().execute(
            f"INSERT INTO {OPERACAO_TABLE} ({', '.join(colunas)}) VALUES ({', '.join(valores)})",
            tuple(params),
        )
        for relatorio_id in relatorios_ids:
            vinculos_repo.insert_operation_report_link(connection, operacao_id, relatorio_id, usuario_id)
        connection.commit()
    return operacao_id


def renomear_operacao(operacao_id: int, nome_operacao: str) -> None:
    with closing(sql.db_connection()) as connection:
        if operation_name_exists(connection, nome_operacao, exclude_id=operacao_id):
            raise ValueError("Ja existe uma operacao ativa com este nome.")
        connection.cursor().execute(
            f"UPDATE {OPERACAO_TABLE} SET NomeOperacao = ? WHERE IdCapRecursoOperacoes = ?",
            (nome_operacao, operacao_id),
        )
        connection.commit()


def inativar_operacao(operacao_id: int) -> None:
    sql.execute(
        f"UPDATE {OPERACAO_TABLE} SET IdAtivo = 0 WHERE IdCapRecursoOperacoes = ?",
        (operacao_id,),
        commit=True,
    )
