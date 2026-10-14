"""Variaveis de ambiente da aplicacao web.

Importar este modulo garante que a configuracao (.env) ja foi carregada, entao
qualquer modulo que leia variavel de ambiente no import deve importar daqui.
"""

from __future__ import annotations

import os

from app_captacao.core.config.environment import initialize_environment

initialize_environment()

# Assina o cookie de sessao. Vazio: chave aleatoria por processo (todos saem ao reiniciar).
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "").strip()

# Tabelas do SQL Server (schema.tabela). Os padroes refletem o banco atual.
USUARIO_TABLE = os.getenv("USUARIO_TABLE", "dbo.CapRecursoUsuario")
OPERACAO_TABLE = os.getenv("OPERACAO_TABLE", "dbo.CapRecursoOperacoes")
RELATORIO_TABLE = os.getenv("RELATORIO_TABLE", "dbo.CapRecursoRelatorio")
RELATORIO_X_OPERACAO_TABLE = os.getenv("RELATORIO_X_OPERACAO_TABLE", "dbo.CapRecursoRelatorio_X_Operacao")
FILTRO_CATALOGO_TABLE = os.getenv("FILTRO_CATALOGO_TABLE", "dbo.CapRecursoFiltro")
FILTRO_X_OPERACAO_TABLE = os.getenv("FILTRO_X_OPERACAO_TABLE", "dbo.CapRecursoFiltro_X_Operacao")
LOG_CONFIG_TABLE = os.getenv("LOG_CONFIG_TABLE", "dbo.CapRecursoLogConfiguracao")
LOG_OPERACAO_TABLE = os.getenv("LOG_OPERACAO_TABLE", "dbo.CapRecursoLogOperacao")

# Pausa temporaria da persistencia de logs. Defina APP_SAVE_LOGS=true para reativar.
SAVE_LOGS = os.getenv("APP_SAVE_LOGS", "false").strip().lower() == "true"
