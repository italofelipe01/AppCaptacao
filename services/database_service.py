"""
Servico de banco de dados SQL Server.
"""

import os

import pyodbc

from app_core.app_config import initialize_environment


initialize_environment()


def get_db_connection():
    driver = os.getenv("DB_DRIVER", "SQL Server")
    extra_params = os.getenv("DB_EXTRA_PARAMS", "").strip()
    connection_parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={os.getenv('DB_HOST', '')}",
        f"DATABASE={os.getenv('DB_DATABASE', os.getenv('DB_SCHEMA', ''))}",
        f"UID={os.getenv('DB_USER', '')}",
        f"PWD={os.getenv('DB_PASSWORD', '')}",
    ]

    if not extra_params and driver.lower() != "sql server":
        extra_params = "TrustServerCertificate=yes"

    if extra_params:
        connection_parts.extend(
            [part.strip() for part in extra_params.split(";") if part.strip()]
        )

    connection_string = ";".join(connection_parts) + ";"
    timeout = int(os.getenv("DB_TIMEOUT", "5"))
    return pyodbc.connect(connection_string, timeout=timeout)
