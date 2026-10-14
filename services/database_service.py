"""
Serviço de Banco de Dados - Conexão SQL Server
================================================

Módulo responsável pela conexão com o banco de dados SQL Server.
Utiliza ODBC para estabelecer comunicação com o banco de dados
configurado via variáveis de ambiente.

Autor: Equipe de Desenvolvimento
Versão: 1.0.0
Data: Abril 2026
"""

import os

import pyodbc
from app_config import initialize_environment

# Carrega variáveis de ambiente
initialize_environment()


def get_db_connection():
    """
    Estabelece conexão com o banco de dados SQL Server.
    
    Utiliza variáveis de ambiente para configuração:
    - DB_DRIVER: Driver ODBC (padrão: SQL Server)
    - DB_HOST: Servidor do banco de dados
    - DB_DATABASE: Nome do banco de dados
    - DB_SCHEMA: Schema do banco (alternativo ao DATABASE)
    - DB_USER: Usuário para conexão
    - DB_PASSWORD: Senha do usuário
    - DB_EXTRA_PARAMS: Parâmetros adicionais de conexão
    - DB_TIMEOUT: Tempo limite em segundos (padrão: 5)
    
    Returns:
        pyodbc.Connection: Objeto de conexão com o banco
    
    Example:
        >>> conn = get_db_connection()
        >>> cursor = conn.cursor()
        >>> cursor.execute("SELECT * FROM tabela")
    """
    driver = os.getenv("DB_DRIVER", "SQL Server")
    extra_params = os.getenv("DB_EXTRA_PARAMS", "").strip()
    connection_parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={os.getenv('DB_HOST', '')}",
        f"DATABASE={os.getenv('DB_DATABASE', os.getenv('DB_SCHEMA', ''))}",
        f"UID={os.getenv('DB_USER', '')}",
        f"PWD={os.getenv('DB_PASSWORD', '')}",
    ]

    # Adiciona certificado de confiança para drivers não-SQL Server
    if not extra_params and driver.lower() != "sql server":
        extra_params = "TrustServerCertificate=yes"

    # Processa parâmetros extras da conexão
    if extra_params:
        connection_parts.extend(
            [part.strip() for part in extra_params.split(";") if part.strip()]
        )

    # Constrói string de conexão
    connection_string = ";".join(connection_parts) + ";"
    timeout = int(os.getenv("DB_TIMEOUT", "5"))
    return pyodbc.connect(connection_string, timeout=timeout)
