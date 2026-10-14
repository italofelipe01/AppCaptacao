"""Execucao de SQL e introspeccao de colunas no SQL Server.

Todo acesso ao banco passa por aqui ou pelos repositorios que usam este modulo.
"""

from __future__ import annotations

import logging
from contextlib import closing

from app_captacao.core.database.connection import DbConnection, get_db_connection

logger = logging.getLogger(__name__)


def db_connection():
    return get_db_connection()


def execute(query: str, params: tuple = (), fetch: bool = False, commit: bool = False) -> list[dict]:
    with closing(db_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(query, params)
        rows: list[dict] = []
        if fetch:
            columns = [column[0] for column in cursor.description or []]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        if commit:
            connection.commit()
        return rows


def fetch_one(query: str, params: tuple = ()) -> dict | None:
    rows = execute(query, params, fetch=True)
    return rows[0] if rows else None


def fetch_all(query: str, params: tuple = ()) -> list[dict]:
    return execute(query, params, fetch=True)


def split_table_name(table_name: str) -> tuple[str, str]:
    parts = [part.strip("[] ") for part in str(table_name or "").split(".") if part.strip()]
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    return "dbo", parts[0]


def column_exists(connection: DbConnection, table_name: str, column_name: str) -> bool:
    schema, table = split_table_name(table_name)
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT COUNT(1) AS Total
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = ?
          AND TABLE_NAME = ?
          AND COLUMN_NAME = ?
        """,
        (schema, table, column_name),
    )
    row = cursor.fetchone()
    return bool(row and row.Total)


def column_is_identity(connection: DbConnection, table_name: str, column_name: str) -> bool:
    schema, table = split_table_name(table_name)
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT COLUMNPROPERTY(
            OBJECT_ID(QUOTENAME(?) + '.' + QUOTENAME(?)),
            ?,
            'IsIdentity'
        ) AS IsIdentity
        """,
        (schema, table, column_name),
    )
    row = cursor.fetchone()
    return bool(row and row.IsIdentity)


def get_next_id(connection: DbConnection, table_name: str, id_column: str) -> int:
    cursor = connection.cursor()
    cursor.execute(
        f"SELECT ISNULL(MAX({id_column}), 0) + 1 AS ProximoId "
        f"FROM {table_name} WITH (UPDLOCK, HOLDLOCK)"
    )
    row = cursor.fetchone()
    return int(row.ProximoId if row and row.ProximoId is not None else 1)


def safe_db_call(loader, default):
    try:
        return loader()
    except Exception:
        logger.exception("Falha ao acessar o banco de dados.")
        return default
