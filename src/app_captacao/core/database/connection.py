"""
Servico de banco de dados SQL Server.
"""

import logging
import os

import pyodbc

try:
    import pymssql  # pyright: ignore[reportMissingImports]
except ImportError:  # pragma: no cover - fallback opcional em instalacoes antigas
    pymssql = None

from app_captacao.core.config.environment import initialize_environment
from app_captacao.core.shared.texto import parse_int


initialize_environment()

logger = logging.getLogger(__name__)
_preferred_backend: str | None = None


class _CompatibleRow(tuple):
    _column_indexes: dict[str, int]

    def __new__(cls, values, columns):
        instance = super().__new__(cls, values)
        instance._column_indexes = {
            str(column).lower(): index for index, column in enumerate(columns)
        }
        return instance

    def __getattr__(self, name):
        try:
            return self[self._column_indexes[name.lower()]]
        except KeyError as exc:
            raise AttributeError(name) from exc


class _PymssqlCursorAdapter:
    def __init__(self, cursor):
        self._cursor = cursor

    @property
    def description(self):
        return self._cursor.description

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def execute(self, query, params=()):
        converted_query = str(query).replace("?", "%s")
        if params is None:
            normalized_params = ()
        elif isinstance(params, (tuple, list)):
            normalized_params = tuple(params)
        else:
            normalized_params = (params,)
        self._cursor.execute(converted_query, normalized_params)
        return self

    def _columns(self):
        return [column[0] for column in self.description or []]

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return _CompatibleRow(row, self._columns())

    def fetchall(self):
        columns = self._columns()
        return [_CompatibleRow(row, columns) for row in self._cursor.fetchall()]

    def close(self):
        return self._cursor.close()


class _PymssqlConnectionAdapter:
    def __init__(self, connection):
        self._connection = connection

    def cursor(self):
        return _PymssqlCursorAdapter(self._connection.cursor())

    def commit(self):
        return self._connection.commit()

    def rollback(self):
        return self._connection.rollback()

    def close(self):
        return self._connection.close()


# Conexao devolvida pelo ODBC ou pelo fallback pymssql; as duas expoem cursor/commit/close.
DbConnection = pyodbc.Connection | _PymssqlConnectionAdapter


def nome_do_banco() -> str:
    """Banco usado na conexao: DB_DATABASE; DB_SCHEMA so quando DB_DATABASE nem existe (legado)."""
    return os.getenv("DB_DATABASE", os.getenv("DB_SCHEMA", "")).strip()


def _valor_odbc(valor: str) -> str:
    """Valor de atributo ODBC entre chaves: senha com ';' ou '}' nao quebra a string."""
    return "{" + str(valor).replace("}", "}}") + "}"


def _get_odbc_connection(timeout: int):
    driver = os.getenv("DB_DRIVER", "SQL Server")
    extra_params = os.getenv("DB_EXTRA_PARAMS", "").strip()
    connection_parts = [
        f"DRIVER={_valor_odbc(driver)}",
        f"SERVER={_valor_odbc(os.getenv('DB_HOST', ''))}",
        f"DATABASE={_valor_odbc(nome_do_banco())}",
        f"UID={_valor_odbc(os.getenv('DB_USER', ''))}",
        f"PWD={_valor_odbc(os.getenv('DB_PASSWORD', ''))}",
    ]

    if not extra_params and driver.lower() != "sql server":
        extra_params = "TrustServerCertificate=yes"

    if extra_params:
        connection_parts.extend(
            [part.strip() for part in extra_params.split(";") if part.strip()]
        )

    connection_string = ";".join(connection_parts) + ";"
    return pyodbc.connect(connection_string, timeout=timeout)


def _get_pymssql_connection(timeout: int):
    if pymssql is None:
        raise RuntimeError(
            "O driver ODBC falhou e o fallback pymssql nao esta instalado."
        )
    connection = pymssql.connect(
        server=os.getenv("DB_HOST", ""),
        user=os.getenv("DB_USER", ""),
        password=os.getenv("DB_PASSWORD", ""),
        database=nome_do_banco(),
        login_timeout=timeout,
        timeout=timeout,
        charset="UTF-8",
    )
    return _PymssqlConnectionAdapter(connection)


def get_db_connection() -> DbConnection:
    global _preferred_backend
    timeout = parse_int(os.getenv("DB_TIMEOUT"), 5) or 5

    if _preferred_backend == "pymssql":
        return _get_pymssql_connection(timeout)

    try:
        connection = _get_odbc_connection(timeout)
        _preferred_backend = "odbc"
        return connection
    except pyodbc.Error as exc:
        if pymssql is None:
            raise
        logger.warning(
            "Conexao ODBC indisponivel (%s). Usando fallback pymssql nesta execucao.",
            exc.args[0] if exc.args else type(exc).__name__,
        )
        connection = _get_pymssql_connection(timeout)
        _preferred_backend = "pymssql"
        return connection
