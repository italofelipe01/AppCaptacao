"""
AppCaptação - Sistema de Captação e Automação de Relatórios
=============================================================

Aplicação Flask para gestão de usuários, execução de relatórios
automatizados via Selenium e interface web para acompanhamento.

Autor: Equipe de Desenvolvimento
Versão: 1.0.0
Data: Abril 2026
"""

import json
import os
import shutil
import socket
import subprocess
import threading
import time
import traceback
from contextlib import closing
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import webbrowser

import pyodbc
from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app_config import get_static_path, get_template_path, initialize_environment
from services.automacao_service import (
    acao_exige_valor,
    executar_relatorio,
    executar_relatorios_em_sequencia,
)
from services.relatorio_action_service import (
    anexar_botoes_automaticos,
    eh_filtro_opcional_relatorio,
    obter_executor_relatorio,
)
from services.relatorio_service import buscar_relatorio_com_filtros, montar_payload_execucao

# Carrega variáveis de ambiente do arquivo .env
initialize_environment()

# ============================================================
# CONFIGURAÇÃO PRINCIPAL DA APLICAÇÃO FLASK
# ============================================================

app = Flask(
    __name__,
    template_folder=get_template_path(),
    static_folder=get_static_path(),
)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "<valor removido>")


def _wait_for_server(host, port, timeout_seconds=15):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def _get_browser_host(host):
    normalized_host = (host or "").strip()
    if normalized_host in {"", "0.0.0.0", "::"}:
        return "127.0.0.1"
    return normalized_host


def _build_launch_url(host, port):
    browser_host = _get_browser_host(host)
    launch_url = (os.getenv("APP_LAUNCH_URL", "").strip() or "/")

    parsed = urlsplit(launch_url)
    if parsed.scheme and parsed.netloc:
        return launch_url

    path = parsed.path or "/"
    if not path.startswith("/"):
        path = f"/{path}"

    return urlunsplit(("http", f"{browser_host}:{port}", path, parsed.query, parsed.fragment))


def _get_chrome_path():
    chrome_candidates = [
        shutil.which("chrome"),
        shutil.which("chrome.exe"),
        shutil.which("google-chrome"),
        os.path.join(os.getenv("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.getenv("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.getenv("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
    ]

    for candidate in chrome_candidates:
        if candidate and Path(candidate).exists():
            return str(Path(candidate))
    return None


def _open_url_in_browser(target_url):
    chrome_path = _get_chrome_path()
    if chrome_path:
        try:
            subprocess.Popen([chrome_path, target_url])
            return True
        except OSError:
            pass

    if os.name == "nt" and hasattr(os, "startfile"):
        try:
            os.startfile(target_url)
            return True
        except OSError:
            pass

    try:
        return bool(webbrowser.open(target_url, new=2))
    except Exception:
        return False


def _open_browser_when_ready(host, port):
    target_url = _build_launch_url(host, port)
    if not _wait_for_server(host, port):
        return
    _open_url_in_browser(target_url)


def start_browser_thread(host, port):
    browser_thread = threading.Thread(
        target=_open_browser_when_ready,
        args=(host, port),
        daemon=True,
    )
    browser_thread.start()
    return browser_thread


def run_application(use_waitress=False):
    host = os.getenv("APP_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.getenv("APP_PORT", "4732"))
    debug = os.getenv("APP_DEBUG", "false").strip().lower() == "true"

    start_browser_thread(host, port)

    if use_waitress:
        from waitress import serve

        serve(app, host=host, port=port)
        return

    app.run(host=host, port=port, debug=debug)

# ============================================================
# CONFIGURAÇÃO DE TABELAS DO BANCO DE DADOS
# ============================================================

# Mapeamento das tabelas do banco de dados para configuração
# Estas tabelas armazenam a relação entre relatórios e operações,
# filtros disponíveis e usuários do sistema

RELATORIO_X_OPERACAO_TABLE = os.getenv(
    "RELATORIO_X_OPERACAO_TABLE",
    "dbo.CapRecursoRelatorio_X_Operacao",
)
FILTRO_X_OPERACAO_TABLE = os.getenv(
    "FILTRO_X_OPERACAO_TABLE",
    "dbo.CapRecursoFiltro_X_Operacao",
)
FILTRO_CATALOGO_TABLE = os.getenv(
    "FILTRO_CATALOGO_TABLE",
    "dbo.CapRecursoFiltro",
)
USUARIO_TABLE = os.getenv(
    "USUARIO_TABLE",
    "dbo.CapRecursoUsuario",
)
LOG_ACESSO_TABLE = os.getenv(
    "LOG_ACESSO_TABLE",
    "dbo.CapRecursoLogAcesso",
)
LOG_EXECUCAO_TABLE = os.getenv(
    "LOG_EXECUCAO_TABLE",
    "dbo.CapRecursoLogExecucao",
)

# ============================================================
# DEFINIÇÃO DE NÍVEIS DE ACESSO
# ============================================================

# Códigos de acesso para controle de permissões
ACESSO_ADMIN = 1        # Administrador - acesso total ao sistema
ACESSO_OPERACAO = 2     # Cadastro de operação - pode configurar relatórios
ACESSO_EXECUCAO = 3     # Execução - pode apenas executar relatórios


def get_bootstrap_admin():
    """
    Retorna configurações de administrador bootstrap para ambiente de desenvolvimento.
    
    Quando a variável DEV_BOOTSTRAP_ADMIN_ENABLED=true, cria um usuário admin
    temporário para testes sem precisar configurar o banco de dados.
    
    Returns:
        dict: Dicionário com dados do admin ou None se desabilitado
    """
    if os.getenv("DEV_BOOTSTRAP_ADMIN_ENABLED", "false").strip().lower() != "true":
        return None

    return {
        "id": int(os.getenv("DEV_BOOTSTRAP_ADMIN_ID", "999999")),
        "login": os.getenv("DEV_BOOTSTRAP_ADMIN_LOGIN", "admin").strip(),
        "password_hash": os.getenv("DEV_BOOTSTRAP_ADMIN_PASSWORD_HASH", "").strip(),
        "email": os.getenv("DEV_BOOTSTRAP_ADMIN_EMAIL", "admin@local.test").strip(),
        "area": os.getenv("DEV_BOOTSTRAP_ADMIN_AREA", "performance").strip(),
        "access_id": int(os.getenv("DEV_BOOTSTRAP_ADMIN_ACCESS_ID", "1")),
    }


def get_db_connection():
    """
    Estabelece conexão com o banco de dados SQL Server.
    
    Utiliza variáveis de ambiente para configuração:
    - DB_DRIVER: Driver ODBC (padrão: SQL Server)
    - DB_HOST: Servidor do banco
    - DB_DATABASE: Nome do banco de dados
    - DB_USER: Usuário para conexão
    - DB_PASSWORD: Senha do usuário
    - DB_TIMEOUT: Tempo limite em segundos (padrão: 5)
    
    Returns:
        pyodbc.Connection: Objeto de conexão com o banco
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

    if not extra_params and driver.lower() != "sql server":
        extra_params = "TrustServerCertificate=yes"

    if extra_params:
        connection_parts.extend(
            [part.strip() for part in extra_params.split(";") if part.strip()]
        )

    connection_string = ";".join(connection_parts) + ";"
    timeout = int(os.getenv("DB_TIMEOUT", "5"))
    return pyodbc.connect(connection_string, timeout=timeout)


def get_login_ids():
    """
    Obtém IDs de login para operações no banco de dados.
    
    Prioriza sessão atual do usuário, caso contrário usa
    valor padrão da variável de ambiente.
    
    Returns:
        tuple: (id_usuario_criacao, id_usuario_alteracao)
    """
    session_login_id = session.get("user_id")
    if session_login_id:
        return int(session_login_id), int(session_login_id)

    fallback_login_id = int(os.getenv("CAP_OPERACOES_LOGIN_CRIACAO", "1"))
    return fallback_login_id, fallback_login_id


def get_next_id(cursor, table_name, id_column):
    """
    Gera próximo ID disponível para uma tabela.
    
    Utiliza lock no banco para garantir unicidade em
    ambiente com múltiplas requisições simultâneas.
    
    Args:
        cursor: Cursor do banco de dados
        table_name: Nome da tabela
        id_column: Nome da coluna de ID
    
    Returns:
        int: Próximo ID disponível
    """
    cursor.execute(
        f"""
            SELECT ISNULL(MAX({id_column}), 0) + 1 AS ProximoId
            FROM {table_name} WITH (UPDLOCK, HOLDLOCK)
        """
    )
    return cursor.fetchone().ProximoId


# ============================================================
# DECORADORES DE SEGURANÇA
# ============================================================

def login_required(view_func):
    """
    Decorador que exige autenticação para acesso à rota.
    
    Verifica se existe user_id na sessão. Se não existir,
    redireciona para página de login com mensagem de erro.
    
    Args:
        view_func: Função da rota protegida
    
    Returns:
        function: Função wrapper com verificação de login
    """
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Sua sessao expirou ou voce precisa fazer login.", "error")
            return redirect(url_for("index"))
        return view_func(*args, **kwargs)

    return wrapper


def access_required(*allowed_access_ids):
    """
    Decorador que verifica nível de acesso do usuário.
    
    Permite apenas usuários com perfis específicos acessar
    determinadas rotas. Verifica tanto login quanto nível de acesso.
    
    Args:
        *allowed_access_ids: IDs de acesso permitidos
    
    Returns:
        function: Decorador para função de rota
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            if not session.get("user_id"):
                flash("Sua sessao expirou ou voce precisa fazer login.", "error")
                return redirect(url_for("index"))

            if session.get("user_access_id") not in allowed_access_ids:
                flash("Seu perfil nao possui permissao para acessar esta area.", "error")
                return redirect(url_for("main"))

            return view_func(*args, **kwargs)

        return wrapper

    return decorator


# ============================================================
# HOOKS FLASK
# ============================================================

@app.before_request
def load_current_user():
    """
    Hook executado antes de cada requisição.
    
    Carrega dados do usuário atual na variável global 'g'
    para acesso em templates e rotas.
    """
    g.current_user = {
        "id": session.get("user_id"),
        "login": session.get("user_login"),
        "email": session.get("user_email"),
        "area": session.get("user_area"),
        "access_id": session.get("user_access_id"),
    }


@app.context_processor
def inject_auth_context():
    """
    Injeta contexto de autenticação em todos os templates.
    
    Disponibiliza variável 'current_user' em todos os
    templates renderizados pela aplicação.
    """
    return {
        "current_user": g.get("current_user"),
    }


# ============================================================
# GERENCIAMENTO DE SESSÃO E CREDENCIAIS
# ============================================================

def salvar_credenciais_execucao(email="", senha="", sharepoint_link=""):
    """
    Armazena credenciais de execução na sessão do usuário.
    
    Usado para manter dados de login do Sienge e link do
    SharePoint durante a execução de relatórios automatizados.
    
    Args:
        email: Email de login no Sienge
        senha: Senha do usuário
        sharepoint_link: Link para pasta do SharePoint
    """
    session["execucao_email"] = str(email or "").strip()
    session["execucao_senha"] = str(senha or "")
    session["execucao_sharepoint_link"] = str(sharepoint_link or "").strip()


def obter_credenciais_execucao():
    """
    Recupera credenciais de execução armazenadas na sessão.
    
    Returns:
        dict: Dicionário com email, senha e sharepoint_link
    """
    return {
        "email": session.get("execucao_email", ""),
        "senha": session.get("execucao_senha", ""),
        "sharepoint_link": session.get("execucao_sharepoint_link", ""),
    }


# ============================================================
# FUNÇÕES DE CONSULTA E MANIPULAÇÃO DE USUÁRIOS
# ============================================================

def buscar_usuario_por_login(login_usuario):
    """
    Busca usuário no banco de dados pelo login.
    
    Args:
        login_usuario: Nome de login do usuário
    
    Returns:
        Row ou None: Dados do usuário encontrado
    """
    query = f"""
        SELECT
            IdLogin,
            Login,
            Senha,
            Email,
            Area,
            IdAcesso,
            IdAtivo
        FROM {USUARIO_TABLE}
        WHERE Login = ?
    """

    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(query, login_usuario)
        row = cursor.fetchone()

    return row


def buscar_usuario_por_id(id_login):
    """
    Busca usuário no banco de dados pelo ID.
    
    Args:
        id_login: ID do usuário
    
    Returns:
        Row ou None: Dados do usuário encontrado
    """
    query = f"""
        SELECT
            IdLogin,
            Login,
            Email,
            Area,
            IdAcesso,
            IdAtivo,
            DataCriacao
        FROM {USUARIO_TABLE}
        WHERE IdLogin = ?
    """

    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(query, id_login)
        row = cursor.fetchone()

    return row


def criar_usuario(login_usuario, senha, email, area, id_acesso):
    """
    Cria novo usuário no banco de dados.
    
    Args:
        login_usuario: Nome de login
        senha: Senha em texto plano (será hasheada)
        email: Email do usuário
        area: Área/setor do usuário
        id_acesso: Nível de acesso (1=Admin, 2=Operação, 3=Execução)
    
    Returns:
        bool: True se criado com sucesso, False se login/email já existe
    """
    senha_hash = generate_password_hash(senha, method="scrypt")

    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"""
                SELECT COUNT(1) AS Total
                FROM {USUARIO_TABLE}
                WHERE Login = ? OR Email = ?
            """,
            login_usuario,
            email,
        )
        if cursor.fetchone().Total:
            return False

        cursor.execute(
            f"""
                INSERT INTO {USUARIO_TABLE} (
                    Login,
                    Senha,
                    Email,
                    Area,
                    IdAcesso,
                    IdAtivo,
                    DataCriacao
                )
                VALUES (?, ?, ?, ?, ?, 1, GETDATE())
            """,
            login_usuario,
            senha_hash,
            email,
            area,
            id_acesso,
        )
        connection.commit()

    return True


def listar_usuarios(filtro_busca="", filtro_status="ativos"):
    """
    Lista usuários com filtros opcionais de busca e status.
    
    Args:
        filtro_busca: Texto para buscar em login, email ou área
        filtro_status: 'ativos', 'inativos' ou 'todos'
    
    Returns:
        list: Lista de dicionários com dados dos usuários
    """
    busca_like = f"%{filtro_busca}%"
    filtro_status = (filtro_status or "ativos").strip().lower()
    if filtro_status not in {"ativos", "inativos", "todos"}:
        filtro_status = "ativos"

    query = f"""
        SELECT
            IdLogin,
            Login,
            Email,
            Area,
            IdAcesso,
            IdAtivo,
            DataCriacao
        FROM {USUARIO_TABLE}
        WHERE (
            ? = 'todos'
            OR (? = 'ativos' AND IdAtivo = 1)
            OR (? = 'inativos' AND IdAtivo = 0)
        )
          AND (? = '' OR Login LIKE ? OR Email LIKE ? OR Area LIKE ?)
        ORDER BY IdAtivo DESC, Login
    """

    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(
            query,
            filtro_status,
            filtro_status,
            filtro_status,
            filtro_busca,
            busca_like,
            busca_like,
            busca_like,
        )
        rows = cursor.fetchall()

    perfis = {
        ACESSO_ADMIN: "Administrador",
        ACESSO_OPERACAO: "Cadastro de operacao",
        ACESSO_EXECUCAO: "Execucao",
    }

    return [
        {
            "id": row.IdLogin,
            "login": row.Login,
            "email": row.Email,
            "area": row.Area,
            "id_acesso": row.IdAcesso,
            "perfil": perfis.get(row.IdAcesso, f"Acesso {row.IdAcesso}"),
            "ativo": bool(row.IdAtivo),
            "status": "Ativo" if row.IdAtivo else "Inativo",
            "data_criacao": row.DataCriacao.strftime("%d/%m/%Y %H:%M") if row.DataCriacao else "-",
        }
        for row in rows
    ]


def atualizar_usuario(id_login, email, area, id_acesso, nova_senha=""):
    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"""
                SELECT COUNT(1) AS Total
                FROM {USUARIO_TABLE}
                WHERE Email = ? AND IdLogin <> ?
            """,
            email,
            id_login,
        )
        if cursor.fetchone().Total:
            return False

        if nova_senha:
            senha_hash = generate_password_hash(nova_senha, method="scrypt")
            cursor.execute(
                f"""
                    UPDATE {USUARIO_TABLE}
                    SET
                        Email = ?,
                        Area = ?,
                        IdAcesso = ?,
                        Senha = ?,
                        DataAlteracao = GETDATE()
                    WHERE IdLogin = ?
                """,
                email,
                area,
                id_acesso,
                senha_hash,
                id_login,
            )
        else:
            cursor.execute(
                f"""
                    UPDATE {USUARIO_TABLE}
                    SET
                        Email = ?,
                        Area = ?,
                        IdAcesso = ?,
                        DataAlteracao = GETDATE()
                    WHERE IdLogin = ?
                """,
                email,
                area,
                id_acesso,
                id_login,
            )

        connection.commit()

    return True


def inativar_usuario(id_login):
    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"""
                UPDATE {USUARIO_TABLE}
                SET
                    IdAtivo = 0,
                    DataAlteracao = GETDATE()
                WHERE IdLogin = ?
            """,
            id_login,
        )
        connection.commit()


def atualizar_propria_senha(id_login, nova_senha):
    senha_hash = generate_password_hash(nova_senha, method="scrypt")

    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"""
                UPDATE {USUARIO_TABLE}
                SET
                    Senha = ?,
                    DataAlteracao = GETDATE()
                WHERE IdLogin = ?
            """,
            senha_hash,
            id_login,
        )
        connection.commit()


def listar_operacoes(filtro_nome=""):
    like_filter = f"%{filtro_nome}%"
    filtro_visibilidade, parametros_visibilidade = construir_filtro_visibilidade_operacoes("cro")
    query = """
        SELECT
            cro.IdCapRecursoOperacoes,
            cro.NomeOperacao,
            cro.IdAtivo,
            cro.DataCriacao
        FROM dbo.CapRecursoOperacoes cro
        WHERE cro.IdAtivo = 1
          AND (? = '' OR NomeOperacao LIKE ?)
          AND {filtro_visibilidade}
        ORDER BY DataCriacao DESC, IdCapRecursoOperacoes DESC
    """.format(filtro_visibilidade=filtro_visibilidade)

    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(query, filtro_nome, like_filter, *parametros_visibilidade)
        rows = cursor.fetchall()

    return [
        {
            "id": row.IdCapRecursoOperacoes,
            "nome": row.NomeOperacao,
            "ativo": bool(row.IdAtivo),
            "status": "Ativa" if row.IdAtivo else "Inativa",
            "data_criacao": row.DataCriacao.strftime("%d/%m/%Y %H:%M") if row.DataCriacao else "-",
        }
        for row in rows
    ]


def listar_operacoes_execucao():
    filtro_visibilidade, parametros_visibilidade = construir_filtro_visibilidade_operacoes("cro")
    query = """
        SELECT
            cro.IdCapRecursoOperacoes,
            cro.NomeOperacao
        FROM dbo.CapRecursoOperacoes cro
        WHERE cro.IdAtivo = 1
          AND {filtro_visibilidade}
        ORDER BY NomeOperacao
    """.format(filtro_visibilidade=filtro_visibilidade)

    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(query, *parametros_visibilidade)
        rows = cursor.fetchall()

    return [
        {
            "id": row.IdCapRecursoOperacoes,
            "nome": row.NomeOperacao,
        }
        for row in rows
    ]


def construir_filtro_visibilidade_operacoes(operacao_alias="cro"):
    if session.get("user_access_id") == ACESSO_ADMIN:
        return "1 = 1", []

    usuario_id = session.get("user_id")
    area_usuario = normalizar_area_comparacao(session.get("user_area"))
    condicoes = [f"{operacao_alias}.IdLoginCriacao = ?"]
    parametros = [usuario_id]

    if area_usuario:
        condicoes.append(
            f"""
                EXISTS (
                    SELECT 1
                    FROM {USUARIO_TABLE} cru
                    WHERE cru.IdLogin = {operacao_alias}.IdLoginCriacao
                      AND LOWER(LTRIM(RTRIM(ISNULL(cru.Area, '')))) = ?
                )
            """
        )
        parametros.append(area_usuario)

    return "(" + " OR ".join(condicoes) + ")", parametros


def normalizar_area_comparacao(area):
    return str(area or "").strip().lower()


def usuario_pode_acessar_operacao(operacao_id, exigir_ativa=True):
    filtro_visibilidade, parametros_visibilidade = construir_filtro_visibilidade_operacoes("cro")
    filtro_ativo = "AND cro.IdAtivo = 1" if exigir_ativa else ""
    query = f"""
        SELECT COUNT(1) AS Total
        FROM dbo.CapRecursoOperacoes cro
        WHERE cro.IdCapRecursoOperacoes = ?
          {filtro_ativo}
          AND {filtro_visibilidade}
    """

    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(query, operacao_id, *parametros_visibilidade)
        row = cursor.fetchone()

    return bool(row and row.Total)


def listar_relatorios_disponiveis():
    query = """
        SELECT
            IdCapRecursoRelatorio,
            NomeRelatorio,
            UrlRelatorio
        FROM dbo.CapRecursoRelatorio
        WHERE IdAtivo = 1
        ORDER BY NomeRelatorio
    """

    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()

    return [
        {
            "id": row.IdCapRecursoRelatorio,
            "nome": row.NomeRelatorio,
            "url": row.UrlRelatorio or "",
        }
        for row in rows
    ]


def buscar_relatorio_por_id(id_relatorio):
    query = """
        SELECT
            IdCapRecursoRelatorio,
            NomeRelatorio,
            UrlRelatorio
        FROM dbo.CapRecursoRelatorio
        WHERE IdCapRecursoRelatorio = ?
          AND IdAtivo = 1
    """

    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(query, id_relatorio)
        row = cursor.fetchone()

    if not row:
        return None

    return {
        "id": row.IdCapRecursoRelatorio,
        "nome": row.NomeRelatorio,
        "url": row.UrlRelatorio or "",
    }


def listar_filtros_disponiveis():
    query = f"""
        SELECT
            IdFiltro,
            NomeFiltro
        FROM {FILTRO_CATALOGO_TABLE}
        WHERE IdAtivo = 1
        ORDER BY NomeFiltro
    """

    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()

    return [{"id": row.IdFiltro, "nome": row.NomeFiltro} for row in rows]


def listar_filtros_relatorio(id_relatorio):
    query = f"""
        SELECT
            IdFiltro,
            NomeFiltro,
            TipoCampo,
            TipoCampoValor,
            IframeIndex,
            CampoIdentificador,
            Acao,
            IdCapRecursoRelatorio
        FROM {FILTRO_CATALOGO_TABLE}
        WHERE IdAtivo = 1
          AND IdCapRecursoRelatorio = ?
        ORDER BY IdFiltro
    """

    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(query, id_relatorio)
        rows = cursor.fetchall()

    return [
        {
            "id": row.IdFiltro,
            "nome": row.NomeFiltro,
            "tipo_campo": (row.TipoCampo or "").strip().upper(),
            "tipo_campo_valor": (row.TipoCampoValor or "").strip().upper(),
            "iframe_index": int(row.IframeIndex or 0),
            "campo_identificador": row.CampoIdentificador,
            "acao": (row.Acao or "").strip().lower(),
            "id_relatorio": row.IdCapRecursoRelatorio,
        }
        for row in rows
    ]


def coletar_valores_filtros(relatorio, origem_dados):
    valores = {}
    parametros_extras = {}
    if isinstance(origem_dados, dict):
        parametros_extras = origem_dados.get("parametros") or {}

    for filtro in relatorio.get("filtros", []):
        chave = f"filtro_{filtro['id']}"
        valor = origem_dados.getlist(chave) if hasattr(origem_dados, "getlist") else None

        if valor:
            valor = valor if len(valor) > 1 else valor[0]
        else:
            valor = origem_dados.get(chave)

        if valor in (None, "") and filtro["nome"]:
            valor = origem_dados.get(filtro["nome"])

        if valor in (None, "") and isinstance(parametros_extras, dict):
            valor = parametros_extras.get(chave)
            if valor in (None, "") and filtro["nome"]:
                valor = parametros_extras.get(filtro["nome"])

        valores[chave] = valor
    return valores


def validar_filtros_preenchidos(relatorio, valores_filtros):
    campos_pendentes = []

    for filtro in relatorio.get("filtros", []):
        if not acao_exige_valor(filtro.get("acao")):
            continue

        if eh_filtro_opcional_relatorio(relatorio, filtro):
            continue

        chave = f"filtro_{filtro['id']}"
        valor = valores_filtros.get(chave)

        if isinstance(valor, list):
            possui_valor = any(str(item).strip() for item in valor)
        else:
            possui_valor = bool(str(valor or "").strip())

        if not possui_valor:
            campos_pendentes.append(filtro["nome"])

    return campos_pendentes


def iniciar_execucao_automacao(email, senha, relatorio_config, log_execucao_id=None):
    def _runner():
        resumo_filtros = resumir_filtros_para_log(relatorio_config.get("filtros", []))
        if log_execucao_id:
            try:
                atualizar_log_execucao(
                    log_execucao_id,
                    "processando",
                    payload_resultado={
                        "etapa": "processando",
                        "empresa": resumo_filtros.get("empresa", []),
                        "empreendimento": resumo_filtros.get("empreendimento", []),
                        "filtros_recebidos": resumo_filtros.get("filtros", []),
                    },
                    observacao="Execucao iniciada em background.",
                )
            except pyodbc.Error:
                app.logger.exception("Nao foi possivel atualizar o log %s para processando.", log_execucao_id)

        try:
            executar_relatorio(email, senha, relatorio_config)
            if log_execucao_id:
                atualizar_log_execucao(
                    log_execucao_id,
                    "sucesso",
                    payload_resultado={
                        "relatorio_id": relatorio_config.get("id"),
                        "relatorio_nome": relatorio_config.get("nome"),
                        "filtros_processados": len(relatorio_config.get("filtros", [])),
                        "empresa": resumo_filtros.get("empresa", []),
                        "empreendimento": resumo_filtros.get("empreendimento", []),
                        "filtros_executados": resumo_filtros.get("filtros", []),
                        "resultado": "sucesso",
                    },
                    observacao="Execucao finalizada com sucesso.",
                )
        except Exception:
            app.logger.exception(
                "Erro na execucao da automacao para o relatorio %s.",
                relatorio_config.get("id"),
            )
            if log_execucao_id:
                try:
                    atualizar_log_execucao(
                        log_execucao_id,
                        "erro",
                        erro={
                            "mensagem": "Erro na execucao da automacao do relatorio.",
                            "traceback": traceback.format_exc(),
                            "relatorio_id": relatorio_config.get("id"),
                            "empresa": resumo_filtros.get("empresa", []),
                            "empreendimento": resumo_filtros.get("empreendimento", []),
                            "filtros_tentados": resumo_filtros.get("filtros", []),
                        },
                        observacao="Execucao finalizada com erro.",
                    )
                except pyodbc.Error:
                    app.logger.exception("Nao foi possivel atualizar o log %s com erro.", log_execucao_id)

    thread = threading.Thread(
        target=_runner,
        daemon=True,
    )
    thread.start()
    return thread


def iniciar_execucao_automacao_operacao(
    email,
    senha,
    relatorios_config,
    log_execucao_id=None,
    modo_execucao="parceiros",
):
    logs_relatorios = []
    for relatorio in relatorios_config:
        resumo_filtros = resumir_filtros_para_log(relatorio.get("filtros", []))
        log_relatorio_id = None
        payload_log_relatorio = {
            "tipo_execucao": "relatorio",
            "modo_execucao": modo_execucao,
            "origem_execucao": "operacao",
            "operacao_id": relatorio.get("id_operacao"),
            "operacao_nome": relatorio.get("nome_operacao"),
            "relatorio": {
                "id": relatorio.get("id"),
                "nome": relatorio.get("nome"),
            },
            "resumo_filtros": resumo_filtros,
            "sharepoint_link": relatorio.get("sharepoint_link"),
        }
        try:
            log_relatorio_id = criar_log_execucao(
                "relatorio",
                modo_execucao,
                "aguardando",
                payload_entrada=payload_log_relatorio,
                id_operacao=relatorio.get("id_operacao"),
                nome_operacao=relatorio.get("nome_operacao"),
                id_relatorio=relatorio.get("id"),
                nome_relatorio=relatorio.get("nome"),
                observacao="Execucao do relatorio criada a partir da operacao.",
            )
        except pyodbc.Error:
            app.logger.exception(
                "Nao foi possivel criar log individual do relatorio %s na operacao %s.",
                relatorio.get("id"),
                relatorio.get("id_operacao"),
            )
        logs_relatorios.append(
            {
                "relatorio_id": relatorio.get("id"),
                "relatorio_nome": relatorio.get("nome"),
                "resumo_filtros": resumo_filtros,
                "log_id": log_relatorio_id,
            }
        )

    def _runner():
        relatorios_resumo = []
        for relatorio in relatorios_config:
            resumo_filtros = resumir_filtros_para_log(relatorio.get("filtros", []))
            relatorios_resumo.append(
                {
                    "id": relatorio.get("id"),
                    "nome": relatorio.get("nome"),
                    "empresa": resumo_filtros.get("empresa", []),
                    "empreendimento": resumo_filtros.get("empreendimento", []),
                    "filtros": resumo_filtros.get("filtros", []),
                }
            )
        if log_execucao_id:
            try:
                atualizar_log_execucao(
                    log_execucao_id,
                    "processando",
                    payload_resultado={
                        "etapa": "processando",
                        "relatorios": relatorios_resumo,
                    },
                    observacao="Execucao da operacao iniciada em background.",
                )
            except pyodbc.Error:
                app.logger.exception("Nao foi possivel atualizar o log %s para processando.", log_execucao_id)

        try:
            def _atualizar_log_relatorio(status_evento, relatorio_config, detalhe=None):
                detalhe = detalhe or {}
                log_relatorio = next(
                    (
                        item
                        for item in logs_relatorios
                        if item.get("relatorio_id") == relatorio_config.get("id")
                    ),
                    None,
                )
                if not log_relatorio or not log_relatorio.get("log_id"):
                    return

                payload_base = {
                    "relatorio_id": relatorio_config.get("id"),
                    "relatorio_nome": relatorio_config.get("nome"),
                    "empresa": log_relatorio.get("resumo_filtros", {}).get("empresa", []),
                    "empreendimento": log_relatorio.get("resumo_filtros", {}).get("empreendimento", []),
                    "filtros_executados": log_relatorio.get("resumo_filtros", {}).get("filtros", []),
                    "indice": detalhe.get("indice"),
                    "total": detalhe.get("total"),
                }
                try:
                    if status_evento == "processando":
                        atualizar_log_execucao(
                            log_relatorio["log_id"],
                            "processando",
                            payload_resultado={**payload_base, "etapa": "processando"},
                            observacao="Execucao do relatorio iniciada em background.",
                        )
                    elif status_evento == "sucesso":
                        atualizar_log_execucao(
                            log_relatorio["log_id"],
                            "sucesso",
                            payload_resultado={**payload_base, "resultado": "sucesso"},
                            observacao="Execucao do relatorio finalizada com sucesso.",
                        )
                    elif status_evento == "erro":
                        atualizar_log_execucao(
                            log_relatorio["log_id"],
                            "erro",
                            erro={
                                **payload_base,
                                "mensagem": detalhe.get("mensagem"),
                                "traceback": detalhe.get("traceback"),
                            },
                            observacao="Execucao do relatorio finalizada com erro.",
                        )
                except pyodbc.Error:
                    app.logger.exception(
                        "Nao foi possivel atualizar o log individual %s do relatorio %s.",
                        log_relatorio["log_id"],
                        relatorio_config.get("id"),
                    )

            resultado_execucao = executar_relatorios_em_sequencia(
                email,
                senha,
                relatorios_config,
                on_report_event=_atualizar_log_relatorio,
            )
            houve_falha = bool(resultado_execucao.get("falhas"))
            if log_execucao_id and not houve_falha:
                atualizar_log_execucao(
                    log_execucao_id,
                    "sucesso",
                    payload_resultado={
                        "quantidade_relatorios": len(relatorios_config),
                        "relatorios": relatorios_resumo,
                        "sucessos": resultado_execucao.get("sucessos", []),
                        "falhas": resultado_execucao.get("falhas", []),
                        "resultado": "sucesso",
                    },
                    observacao="Execucao da operacao finalizada com sucesso.",
                )
            elif log_execucao_id:
                atualizar_log_execucao(
                    log_execucao_id,
                    "erro",
                    payload_resultado={
                        "quantidade_relatorios": len(relatorios_config),
                        "relatorios": relatorios_resumo,
                        "sucessos": resultado_execucao.get("sucessos", []),
                        "falhas": resultado_execucao.get("falhas", []),
                        "resultado": "erro",
                    },
                    erro={
                        "mensagem": "Um ou mais relatorios da operacao finalizaram com erro.",
                        "falhas": resultado_execucao.get("falhas", []),
                    },
                    observacao="Execucao da operacao finalizada com erro em um ou mais relatorios.",
                )
        except Exception:
            app.logger.exception(
                "Erro na execucao sequencial da automacao da operacao."
            )
            if log_execucao_id:
                try:
                    atualizar_log_execucao(
                        log_execucao_id,
                        "erro",
                        erro={
                            "mensagem": "Erro na execucao sequencial da operacao.",
                            "traceback": traceback.format_exc(),
                            "quantidade_relatorios": len(relatorios_config),
                            "relatorios": relatorios_resumo,
                        },
                        observacao="Execucao da operacao finalizada com erro.",
                    )
                except pyodbc.Error:
                    app.logger.exception("Nao foi possivel atualizar o log %s com erro.", log_execucao_id)

    thread = threading.Thread(
        target=_runner,
        daemon=True,
    )
    thread.start()
    return thread


def obter_texto(dados, chave, padrao=""):
    valor = dados.get(chave, padrao)
    if valor is None:
        return padrao
    return str(valor).strip()


def sanitizar_payload_log(valor, chave_atual=""):
    chaves_sensiveis = {"senha", "password", "token", "secret"}
    chave_normalizada = str(chave_atual or "").strip().lower()
    if chave_normalizada in chaves_sensiveis:
        return "***"

    if isinstance(valor, dict):
        return {
            str(chave): sanitizar_payload_log(subvalor, chave)
            for chave, subvalor in valor.items()
        }

    if isinstance(valor, list):
        return [sanitizar_payload_log(item, chave_atual) for item in valor]

    if isinstance(valor, tuple):
        return [sanitizar_payload_log(item, chave_atual) for item in valor]

    if hasattr(valor, "isoformat"):
        try:
            return valor.isoformat()
        except TypeError:
            return str(valor)

    return valor


def serializar_json_log(payload):
    if payload in (None, "", [], {}):
        return None
    return json.dumps(
        sanitizar_payload_log(payload),
        ensure_ascii=False,
        default=str,
    )


def carregar_json_seguro(payload_json):
    texto = str(payload_json or "").strip()
    if not texto:
        return {}
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        return {}


def extrair_lista_valores_filtro(valor):
    if valor is None:
        return []
    if isinstance(valor, list):
        return [str(item).strip() for item in valor if str(item).strip()]

    texto = str(valor).strip()
    if not texto:
        return []

    if "|" in texto:
        return [item.strip() for item in texto.split("|") if item.strip()]
    if "," in texto:
        return [item.strip() for item in texto.split(",") if item.strip()]

    return [texto]


def resumir_filtros_para_log(filtros):
    resumo = {
        "empresa": [],
        "empreendimento": [],
        "filtros": [],
    }

    for filtro in filtros or []:
        nome = str(filtro.get("nome") or filtro.get("nome_filtro") or "").strip()
        campo = str(filtro.get("campo_identificador") or "").strip()
        acao = str(filtro.get("acao") or "").strip().lower()
        valores = extrair_lista_valores_filtro(filtro.get("valor"))
        item = {
            "id": filtro.get("id") or filtro.get("id_filtro"),
            "nome": nome,
            "campo_identificador": campo,
            "acao": acao,
            "valores": valores,
        }
        resumo["filtros"].append(item)

        nome_campo = f"{nome} {campo}".lower()
        if "empresa" in nome_campo:
            resumo["empresa"].extend(valores)
        if "empreend" in nome_campo or "centro_custo" in nome_campo or "centro custo" in nome_campo:
            resumo["empreendimento"].extend(valores)

    resumo["empresa"] = list(dict.fromkeys(resumo["empresa"]))
    resumo["empreendimento"] = list(dict.fromkeys(resumo["empreendimento"]))
    return resumo


def resumir_relatorios_para_log(relatorios):
    resumo = {
        "empresa": [],
        "empreendimento": [],
        "filtros": [],
    }

    for relatorio in relatorios or []:
        resumo_relatorio = relatorio.get("resumo_filtros") or {}
        resumo["empresa"].extend(resumo_relatorio.get("empresa", []))
        resumo["empreendimento"].extend(resumo_relatorio.get("empreendimento", []))
        filtros = resumo_relatorio.get("filtros", [])
        if filtros:
            resumo["filtros"].append(
                {
                    "relatorio_id": relatorio.get("id"),
                    "relatorio_nome": relatorio.get("nome"),
                    "filtros": filtros,
                }
            )

    resumo["empresa"] = list(dict.fromkeys([item for item in resumo["empresa"] if item]))
    resumo["empreendimento"] = list(dict.fromkeys([item for item in resumo["empreendimento"] if item]))
    return resumo


def obter_metadados_requisicao():
    return {
        "origem": "api" if request.path.startswith("/api/") or request.is_json else "web",
        "rota": request.path,
        "metodo": request.method,
        "ip_usuario": (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.remote_addr
            or ""
        ),
        "user_agent": request.headers.get("User-Agent", "")[:500],
    }


def obter_contexto_usuario_log(usuario=None):
    usuario = usuario or {}
    return {
        "id_login": usuario.get("id") if usuario.get("id") is not None else session.get("user_id"),
        "login": usuario.get("login") or session.get("user_login") or "",
        "email": usuario.get("email") or session.get("user_email") or "",
        "area": usuario.get("area") or session.get("user_area") or "",
        "id_acesso": (
            usuario.get("access_id")
            if usuario.get("access_id") is not None
            else session.get("user_access_id")
        ),
    }


def registrar_log_acesso(tipo_evento, detalhe="", payload=None, usuario=None):
    contexto_usuario = obter_contexto_usuario_log(usuario)
    metadados = obter_metadados_requisicao()
    payload_completo = {
        "usuario": contexto_usuario,
        "request": metadados,
        "payload": payload or {},
    }

    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"""
                INSERT INTO {LOG_ACESSO_TABLE} (
                    IdLogin,
                    LoginUsuario,
                    EmailUsuario,
                    AreaUsuario,
                    IdAcesso,
                    TipoEvento,
                    Detalhe,
                    Origem,
                    IpUsuario,
                    UserAgent,
                    PayloadJson,
                    DataEvento
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE())
            """,
            contexto_usuario.get("id_login"),
            contexto_usuario.get("login"),
            contexto_usuario.get("email"),
            contexto_usuario.get("area"),
            contexto_usuario.get("id_acesso"),
            tipo_evento,
            detalhe,
            metadados.get("origem"),
            metadados.get("ip_usuario"),
            metadados.get("user_agent"),
            serializar_json_log(payload_completo),
        )
        connection.commit()


def criar_log_execucao(
    tipo_execucao,
    modo_execucao,
    status_execucao,
    payload_entrada=None,
    id_operacao=None,
    nome_operacao="",
    id_relatorio=None,
    nome_relatorio="",
    observacao="",
    responsavel="",
):
    contexto_usuario = obter_contexto_usuario_log()
    query = f"""
        INSERT INTO {LOG_EXECUCAO_TABLE} (
            IdLogin,
            LoginUsuario,
            EmailUsuario,
            AreaUsuario,
            TipoExecucao,
            ModoExecucao,
            IdCapRecursoOperacoes,
            NomeOperacao,
            IdCapRecursoRelatorio,
            NomeRelatorio,
            StatusExecucao,
            Responsavel,
            DataInicio,
            DataAtualizacao,
            PayloadEntradaJson,
            Observacao
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE(), GETDATE(), ?, ?);
        SELECT CAST(SCOPE_IDENTITY() AS BIGINT) AS NovoId;
    """

    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(
            query,
            contexto_usuario.get("id_login"),
            contexto_usuario.get("login"),
            contexto_usuario.get("email"),
            contexto_usuario.get("area"),
            tipo_execucao,
            modo_execucao,
            id_operacao,
            nome_operacao or None,
            id_relatorio,
            nome_relatorio or None,
            status_execucao,
            responsavel or contexto_usuario.get("login"),
            serializar_json_log(payload_entrada),
            observacao or None,
        )
        row = cursor.fetchone()
        connection.commit()

    return int(row.NovoId)


def atualizar_log_execucao(log_id, status_execucao, payload_resultado=None, erro=None, observacao=None):
    set_data_fim = ", DataFim = GETDATE()" if status_execucao in {"sucesso", "erro"} else ""
    query = f"""
        UPDATE {LOG_EXECUCAO_TABLE}
        SET
            StatusExecucao = ?,
            DataAtualizacao = GETDATE()
            {set_data_fim},
            PayloadResultadoJson = COALESCE(?, PayloadResultadoJson),
            ErroJson = COALESCE(?, ErroJson),
            Observacao = COALESCE(?, Observacao)
        WHERE IdCapRecursoLogExecucao = ?
    """

    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(
            query,
            status_execucao,
            serializar_json_log(payload_resultado),
            serializar_json_log(erro),
            observacao,
            log_id,
        )
        connection.commit()


def listar_logs_acesso(filtros):
    like_usuario = f"%{filtros.get('usuario', '')}%"
    query = f"""
        SELECT
            IdCapRecursoLogAcesso,
            LoginUsuario,
            TipoEvento,
            Detalhe,
            DataEvento,
            PayloadJson
        FROM {LOG_ACESSO_TABLE}
        WHERE (? = '' OR LoginUsuario LIKE ?)
          AND (? = '' OR TipoEvento = ?)
          AND (? = '' OR DataEvento >= CAST(? AS DATETIME))
          AND (? = '' OR DataEvento < DATEADD(DAY, 1, CAST(? AS DATETIME)))
        ORDER BY DataEvento DESC, IdCapRecursoLogAcesso DESC
    """

    parametros = [
        filtros.get("usuario", ""),
        like_usuario,
        filtros.get("tipo_evento", ""),
        filtros.get("tipo_evento", ""),
        filtros.get("data_inicio", ""),
        filtros.get("data_inicio", ""),
        filtros.get("data_fim", ""),
        filtros.get("data_fim", ""),
    ]

    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(query, *parametros)
        rows = cursor.fetchall()

    return [
        {
            "id": row.IdCapRecursoLogAcesso,
            "usuario": row.LoginUsuario or "-",
            "evento": row.TipoEvento or "-",
            "detalhe": row.Detalhe or "-",
            "data_evento": row.DataEvento.strftime("%d/%m/%Y %H:%M:%S") if row.DataEvento else "-",
            "payload_json": row.PayloadJson or "",
        }
        for row in rows
    ]


def listar_logs_execucao(filtros):
    like_operacao = f"%{filtros.get('nome_operacao', '')}%"
    like_responsavel = f"%{filtros.get('responsavel', '')}%"
    query = f"""
        SELECT
            IdCapRecursoLogExecucao,
            TipoExecucao,
            NomeOperacao,
            NomeRelatorio,
            StatusExecucao,
            Responsavel,
            DataAtualizacao,
            Observacao,
            PayloadEntradaJson,
            PayloadResultadoJson,
            ErroJson
        FROM {LOG_EXECUCAO_TABLE}
        WHERE (? = '' OR NomeOperacao LIKE ?)
          AND (? = '' OR StatusExecucao = ?)
          AND (? = '' OR Responsavel LIKE ?)
          AND (? = '' OR DataInicio >= CAST(? AS DATETIME))
        ORDER BY DataInicio DESC, IdCapRecursoLogExecucao DESC
    """

    parametros = [
        filtros.get("nome_operacao", ""),
        like_operacao,
        filtros.get("status", ""),
        filtros.get("status", ""),
        filtros.get("responsavel", ""),
        like_responsavel,
        filtros.get("data_inicio", ""),
        filtros.get("data_inicio", ""),
    ]

    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(query, *parametros)
        rows = cursor.fetchall()

    registros = []
    for row in rows:
        payload_entrada = carregar_json_seguro(row.PayloadEntradaJson)
        payload_resultado = carregar_json_seguro(row.PayloadResultadoJson)
        payload_erro = carregar_json_seguro(row.ErroJson)
        resumo_relatorios_entrada = resumir_relatorios_para_log(payload_entrada.get("relatorios", []))

        empresa = (
            payload_resultado.get("empresa")
            or payload_entrada.get("resumo_filtros", {}).get("empresa")
            or resumo_relatorios_entrada.get("empresa")
            or []
        )
        empreendimento = (
            payload_resultado.get("empreendimento")
            or payload_entrada.get("resumo_filtros", {}).get("empreendimento")
            or resumo_relatorios_entrada.get("empreendimento")
            or []
        )
        filtros_resumo = (
            payload_resultado.get("filtros_executados")
            or payload_resultado.get("filtros_recebidos")
            or payload_erro.get("filtros_tentados")
            or payload_entrada.get("resumo_filtros", {}).get("filtros")
            or resumo_relatorios_entrada.get("filtros")
            or []
        )

        registros.append(
            {
                "id": row.IdCapRecursoLogExecucao,
                "tipo_execucao": row.TipoExecucao or "-",
                "nome_operacao": row.NomeOperacao or "-",
                "nome_relatorio": row.NomeRelatorio or "-",
                "status": row.StatusExecucao or "-",
                "responsavel": row.Responsavel or "-",
                "atualizacao": row.DataAtualizacao.strftime("%d/%m/%Y %H:%M:%S") if row.DataAtualizacao else "-",
                "observacao": row.Observacao or "",
                "empresa": empresa,
                "empreendimento": empreendimento,
                "filtros_resumo": filtros_resumo,
                "payload_entrada_json": row.PayloadEntradaJson or "",
                "payload_resultado_json": row.PayloadResultadoJson or "",
                "erro_json": row.ErroJson or "",
            }
        )

    return registros


def listar_relatorios_operacao(operacao_id):
    query = f"""
        SELECT
            ro.IdCapRecursoRelatorioOperacao,
            ro.IdCapRecursoRelatorio,
            r.NomeRelatorio
        FROM {RELATORIO_X_OPERACAO_TABLE} ro
        INNER JOIN dbo.CapRecursoRelatorio r
            ON r.IdCapRecursoRelatorio = ro.IdCapRecursoRelatorio
        WHERE ro.IdCapRecursoOperacoes = ?
          AND ro.IdAtivo = 1
        ORDER BY r.NomeRelatorio
    """

    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(query, operacao_id)
        rows = cursor.fetchall()

    return [
        {
            "id_relatorio_operacao": row.IdCapRecursoRelatorioOperacao,
            "id_relatorio": row.IdCapRecursoRelatorio,
            "nome_relatorio": row.NomeRelatorio,
        }
        for row in rows
    ]


def dividir_nome_tabela(table_name):
    partes = [parte.strip("[] ") for parte in table_name.split(".")]
    if len(partes) == 2:
        return partes[0], partes[1]
    return "dbo", partes[0]


def coluna_existe(cursor, table_name, column_name):
    schema, tabela = dividir_nome_tabela(table_name)
    cursor.execute(
        """
            SELECT COUNT(1) AS Total
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = ?
              AND TABLE_NAME = ?
              AND COLUMN_NAME = ?
        """,
        schema,
        tabela,
        column_name,
    )
    return bool(cursor.fetchone().Total)


def obter_coluna_valor_filtro(cursor):
    for coluna in ("Valor", "ValorPadrao", "ValorFiltro"):
        if coluna_existe(cursor, FILTRO_X_OPERACAO_TABLE, coluna):
            return coluna
    return None


def formatar_valor_filtro(valor, tipo_campo_valor=""):
    if valor is None:
        return ""

    tipo_normalizado = (tipo_campo_valor or "").strip().upper()

    if tipo_normalizado == "CLICK":
        return ""

    if tipo_normalizado == "DATE" and hasattr(valor, "strftime"):
        return valor.strftime("%Y-%m-%d")

    return str(valor)


def listar_filtros_operacao_relatorio(operacao_id, id_relatorio):
    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        coluna_valor = obter_coluna_valor_filtro(cursor)
        coluna_relatorio_existe = coluna_existe(
            cursor,
            FILTRO_X_OPERACAO_TABLE,
            "IdCapRecursoRelatorio",
        )
        valor_select = (
            f"fo.{coluna_valor} AS Valor"
            if coluna_valor
            else "CAST('' AS varchar(255)) AS Valor"
        )
        filtro_relatorio_operacao = (
            "AND fo.IdCapRecursoRelatorio = ?"
            if coluna_relatorio_existe
            else ""
        )
        parametros = [operacao_id]
        if coluna_relatorio_existe:
            parametros.append(id_relatorio)
        parametros.append(id_relatorio)

        cursor.execute(
            f"""
                SELECT
                    fo.IdFiltro,
                    f.NomeFiltro,
                    f.TipoCampoValor,
                    {valor_select}
                FROM {FILTRO_X_OPERACAO_TABLE} fo
                INNER JOIN {FILTRO_CATALOGO_TABLE} f
                    ON f.IdFiltro = fo.IdFiltro
                WHERE fo.IdCapRecursoOperacoes = ?
                  {filtro_relatorio_operacao}
                  AND f.IdCapRecursoRelatorio = ?
                  AND fo.IdAtivo = 1
                  AND f.IdAtivo = 1
                ORDER BY fo.OrdemVisual, f.NomeFiltro
            """,
            *parametros,
        )
        rows = cursor.fetchall()

    return [
        {
            "id_filtro": row.IdFiltro,
            "nome_filtro": row.NomeFiltro,
            "tipo_campo_valor": (row.TipoCampoValor or "").strip().upper(),
            "valor": formatar_valor_filtro(row.Valor, row.TipoCampoValor),
        }
        for row in rows
    ]


def montar_relatorios_operacao_execucao(operacao_id):
    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        coluna_valor = obter_coluna_valor_filtro(cursor)
        coluna_relatorio_existe = coluna_existe(
            cursor,
            FILTRO_X_OPERACAO_TABLE,
            "IdCapRecursoRelatorio",
        )
        coluna_relatorio_operacao_existe = coluna_existe(
            cursor,
            FILTRO_X_OPERACAO_TABLE,
            "IdCapRecursoRelatorioOperacao",
        )
        valor_select = (
            f"fo.{coluna_valor} AS Valor"
            if coluna_valor
            else "CAST('' AS varchar(255)) AS Valor"
        )
        relatorio_operacao_select = (
            "fo.IdCapRecursoRelatorioOperacao AS IdCapRecursoRelatorioOperacaoFiltro,"
            if coluna_relatorio_operacao_existe
            else "NULL AS IdCapRecursoRelatorioOperacaoFiltro,"
        )
        filtro_relatorio_operacao = (
            "AND fo.IdCapRecursoRelatorio = ro.IdCapRecursoRelatorio"
            if coluna_relatorio_existe
            else ""
        )

        cursor.execute(
            f"""
                SELECT
                    ro.IdCapRecursoRelatorioOperacao,
                    ro.IdCapRecursoRelatorio,
                    r.NomeRelatorio,
                    r.UrlRelatorio,
                    f.IdFiltro,
                    f.NomeFiltro,
                    f.TipoCampo,
                    f.TipoCampoValor,
                    f.IframeIndex,
                    f.CampoIdentificador,
                    f.Acao,
                    {relatorio_operacao_select}
                    {valor_select}
                FROM {RELATORIO_X_OPERACAO_TABLE} ro
                INNER JOIN dbo.CapRecursoRelatorio r
                    ON r.IdCapRecursoRelatorio = ro.IdCapRecursoRelatorio
                LEFT JOIN {FILTRO_X_OPERACAO_TABLE} fo
                    ON fo.IdCapRecursoOperacoes = ro.IdCapRecursoOperacoes
                   {filtro_relatorio_operacao}
                   AND fo.IdAtivo = 1
                LEFT JOIN {FILTRO_CATALOGO_TABLE} f
                    ON f.IdFiltro = fo.IdFiltro
                   AND f.IdCapRecursoRelatorio = ro.IdCapRecursoRelatorio
                   AND f.IdAtivo = 1
                WHERE ro.IdCapRecursoOperacoes = ?
                  AND ro.IdAtivo = 1
                  AND r.IdAtivo = 1
                ORDER BY r.NomeRelatorio, fo.OrdemVisual, f.IdFiltro
            """,
            operacao_id,
        )
        rows = cursor.fetchall()

    relatorios = {}
    for row in rows:
        relatorio_id = row.IdCapRecursoRelatorio
        relatorio = relatorios.setdefault(
            relatorio_id,
            {
                "id": relatorio_id,
                "id_relatorio_operacao": (
                    row.IdCapRecursoRelatorioOperacaoFiltro
                    if getattr(row, "IdCapRecursoRelatorioOperacaoFiltro", None) is not None
                    else row.IdCapRecursoRelatorioOperacao
                ),
                "nome": row.NomeRelatorio,
                "url": row.UrlRelatorio or "",
                "filtros": [],
            },
        )

        if row.IdFiltro is None:
            continue

        relatorio["filtros"].append(
            {
                "id": row.IdFiltro,
                "nome": (row.NomeFiltro or "").strip(),
                "tipo_campo": (row.TipoCampo or "").strip().upper(),
                "tipo_campo_valor": (row.TipoCampoValor or "").strip().upper(),
                "iframe_index": int(row.IframeIndex or 0),
                "campo_identificador": (row.CampoIdentificador or "").strip(),
                "acao": (row.Acao or "").strip().lower(),
                "valor": formatar_valor_filtro(row.Valor, row.TipoCampoValor),
            }
        )

    relatorios_ordenados = [anexar_botoes_automaticos(relatorio) for relatorio in relatorios.values()]
    return _ordenar_relatorios_operacao(relatorios_ordenados)


def _ordenar_relatorios_operacao(relatorios):
    if not relatorios:
        return relatorios

    relatorios_saldo_devedor = []
    relatorios_outros = []
    for relatorio in relatorios:
        if relatorio.get("id") == 2:
            relatorios_saldo_devedor.append(relatorio)
            continue

        executor = obter_executor_relatorio(
            relatorio.get("nome", ""),
            relatorio.get("id_relatorio_operacao"),
            relatorio.get("id"),
            relatorio.get("url", ""),
        )
        if executor == "extrato_saldo_devedor_presente":
            relatorios_saldo_devedor.append(relatorio)
        else:
            relatorios_outros.append(relatorio)

    return relatorios_outros + relatorios_saldo_devedor


def criar_operacao(nome_operacao):
    id_login_criacao, _ = get_login_ids()

    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        proximo_id = get_next_id(cursor, "dbo.CapRecursoOperacoes", "IdCapRecursoOperacoes")
        cursor.execute(
            """
                INSERT INTO dbo.CapRecursoOperacoes (
                    IdCapRecursoOperacoes,
                    NomeOperacao,
                    IdAtivo,
                    DataCriacao,
                    IdLoginCriacao
                )
                VALUES (?, ?, 1, GETDATE(), ?)
            """,
            proximo_id,
            nome_operacao,
            id_login_criacao,
        )
        connection.commit()

    return proximo_id


def atualizar_operacao(operacao_id, nome_operacao):
    _, id_login_alteracao = get_login_ids()
    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
                UPDATE dbo.CapRecursoOperacoes
                SET
                    NomeOperacao = ?,
                    DataAlteracao = GETDATE(),
                    IdLoginAlteracao = ?
                WHERE IdCapRecursoOperacoes = ?
            """,
            nome_operacao,
            id_login_alteracao,
            operacao_id,
        )
        connection.commit()


def inativar_operacao(operacao_id):
    _, id_login_alteracao = get_login_ids()
    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
                UPDATE dbo.CapRecursoOperacoes
                SET
                    IdAtivo = 0,
                    DataAlteracao = GETDATE(),
                    IdLoginAlteracao = ?
                WHERE IdCapRecursoOperacoes = ?
            """,
            id_login_alteracao,
            operacao_id,
        )
        connection.commit()


def adicionar_relatorio_operacao(operacao_id, id_relatorio):
    id_login_criacao, _ = get_login_ids()
    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"""
                SELECT COUNT(1) AS Total
                FROM {RELATORIO_X_OPERACAO_TABLE}
                WHERE IdCapRecursoOperacoes = ?
                  AND IdCapRecursoRelatorio = ?
                  AND IdAtivo = 1
            """,
            operacao_id,
            id_relatorio,
        )
        if cursor.fetchone().Total:
            return False

        proximo_id = get_next_id(
            cursor,
            RELATORIO_X_OPERACAO_TABLE,
            "IdCapRecursoRelatorioOperacao",
        )
        cursor.execute(
            f"""
                INSERT INTO {RELATORIO_X_OPERACAO_TABLE} (
                    IdCapRecursoRelatorioOperacao,
                    IdCapRecursoRelatorio,
                    IdCapRecursoOperacoes,
                    IdAtivo,
                    DataCriacao,
                    IdLoginCriacao
                )
                VALUES (?, ?, ?, 1, GETDATE(), ?)
            """,
            proximo_id,
            id_relatorio,
            operacao_id,
            id_login_criacao,
        )

        inserir_filtros_relatorio_operacao(
            cursor,
            operacao_id,
            id_relatorio,
            id_login_criacao,
        )
        connection.commit()
    return True


def remover_relatorio_operacao(operacao_id, id_relatorio):
    _, id_login_alteracao = get_login_ids()
    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        coluna_alteracao_existe = coluna_existe(
            cursor,
            RELATORIO_X_OPERACAO_TABLE,
            "IdLoginAlteracao",
        )
        data_alteracao_existe = coluna_existe(
            cursor,
            RELATORIO_X_OPERACAO_TABLE,
            "DataAlteracao",
        )
        set_alteracao = ", IdLoginAlteracao = ?" if coluna_alteracao_existe else ""
        set_data_alteracao = ", DataAlteracao = GETDATE()" if data_alteracao_existe else ""

        parametros = [id_login_alteracao] if coluna_alteracao_existe else []
        parametros.extend([operacao_id, id_relatorio])
        cursor.execute(
            f"""
                UPDATE {RELATORIO_X_OPERACAO_TABLE}
                SET
                    IdAtivo = 0
                    {set_data_alteracao}
                    {set_alteracao}
                WHERE IdCapRecursoOperacoes = ?
                  AND IdCapRecursoRelatorio = ?
                  AND IdAtivo = 1
            """,
            *parametros,
        )
        removidos = cursor.rowcount

        coluna_relatorio_existe = coluna_existe(
            cursor,
            FILTRO_X_OPERACAO_TABLE,
            "IdCapRecursoRelatorio",
        )
        coluna_filtro_alteracao_existe = coluna_existe(
            cursor,
            FILTRO_X_OPERACAO_TABLE,
            "IdLoginAlteracao",
        )
        coluna_filtro_data_alteracao_existe = coluna_existe(
            cursor,
            FILTRO_X_OPERACAO_TABLE,
            "DataAlteracao",
        )
        where_relatorio = "AND IdCapRecursoRelatorio = ?" if coluna_relatorio_existe else ""
        where_filtros_catalogo = (
            f"""
                  AND IdFiltro IN (
                      SELECT IdFiltro
                      FROM {FILTRO_CATALOGO_TABLE}
                      WHERE IdCapRecursoRelatorio = ?
                        AND IdAtivo = 1
                  )
            """
            if not coluna_relatorio_existe
            else ""
        )
        set_filtro_alteracao = ", IdLoginAlteracao = ?" if coluna_filtro_alteracao_existe else ""
        set_filtro_data = ", DataAlteracao = GETDATE()" if coluna_filtro_data_alteracao_existe else ""

        parametros_filtro = []
        if coluna_filtro_alteracao_existe:
            parametros_filtro.append(id_login_alteracao)
        parametros_filtro.append(operacao_id)
        if coluna_relatorio_existe:
            parametros_filtro.append(id_relatorio)
        else:
            parametros_filtro.append(id_relatorio)

        cursor.execute(
            f"""
                UPDATE {FILTRO_X_OPERACAO_TABLE}
                SET
                    IdAtivo = 0
                    {set_filtro_data}
                    {set_filtro_alteracao}
                WHERE IdCapRecursoOperacoes = ?
                  {where_relatorio}
                  {where_filtros_catalogo}
                  AND IdAtivo = 1
            """,
            *parametros_filtro,
        )

        connection.commit()
    return bool(removidos)


def inserir_filtros_relatorio_operacao(cursor, operacao_id, id_relatorio, id_login_criacao):
    cursor.execute(
        f"""
            SELECT
                IdFiltro,
                NomeFiltro
            FROM {FILTRO_CATALOGO_TABLE}
            WHERE IdAtivo = 1
              AND IdCapRecursoRelatorio = ?
            ORDER BY IdFiltro
        """,
        id_relatorio,
    )
    filtros = cursor.fetchall()
    coluna_valor = obter_coluna_valor_filtro(cursor)
    coluna_relatorio_existe = coluna_existe(
        cursor,
        FILTRO_X_OPERACAO_TABLE,
        "IdCapRecursoRelatorio",
    )

    for ordem_visual, filtro in enumerate(filtros, start=1):
        where_relatorio = "AND IdCapRecursoRelatorio = ?" if coluna_relatorio_existe else ""
        parametros_duplicidade = [operacao_id, filtro.IdFiltro]
        if coluna_relatorio_existe:
            parametros_duplicidade.append(id_relatorio)

        cursor.execute(
            f"""
                SELECT COUNT(1) AS Total
                FROM {FILTRO_X_OPERACAO_TABLE}
                WHERE IdCapRecursoOperacoes = ?
                  AND IdFiltro = ?
                  {where_relatorio}
                  AND IdAtivo = 1
            """,
            *parametros_duplicidade,
        )
        if cursor.fetchone().Total:
            continue

        colunas = [
            "IdCapRecursoOperacoes",
            "IdFiltro",
            "Obrigatorio",
            "OrdemVisual",
            "IdAtivo",
            "DataCriacao",
            "IdLoginCriacao",
        ]
        valores_sql = ["?", "?", "0", "?", "1", "GETDATE()", "?"]
        parametros_insert = [operacao_id, filtro.IdFiltro, ordem_visual, id_login_criacao]

        if coluna_relatorio_existe:
            colunas.insert(2, "IdCapRecursoRelatorio")
            valores_sql.insert(2, "?")
            parametros_insert.insert(2, id_relatorio)

        if coluna_valor:
            colunas.insert(-2, coluna_valor)
            valores_sql.insert(-2, "?")
            parametros_insert.insert(-1, "")

        cursor.execute(
            f"""
                INSERT INTO {FILTRO_X_OPERACAO_TABLE} (
                    {", ".join(colunas)}
                )
                VALUES ({", ".join(valores_sql)})
            """,
            *parametros_insert,
        )


def atualizar_valor_filtro_operacao(operacao_id, id_relatorio, id_filtro, valor):
    atualizar_valores_filtros_operacao(operacao_id, id_relatorio, [(id_filtro, valor)])


def atualizar_valores_filtros_operacao(operacao_id, id_relatorio, filtros_valores):
    _, id_login_alteracao = get_login_ids()
    with closing(get_db_connection()) as connection:
        cursor = connection.cursor()
        coluna_valor = obter_coluna_valor_filtro(cursor)
        if not coluna_valor:
            raise ValueError(
                "A tabela de filtros da operacao ainda nao possui coluna de valor."
            )

        coluna_relatorio_existe = coluna_existe(
            cursor,
            FILTRO_X_OPERACAO_TABLE,
            "IdCapRecursoRelatorio",
        )
        coluna_alteracao_existe = coluna_existe(
            cursor,
            FILTRO_X_OPERACAO_TABLE,
            "IdLoginAlteracao",
        )
        data_alteracao_existe = coluna_existe(
            cursor,
            FILTRO_X_OPERACAO_TABLE,
            "DataAlteracao",
        )
        where_relatorio = "AND IdCapRecursoRelatorio = ?" if coluna_relatorio_existe else ""
        set_alteracao = ", IdLoginAlteracao = ?" if coluna_alteracao_existe else ""
        set_data_alteracao = ", DataAlteracao = GETDATE()" if data_alteracao_existe else ""

        for id_filtro, valor in filtros_valores:
            parametros = [valor]
            if coluna_alteracao_existe:
                parametros.append(id_login_alteracao)
            parametros.extend([operacao_id, id_filtro])
            if coluna_relatorio_existe:
                parametros.append(id_relatorio)

            cursor.execute(
                f"""
                    UPDATE {FILTRO_X_OPERACAO_TABLE}
                    SET
                        {coluna_valor} = ?
                        {set_data_alteracao}
                        {set_alteracao}
                    WHERE IdCapRecursoOperacoes = ?
                      AND IdFiltro = ?
                      {where_relatorio}
                      AND IdAtivo = 1
                """,
                *parametros,
            )
        connection.commit()


@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("main"))
    return render_template("index.html")


@app.route("/painel")
@login_required
def main():
    relatorios_disponiveis = []
    operacoes_disponiveis = []

    try:
        relatorios_disponiveis = listar_relatorios_disponiveis()
    except pyodbc.Error:
        flash("Nao foi possivel carregar os relatorios disponiveis.", "error")

    try:
        operacoes_disponiveis = listar_operacoes_execucao()
    except pyodbc.Error:
        flash("Nao foi possivel carregar as operacoes disponiveis.", "error")

    return render_template(
        "main.html",
        relatorios_disponiveis=relatorios_disponiveis,
        operacoes_disponiveis=operacoes_disponiveis,
        credenciais_execucao=obter_credenciais_execucao(),
    )


@app.route("/usuarios")
@login_required
def usuarios():
    if session.get("user_access_id") != ACESSO_ADMIN:
        try:
            usuario = buscar_usuario_por_id(session.get("user_id"))
        except pyodbc.Error:
            flash("Nao foi possivel carregar os dados do seu perfil.", "error")
            return render_template("perfil.html", perfil_usuario=None)

        perfil_usuario = None
        if usuario:
            perfis = {
                ACESSO_ADMIN: "Administrador",
                ACESSO_OPERACAO: "Cadastro de operacao",
                ACESSO_EXECUCAO: "Execucao",
            }
            perfil_usuario = {
                "id": usuario.IdLogin,
                "login": usuario.Login,
                "email": usuario.Email,
                "area": usuario.Area,
                "perfil": perfis.get(usuario.IdAcesso, f"Acesso {usuario.IdAcesso}"),
                "status": "Ativo" if usuario.IdAtivo else "Inativo",
                "data_criacao": usuario.DataCriacao.strftime("%d/%m/%Y %H:%M") if usuario.DataCriacao else "-",
            }

        return render_template("perfil.html", perfil_usuario=perfil_usuario)

    filtro_busca = request.args.get("busca", "").strip()
    filtro_status = request.args.get("status", "ativos").strip().lower()
    modal_tipo = request.args.get("modal", "").strip().lower()
    modal_usuario_id = request.args.get("usuario_id", "").strip()
    modal_usuario_login = request.args.get("usuario_login", "").strip()
    modal_usuario_email = request.args.get("usuario_email", "").strip()
    modal_usuario_area = request.args.get("usuario_area", "").strip()
    modal_usuario_id_acesso = request.args.get("usuario_id_acesso", "").strip()

    try:
        usuarios_lista = listar_usuarios(filtro_busca, filtro_status)
    except pyodbc.Error:
        usuarios_lista = []
        flash("Nao foi possivel consultar os usuarios no banco.", "error")

    return render_template(
        "usuarios.html",
        usuarios_lista=usuarios_lista,
        filtro_busca=filtro_busca,
        filtro_status=filtro_status,
        modal_tipo=modal_tipo,
        modal_usuario_id=modal_usuario_id,
        modal_usuario_login=modal_usuario_login,
        modal_usuario_email=modal_usuario_email,
        modal_usuario_area=modal_usuario_area,
        modal_usuario_id_acesso=modal_usuario_id_acesso,
    )


@app.route("/usuarios/cadastrar", methods=["POST"])
@access_required(ACESSO_ADMIN)
def cadastrar_usuario():
    email = request.form.get("email", "").strip()
    login_usuario = request.form.get("login_usuario", "").strip()
    senha = request.form.get("senha", "")
    confirmar_senha = request.form.get("confirmar_senha", "")
    area = request.form.get("area", "").strip()
    raw_id_acesso = request.form.get("id_acesso", "").strip()

    if not all([email, login_usuario, senha, confirmar_senha, area, raw_id_acesso]):
        flash("Preencha todos os campos obrigatorios do cadastro de usuario.", "error")
        return redirect(url_for("usuarios"))

    if senha != confirmar_senha:
        flash("A confirmacao de senha precisa ser igual a senha informada.", "error")
        return redirect(url_for("usuarios"))

    try:
        id_acesso = int(raw_id_acesso)
    except ValueError:
        flash("Selecione um nivel de acesso valido.", "error")
        return redirect(url_for("usuarios"))

    if id_acesso not in {ACESSO_ADMIN, ACESSO_OPERACAO, ACESSO_EXECUCAO}:
        flash("Selecione um nivel de acesso valido.", "error")
        return redirect(url_for("usuarios"))

    try:
        criado = criar_usuario(login_usuario, senha, email, area, id_acesso)
    except pyodbc.Error:
        flash("Nao foi possivel salvar o usuario na tabela CapRecursoUsuario.", "error")
        return redirect(url_for("usuarios"))

    if not criado:
        flash("Ja existe um usuario com este login ou email.", "error")
        return redirect(url_for("usuarios"))

    flash("Usuario cadastrado com sucesso.", "success")
    return redirect(url_for("usuarios"))


@app.route("/usuarios/minha-senha", methods=["POST"])
@login_required
def atualizar_minha_senha():
    senha_atual = request.form.get("senha_atual", "")
    nova_senha = request.form.get("nova_senha", "")
    confirmar_senha = request.form.get("confirmar_senha", "")

    if not all([senha_atual, nova_senha, confirmar_senha]):
        flash("Preencha senha atual, nova senha e confirmacao.", "error")
        return redirect(url_for("usuarios"))

    if nova_senha != confirmar_senha:
        flash("A confirmacao da nova senha precisa ser igual.", "error")
        return redirect(url_for("usuarios"))

    try:
        usuario = buscar_usuario_por_login(session.get("user_login"))
    except pyodbc.Error:
        flash("Nao foi possivel validar sua senha atual.", "error")
        return redirect(url_for("usuarios"))

    if not usuario or not check_password_hash(usuario.Senha, senha_atual):
        flash("A senha atual informada esta incorreta.", "error")
        return redirect(url_for("usuarios"))

    try:
        atualizar_propria_senha(session.get("user_id"), nova_senha)
    except pyodbc.Error:
        flash("Nao foi possivel atualizar sua senha.", "error")
        return redirect(url_for("usuarios"))

    flash("Sua senha foi atualizada com sucesso.", "success")
    return redirect(url_for("usuarios"))


@app.route("/usuarios/<int:id_login>/editar", methods=["POST"])
@access_required(ACESSO_ADMIN)
def editar_usuario(id_login):
    email = request.form.get("email", "").strip()
    area = request.form.get("area", "").strip()
    raw_id_acesso = request.form.get("id_acesso", "").strip()
    nova_senha = request.form.get("senha", "")
    confirmar_senha = request.form.get("confirmar_senha", "")
    usuario_login = request.form.get("usuario_login", "").strip()

    if not all([email, area, raw_id_acesso]):
        flash("Preencha email, area e nivel de acesso para editar o usuario.", "error")
        return redirect(
            url_for(
                "usuarios",
                modal="editar",
                usuario_id=id_login,
                usuario_login=usuario_login,
                usuario_email=email,
                usuario_area=area,
                usuario_id_acesso=raw_id_acesso,
            )
        )

    if nova_senha or confirmar_senha:
        if nova_senha != confirmar_senha:
            flash("A confirmacao de senha precisa ser igual a senha informada.", "error")
            return redirect(
                url_for(
                    "usuarios",
                    modal="editar",
                    usuario_id=id_login,
                    usuario_login=usuario_login,
                    usuario_email=email,
                    usuario_area=area,
                    usuario_id_acesso=raw_id_acesso,
                )
            )

    try:
        id_acesso = int(raw_id_acesso)
    except ValueError:
        flash("Selecione um nivel de acesso valido.", "error")
        return redirect(url_for("usuarios"))

    if id_acesso not in {ACESSO_ADMIN, ACESSO_OPERACAO, ACESSO_EXECUCAO}:
        flash("Selecione um nivel de acesso valido.", "error")
        return redirect(url_for("usuarios"))

    try:
        atualizado = atualizar_usuario(id_login, email, area, id_acesso, nova_senha)
    except pyodbc.Error:
        flash("Nao foi possivel atualizar o usuario.", "error")
        return redirect(url_for("usuarios"))

    if not atualizado:
        flash("Ja existe outro usuario com este email.", "error")
        return redirect(url_for("usuarios"))

    flash("Usuario atualizado com sucesso.", "success")
    return redirect(url_for("usuarios"))


@app.route("/usuarios/<int:id_login>/inativar", methods=["POST"])
@access_required(ACESSO_ADMIN)
def inativar_usuario_route(id_login):
    if session.get("user_id") == id_login:
        flash("Nao e permitido inativar o usuario que esta logado.", "error")
        return redirect(url_for("usuarios"))

    try:
        inativar_usuario(id_login)
    except pyodbc.Error:
        flash("Nao foi possivel inativar o usuario selecionado.", "error")
        return redirect(url_for("usuarios"))

    flash("Usuario inativado com sucesso.", "success")
    return redirect(url_for("usuarios"))


@app.route("/acompanhamento")
@access_required(ACESSO_ADMIN, ACESSO_OPERACAO)
def acompanhamento():
    filtro_nome = request.args.get("nome_operacao", "").strip()
    modal_tipo = request.args.get("modal", "").strip().lower()
    modal_operacao_id = request.args.get("operacao_id", "").strip()
    modal_operacao_nome = request.args.get("operacao_nome", "").strip()
    operacoes = []

    try:
        operacoes = listar_operacoes(filtro_nome)
    except pyodbc.Error:
        flash("Nao foi possivel consultar as operacoes no banco. Confira o .env e a conectividade.", "error")

    return render_template(
        "acompanhamento.html",
        operacoes=operacoes,
        filtro_nome=filtro_nome,
        modal_tipo=modal_tipo,
        modal_operacao_id=modal_operacao_id,
        modal_operacao_nome=modal_operacao_nome,
    )


@app.route("/acompanhamento/operacoes/<int:operacao_id>/relatorios/dados")
@access_required(ACESSO_ADMIN, ACESSO_OPERACAO)
def relatorios_operacao_dados(operacao_id):
    try:
        if not usuario_pode_acessar_operacao(operacao_id):
            return jsonify({"error": "Voce nao possui permissao para acessar esta operacao."}), 403
    except pyodbc.Error:
        return jsonify({"error": "Nao foi possivel validar o acesso da operacao."}), 500

    try:
        relatorios_operacao = listar_relatorios_operacao(operacao_id)
        for relatorio in relatorios_operacao:
            relatorio["filtros"] = listar_filtros_operacao_relatorio(
                operacao_id,
                relatorio["id_relatorio"],
            )

        payload = {
            "relatorios_disponiveis": listar_relatorios_disponiveis(),
            "relatorios_operacao": relatorios_operacao,
        }
        return jsonify(payload)
    except pyodbc.Error:
        return jsonify({"error": "Nao foi possivel carregar os relatorios da operacao."}), 500


@app.route("/acompanhamento/filtros/dados")
@access_required(ACESSO_ADMIN, ACESSO_OPERACAO)
def filtros_dados():
    try:
        return jsonify({"filtros_disponiveis": listar_filtros_disponiveis()})
    except pyodbc.Error:
        return jsonify({"error": "Nao foi possivel carregar os filtros disponiveis."}), 500


@app.route("/relatorios/<int:id_relatorio>/filtros-dados")
@access_required(ACESSO_ADMIN, ACESSO_OPERACAO, ACESSO_EXECUCAO)
def relatorio_filtros_dados(id_relatorio):
    try:
        relatorio = buscar_relatorio_por_id(id_relatorio)
        if not relatorio:
            return jsonify({"error": "Relatorio nao encontrado."}), 404

        filtros = listar_filtros_relatorio(id_relatorio)
        for filtro in filtros:
            filtro["opcional"] = eh_filtro_opcional_relatorio(relatorio, filtro)

        return jsonify(
            {
                "relatorio": relatorio,
                "filtros": filtros,
            }
        )
    except pyodbc.Error:
        return jsonify({"error": "Nao foi possivel carregar os dados do relatorio."}), 500


@app.route("/api/relatorios/<int:id_relatorio>/configuracao", methods=["GET"])
@access_required(ACESSO_ADMIN, ACESSO_OPERACAO, ACESSO_EXECUCAO)
def relatorio_configuracao_api(id_relatorio):
    try:
        relatorio = buscar_relatorio_com_filtros(id_relatorio)
    except pyodbc.Error:
        app.logger.exception("Erro ao carregar configuracao do relatorio %s.", id_relatorio)
        return jsonify({"error": "Nao foi possivel carregar a configuracao do relatorio."}), 500

    if not relatorio:
        return jsonify({"error": "Relatorio nao encontrado."}), 404

    return jsonify(relatorio)


@app.route("/acompanhamento/operacoes", methods=["POST"])
@access_required(ACESSO_ADMIN, ACESSO_OPERACAO)
def criar_operacao_route():
    nome_operacao = request.form.get("nome_operacao", "").strip()

    if not nome_operacao:
        flash("Informe o nome da operacao antes de salvar.", "error")
        return redirect(url_for("acompanhamento", modal="criar"))

    try:
        novo_id = criar_operacao(nome_operacao)
    except ValueError:
        flash("O valor de login da sessao e invalido para gravacao.", "error")
        return redirect(url_for("acompanhamento", modal="criar"))
    except pyodbc.Error:
        flash("Nao foi possivel salvar a operacao na tabela CapRecursoOperacoes.", "error")
        return redirect(url_for("acompanhamento", modal="criar"))

    try:
        registrar_log_acesso(
            "operacao_criacao",
            f"Operacao criada: {nome_operacao} (ID {novo_id}).",
            payload={
                "operacao_id": novo_id,
                "nome_operacao": nome_operacao,
            },
        )
    except pyodbc.Error:
        app.logger.exception("Nao foi possivel registrar log de criacao da operacao %s.", novo_id)

    flash(f"Operacao criada com sucesso. Codigo gerado: {novo_id}.", "success")
    return redirect(url_for("acompanhamento"))


@app.route("/acompanhamento/operacoes/<int:operacao_id>/editar", methods=["POST"])
@access_required(ACESSO_ADMIN, ACESSO_OPERACAO)
def editar_operacao_route(operacao_id):
    nome_operacao = request.form.get("nome_operacao", "").strip()
    operacao_nome_atual = request.form.get("operacao_nome_atual", "").strip()

    try:
        if not usuario_pode_acessar_operacao(operacao_id):
            flash("Voce nao possui permissao para editar esta operacao.", "error")
            return redirect(url_for("acompanhamento"))
    except pyodbc.Error:
        flash("Nao foi possivel validar o acesso da operacao.", "error")
        return redirect(url_for("acompanhamento"))

    if not nome_operacao:
        flash("Informe o nome da operacao para editar.", "error")
        return redirect(
            url_for(
                "acompanhamento",
                modal="editar",
                operacao_id=operacao_id,
                operacao_nome=operacao_nome_atual,
            )
        )

    try:
        atualizar_operacao(operacao_id, nome_operacao)
    except ValueError:
        flash("O valor de login da sessao e invalido para gravacao.", "error")
        return redirect(
            url_for(
                "acompanhamento",
                modal="editar",
                operacao_id=operacao_id,
                operacao_nome=nome_operacao,
            )
        )
    except pyodbc.Error:
        flash("Nao foi possivel editar a operacao selecionada.", "error")
        return redirect(
            url_for(
                "acompanhamento",
                modal="editar",
                operacao_id=operacao_id,
                operacao_nome=nome_operacao or operacao_nome_atual,
            )
        )

    try:
        registrar_log_acesso(
            "operacao_edicao",
            f"Operacao {operacao_id} atualizada para '{nome_operacao}'.",
            payload={
                "operacao_id": operacao_id,
                "nome_anterior": operacao_nome_atual,
                "nome_novo": nome_operacao,
            },
        )
    except pyodbc.Error:
        app.logger.exception("Nao foi possivel registrar log de edicao da operacao %s.", operacao_id)

    flash("Operacao atualizada com sucesso.", "success")
    return redirect(url_for("acompanhamento"))


@app.route("/acompanhamento/operacoes/<int:operacao_id>/inativar", methods=["POST"])
@access_required(ACESSO_ADMIN, ACESSO_OPERACAO)
def inativar_operacao_route(operacao_id):
    try:
        if not usuario_pode_acessar_operacao(operacao_id):
            flash("Voce nao possui permissao para inativar esta operacao.", "error")
            return redirect(url_for("acompanhamento"))
    except pyodbc.Error:
        flash("Nao foi possivel validar o acesso da operacao.", "error")
        return redirect(url_for("acompanhamento"))

    try:
        inativar_operacao(operacao_id)
    except ValueError:
        flash("O valor de login da sessao e invalido para gravacao.", "error")
        return redirect(url_for("acompanhamento"))
    except pyodbc.Error:
        flash("Nao foi possivel inativar a operacao selecionada.", "error")
        return redirect(url_for("acompanhamento"))

    try:
        registrar_log_acesso(
            "operacao_inativacao",
            f"Operacao {operacao_id} inativada.",
            payload={
                "operacao_id": operacao_id,
            },
        )
    except pyodbc.Error:
        app.logger.exception("Nao foi possivel registrar log de inativacao da operacao %s.", operacao_id)

    flash("Operacao inativada com sucesso.", "success")
    return redirect(url_for("acompanhamento"))


@app.route("/acompanhamento/operacoes/<int:operacao_id>/relatorios", methods=["POST"])
@access_required(ACESSO_ADMIN, ACESSO_OPERACAO)
def adicionar_relatorio_route(operacao_id):
    operacao_nome = request.form.get("operacao_nome", "").strip()
    raw_id_relatorio = request.form.get("id_relatorio", "").strip()

    try:
        if not usuario_pode_acessar_operacao(operacao_id):
            flash("Voce nao possui permissao para alterar esta operacao.", "error")
            return redirect(url_for("acompanhamento"))
    except pyodbc.Error:
        flash("Nao foi possivel validar o acesso da operacao.", "error")
        return redirect(url_for("acompanhamento"))

    if not raw_id_relatorio:
        flash("Selecione um relatorio antes de adicionar.", "error")
        return redirect(
            url_for(
                "acompanhamento",
                modal="relatorios",
                operacao_id=operacao_id,
                operacao_nome=operacao_nome,
            )
        )

    try:
        incluido = adicionar_relatorio_operacao(operacao_id, int(raw_id_relatorio))
    except ValueError:
        flash("O valor informado para o relatorio e invalido.", "error")
        return redirect(
            url_for(
                "acompanhamento",
                modal="relatorios",
                operacao_id=operacao_id,
                operacao_nome=operacao_nome,
            )
        )
    except pyodbc.Error:
        flash("Nao foi possivel gravar o relatorio da operacao.", "error")
        return redirect(
            url_for(
                "acompanhamento",
                modal="relatorios",
                operacao_id=operacao_id,
                operacao_nome=operacao_nome,
            )
        )

    if not incluido:
        flash("Este relatorio ja esta vinculado na operacao.", "error")
        return redirect(
            url_for(
                "acompanhamento",
                modal="relatorios",
                operacao_id=operacao_id,
                operacao_nome=operacao_nome,
            )
        )

    try:
        registrar_log_acesso(
            "operacao_relatorio_vinculo",
            f"Relatorio {raw_id_relatorio} vinculado na operacao {operacao_id}.",
            payload={
                "operacao_id": operacao_id,
                "operacao_nome": operacao_nome,
                "relatorio_id": int(raw_id_relatorio),
            },
        )
    except pyodbc.Error:
        app.logger.exception("Nao foi possivel registrar log de vinculo de relatorio na operacao %s.", operacao_id)

    flash("Relatorio vinculado com sucesso.", "success")
    return redirect(
        url_for(
            "acompanhamento",
            modal="relatorios",
            operacao_id=operacao_id,
            operacao_nome=operacao_nome,
        )
    )


@app.route("/acompanhamento/operacoes/<int:operacao_id>/filtros", methods=["POST"])
@access_required(ACESSO_ADMIN, ACESSO_OPERACAO)
def adicionar_filtro_route(operacao_id):
    operacao_nome = request.form.get("operacao_nome", "").strip()
    relatorio_nome = request.form.get("relatorio_nome", "").strip()
    raw_id_relatorio = request.form.get("id_relatorio", "").strip()
    raw_ids_filtros = request.form.getlist("id_filtro")
    valores = request.form.getlist("valor")

    try:
        if not usuario_pode_acessar_operacao(operacao_id):
            flash("Voce nao possui permissao para alterar esta operacao.", "error")
            return redirect(url_for("acompanhamento"))
    except pyodbc.Error:
        flash("Nao foi possivel validar o acesso da operacao.", "error")
        return redirect(url_for("acompanhamento"))

    if not raw_id_relatorio or not raw_ids_filtros:
        flash("Selecione filtros ja vinculados ao relatorio.", "error")
        return redirect(
            url_for(
                "acompanhamento",
                modal="relatorios",
                operacao_id=operacao_id,
                operacao_nome=operacao_nome,
            )
        )

    try:
        filtros_valores = [
            (int(raw_id_filtro), valores[indice].strip() if indice < len(valores) else "")
            for indice, raw_id_filtro in enumerate(raw_ids_filtros)
        ]
        atualizar_valores_filtros_operacao(operacao_id, int(raw_id_relatorio), filtros_valores)
    except ValueError:
        flash("Os dados do filtro sao invalidos ou a tabela ainda nao possui coluna de valor.", "error")
        return redirect(
            url_for(
                "acompanhamento",
                modal="relatorios",
                operacao_id=operacao_id,
                operacao_nome=operacao_nome,
            )
        )
    except pyodbc.Error:
        flash("Nao foi possivel atualizar o valor do filtro da operacao.", "error")
        return redirect(
            url_for(
                "acompanhamento",
                modal="relatorios",
                operacao_id=operacao_id,
                operacao_nome=operacao_nome,
            )
        )

    try:
        registrar_log_acesso(
            "operacao_filtros_atualizacao",
            f"Filtros atualizados na operacao {operacao_id}.",
            payload={
                "operacao_id": operacao_id,
                "operacao_nome": operacao_nome,
                "relatorio_id": int(raw_id_relatorio),
                "relatorio_nome": relatorio_nome,
                "filtros_atualizados": filtros_valores,
            },
        )
    except pyodbc.Error:
        app.logger.exception("Nao foi possivel registrar log de atualizacao de filtros da operacao %s.", operacao_id)

    flash(
        f"Valores dos filtros atualizados com sucesso. Contexto do relatorio: {relatorio_nome or 'nao informado'}.",
        "success",
    )
    return redirect(
        url_for(
            "acompanhamento",
            modal="relatorios",
            operacao_id=operacao_id,
            operacao_nome=operacao_nome,
        )
    )


@app.route("/logs")
@access_required(ACESSO_ADMIN, ACESSO_OPERACAO)
def logs():
    aba = request.args.get("aba", "adm").strip().lower()
    if aba not in {"adm", "operacao"}:
        aba = "adm"
    if session.get("user_access_id") != ACESSO_ADMIN and aba == "adm":
        aba = "operacao"

    filtros = {
        "usuario": request.args.get("usuario", "").strip(),
        "tipo_evento": request.args.get("tipo_evento", "").strip(),
        "data_inicio": request.args.get("data_inicio", "").strip(),
        "data_fim": request.args.get("data_fim", "").strip(),
        "nome_operacao": request.args.get("nome_operacao", "").strip(),
        "status": request.args.get("status", "").strip(),
        "responsavel": request.args.get("responsavel", "").strip(),
    }

    try:
        registros = listar_logs_acesso(filtros) if aba == "adm" else listar_logs_execucao(filtros)
    except pyodbc.Error:
        registros = []
        flash("Nao foi possivel carregar os logs do banco.", "error")

    return render_template(
        "logs.html",
        aba=aba,
        filtros=filtros,
        registros=registros,
    )


@app.route("/logs/exportar")
@access_required(ACESSO_ADMIN, ACESSO_OPERACAO)
def exportar_logs_json():
    aba = request.args.get("aba", "adm").strip().lower()
    if aba not in {"adm", "operacao"}:
        aba = "adm"
    if session.get("user_access_id") != ACESSO_ADMIN and aba == "adm":
        aba = "operacao"

    filtros = {
        "usuario": request.args.get("usuario", "").strip(),
        "tipo_evento": request.args.get("tipo_evento", "").strip(),
        "data_inicio": request.args.get("data_inicio", "").strip(),
        "data_fim": request.args.get("data_fim", "").strip(),
        "nome_operacao": request.args.get("nome_operacao", "").strip(),
        "status": request.args.get("status", "").strip(),
        "responsavel": request.args.get("responsavel", "").strip(),
    }

    try:
        registros = listar_logs_acesso(filtros) if aba == "adm" else listar_logs_execucao(filtros)
    except pyodbc.Error:
        return jsonify({"error": "Nao foi possivel exportar os logs."}), 500

    return jsonify(
        {
            "aba": aba,
            "filtros": filtros,
            "total": len(registros),
            "registros": registros,
        }
    )


@app.route("/login", methods=["POST"])
def login():
    login_usuario = request.form.get("login", "").strip()
    senha = request.form.get("senha", "")
    bootstrap_admin = get_bootstrap_admin()
    payload_login = {
        "login_informado": login_usuario,
    }

    if not login_usuario or not senha:
        try:
            registrar_log_acesso(
                "login_falha",
                "Tentativa de login sem preencher login ou senha.",
                payload=payload_login,
                usuario={"login": login_usuario},
            )
        except pyodbc.Error:
            app.logger.exception("Nao foi possivel registrar log de falha de login.")
        flash("Informe login e senha para entrar.", "error")
        return redirect(url_for("index"))

    try:
        usuario = buscar_usuario_por_login(login_usuario)
    except pyodbc.Error:
        usuario = None
        if not (
            bootstrap_admin
            and login_usuario == bootstrap_admin["login"]
            and bootstrap_admin["password_hash"]
            and check_password_hash(bootstrap_admin["password_hash"], senha)
        ):
            try:
                registrar_log_acesso(
                    "login_falha",
                    "Erro ao validar login no banco de dados.",
                    payload=payload_login,
                    usuario={"login": login_usuario},
                )
            except pyodbc.Error:
                app.logger.exception("Nao foi possivel registrar log de falha de login.")
            flash("Nao foi possivel validar o login no banco de dados.", "error")
            return redirect(url_for("index"))

    if (
        not usuario
        and bootstrap_admin
        and login_usuario == bootstrap_admin["login"]
        and bootstrap_admin["password_hash"]
        and check_password_hash(bootstrap_admin["password_hash"], senha)
    ):
        session.clear()
        session["user_id"] = int(bootstrap_admin["id"])
        session["user_login"] = bootstrap_admin["login"]
        session["user_email"] = bootstrap_admin["email"]
        session["user_area"] = bootstrap_admin["area"]
        session["user_access_id"] = int(bootstrap_admin["access_id"])
        try:
            registrar_log_acesso(
                "login",
                "Login realizado com admin local de desenvolvimento.",
                payload=payload_login,
            )
        except pyodbc.Error:
            app.logger.exception("Nao foi possivel registrar log de login bootstrap.")
        flash("Login realizado com admin local de desenvolvimento.", "success")
        return redirect(url_for("main"))

    if not usuario or not usuario.IdAtivo:
        try:
            registrar_log_acesso(
                "login_falha",
                "Usuario inexistente ou inativo.",
                payload=payload_login,
                usuario={"login": login_usuario},
            )
        except pyodbc.Error:
            app.logger.exception("Nao foi possivel registrar log de falha de login.")
        flash("Usuario ou senha invalidos.", "error")
        return redirect(url_for("index"))

    if not check_password_hash(usuario.Senha, senha):
        try:
            registrar_log_acesso(
                "login_falha",
                "Senha invalida.",
                payload=payload_login,
                usuario={
                    "id": int(usuario.IdLogin),
                    "login": usuario.Login,
                    "email": usuario.Email,
                    "area": usuario.Area,
                    "access_id": int(usuario.IdAcesso),
                },
            )
        except pyodbc.Error:
            app.logger.exception("Nao foi possivel registrar log de falha de login.")
        flash("Usuario ou senha invalidos.", "error")
        return redirect(url_for("index"))

    session.clear()
    session["user_id"] = int(usuario.IdLogin)
    session["user_login"] = usuario.Login
    session["user_email"] = usuario.Email
    session["user_area"] = usuario.Area
    session["user_access_id"] = int(usuario.IdAcesso)
    try:
        registrar_log_acesso(
            "login",
            "Login realizado com sucesso.",
            payload=payload_login,
        )
    except pyodbc.Error:
        app.logger.exception("Nao foi possivel registrar log de login.")

    flash(f"Login realizado com sucesso. Bem-vindo, {usuario.Login}.", "success")
    return redirect(url_for("main"))


@app.route("/processar", methods=["POST"])
@access_required(ACESSO_ADMIN, ACESSO_OPERACAO, ACESSO_EXECUCAO)
def processar():
    origem = request.get_json(silent=True) if request.is_json else request.form
    origem = origem or request.form

    email = obter_texto(origem, "email")
    senha = str(origem.get("senha", ""))
    sharepoint_link = obter_texto(origem, "sharepoint_link")
    data_periodo = obter_texto(origem, "data_periodo") or obter_texto(origem, "data")
    modo = obter_texto(origem, "modo", "completo")

    resposta_json = request.is_json
    salvar_credenciais_execucao(email, senha, sharepoint_link)

    if not email or not senha or not modo:
        mensagem = "Preencha email, senha e modo de execucao."
        if resposta_json:
            return jsonify({"error": mensagem}), 400
        flash(mensagem, "error")
        return redirect(url_for("main"))

    if modo != "completo":
        raw_id_operacao = obter_texto(origem, "operacao") or obter_texto(origem, "operacao_id")
        nome_operacao_execucao = (
            obter_texto(origem, "nome_operacao")
            or obter_texto(origem, "operacao_nome")
        )
        if not raw_id_operacao:
            mensagem = "Selecione uma operacao para continuar."
            if resposta_json:
                return jsonify({"error": mensagem}), 400
            flash(mensagem, "error")
            return redirect(url_for("main"))

        try:
            id_operacao = int(raw_id_operacao)
        except ValueError:
            mensagem = "A operacao informada e invalida."
            if resposta_json:
                return jsonify({"error": mensagem}), 400
            flash(mensagem, "error")
            return redirect(url_for("main"))

        try:
            if not usuario_pode_acessar_operacao(id_operacao):
                mensagem = "Voce nao possui permissao para executar esta operacao."
                if resposta_json:
                    return jsonify({"error": mensagem}), 403
                flash(mensagem, "error")
                return redirect(url_for("main"))
        except pyodbc.Error:
            mensagem = "Nao foi possivel validar o acesso da operacao."
            if resposta_json:
                return jsonify({"error": mensagem}), 500
            flash(mensagem, "error")
            return redirect(url_for("main"))

        try:
            relatorios_execucao = montar_relatorios_operacao_execucao(id_operacao)
        except pyodbc.Error:
            app.logger.exception("Erro ao carregar configuracao da operacao %s.", id_operacao)
            mensagem = "Nao foi possivel carregar a configuracao da operacao."
            if resposta_json:
                return jsonify({"error": mensagem}), 500
            flash(mensagem, "error")
            return redirect(url_for("main"))

        if not relatorios_execucao:
            mensagem = "A operacao selecionada nao possui relatorios ativos vinculados."
            if resposta_json:
                return jsonify({"error": mensagem}), 404
            flash(mensagem, "error")
            return redirect(url_for("main"))

        for relatorio in relatorios_execucao:
            relatorio["nome_operacao"] = nome_operacao_execucao
            relatorio["sharepoint_link"] = sharepoint_link

        pendencias = []
        for relatorio in relatorios_execucao:
            campos_pendentes = validar_filtros_preenchidos(
                relatorio,
                {f"filtro_{filtro['id']}": filtro.get("valor") for filtro in relatorio.get("filtros", [])},
            )
            if campos_pendentes:
                pendencias.append(
                    f"{relatorio['nome']}: " + ", ".join(campos_pendentes)
                )

        if pendencias:
            mensagem = (
                "Preencha os valores dos filtros da operacao antes de executar: "
                + "; ".join(pendencias)
                + "."
            )
            if resposta_json:
                return jsonify({"error": mensagem}), 400
            flash(mensagem, "error")
            return redirect(url_for("main"))

        app.logger.info(
            "Payload da automacao por operacao | operacao_id=%s | relatorios=%s",
            id_operacao,
            [
                {
                    "id": relatorio.get("id"),
                    "nome": relatorio.get("nome"),
                    "filtros": [
                        {
                            "id": filtro.get("id"),
                            "nome": filtro.get("nome"),
                            "campo_identificador": filtro.get("campo_identificador"),
                            "acao": filtro.get("acao"),
                            "valor": filtro.get("valor"),
                        }
                        for filtro in relatorio.get("filtros", [])
                    ],
                }
                for relatorio in relatorios_execucao
            ],
        )
        log_execucao_id = None
        resumo_relatorios_log = [
            {
                "id": relatorio.get("id"),
                "nome": relatorio.get("nome"),
                "resumo_filtros": resumir_filtros_para_log(relatorio.get("filtros", [])),
            }
            for relatorio in relatorios_execucao
        ]
        payload_log_execucao = {
            "tipo_execucao": "operacao",
            "modo_execucao": modo,
            "operacao_id": id_operacao,
            "operacao_nome": nome_operacao_execucao,
            "email_execucao": email,
            "sharepoint_link": sharepoint_link,
            "data_periodo": data_periodo,
            "relatorios": resumo_relatorios_log,
        }
        try:
            log_execucao_id = criar_log_execucao(
                "operacao",
                modo,
                "aguardando",
                payload_entrada=payload_log_execucao,
                id_operacao=id_operacao,
                nome_operacao=nome_operacao_execucao,
                observacao="Execucao solicitada pelo formulario principal.",
            )
        except pyodbc.Error:
            app.logger.exception("Nao foi possivel criar log de execucao da operacao %s.", id_operacao)

        iniciar_execucao_automacao_operacao(
            email,
            senha,
            relatorios_execucao,
            log_execucao_id=log_execucao_id,
            modo_execucao=modo,
        )

        mensagem = (
            f"Automacao iniciada para a operacao {id_operacao} "
            f"com {len(relatorios_execucao)} relatorio(s)."
        )

        if resposta_json:
            return jsonify(
                {
                    "message": mensagem,
                    "operacao_id": id_operacao,
                    "relatorios": relatorios_execucao,
                }
            ), 202

        flash(mensagem, "success")
        return redirect(url_for("main"))

    raw_id_relatorio = obter_texto(origem, "relatorio") or obter_texto(origem, "relatorio_id")
    if not raw_id_relatorio:
        mensagem = "Selecione um relatorio para continuar."
        if resposta_json:
            return jsonify({"error": mensagem}), 400
        flash(mensagem, "error")
        return redirect(url_for("main"))

    try:
        id_relatorio = int(raw_id_relatorio)
    except ValueError:
        mensagem = "O relatorio informado e invalido."
        if resposta_json:
            return jsonify({"error": mensagem}), 400
        flash(mensagem, "error")
        return redirect(url_for("main"))

    try:
        relatorio = buscar_relatorio_com_filtros(id_relatorio)
    except pyodbc.Error:
        app.logger.exception("Erro ao carregar configuracao do relatorio %s.", id_relatorio)
        mensagem = "Nao foi possivel carregar a configuracao do relatorio."
        if resposta_json:
            return jsonify({"error": mensagem}), 500
        flash(mensagem, "error")
        return redirect(url_for("main"))

    if not relatorio:
        mensagem = "O relatorio selecionado nao foi encontrado."
        if resposta_json:
            return jsonify({"error": mensagem}), 404
        flash(mensagem, "error")
        return redirect(url_for("main"))

    valores_filtros = coletar_valores_filtros(relatorio, origem)
    valores_filtros.setdefault("filtro_data_periodo", data_periodo)
    campos_pendentes = validar_filtros_preenchidos(relatorio, valores_filtros)

    if campos_pendentes:
        mensagem = (
            "Preencha os filtros do relatorio antes de executar: "
            + ", ".join(campos_pendentes)
            + "."
        )
        if resposta_json:
            return jsonify({"error": mensagem}), 400
        flash(mensagem, "error")
        return redirect(url_for("main"))

    relatorio_execucao = montar_payload_execucao(id_relatorio, valores_filtros)
    relatorio_execucao["sharepoint_link"] = sharepoint_link
    app.logger.info(
        "Payload da automacao | relatorio_id=%s | relatorio_nome=%s | filtros=%s",
        relatorio_execucao.get("id"),
        relatorio_execucao.get("nome"),
        [
            {
                "id": filtro.get("id"),
                "nome": filtro.get("nome"),
                "campo_identificador": filtro.get("campo_identificador"),
                "acao": filtro.get("acao"),
                "valor": filtro.get("valor"),
            }
            for filtro in relatorio_execucao.get("filtros", [])
        ],
    )

    try:
        log_execucao_id = None
        resumo_filtros_log = resumir_filtros_para_log(relatorio_execucao.get("filtros", []))
        payload_log_execucao = {
            "tipo_execucao": "relatorio",
            "modo_execucao": modo,
            "relatorio": relatorio_execucao,
            "resumo_filtros": resumo_filtros_log,
            "email_execucao": email,
            "sharepoint_link": sharepoint_link,
            "data_periodo": data_periodo,
        }
        try:
            log_execucao_id = criar_log_execucao(
                "relatorio",
                modo,
                "aguardando",
                payload_entrada=payload_log_execucao,
                id_relatorio=relatorio_execucao.get("id"),
                nome_relatorio=relatorio_execucao.get("nome"),
                observacao="Execucao de relatorio solicitada pelo formulario principal.",
            )
        except pyodbc.Error:
            app.logger.exception(
                "Nao foi possivel criar log de execucao do relatorio %s.",
                relatorio_execucao.get("id"),
            )

        iniciar_execucao_automacao(
            email,
            senha,
            relatorio_execucao,
            log_execucao_id=log_execucao_id,
        )
    except ValueError as exc:
        if 'log_execucao_id' in locals() and log_execucao_id:
            try:
                atualizar_log_execucao(
                    log_execucao_id,
                    "erro",
                    erro={"mensagem": str(exc)},
                    observacao="Execucao nao iniciada por erro de validacao.",
                )
            except pyodbc.Error:
                app.logger.exception("Nao foi possivel atualizar log %s apos erro de validacao.", log_execucao_id)
        if resposta_json:
            return jsonify({"error": str(exc)}), 400
        flash(str(exc), "error")
        return redirect(url_for("main"))

    mensagem = (
        f"Automacao iniciada para o relatorio {relatorio_execucao['nome']} "
        f"com {len(relatorio_execucao['filtros'])} filtro(s)."
    )

    if resposta_json:
        return jsonify(
            {
                "message": mensagem,
                "relatorio": relatorio_execucao,
            }
        ), 202

    flash(mensagem, "success")
    return redirect(url_for("main"))


@app.route("/api/automacoes/executar", methods=["POST"])
@access_required(ACESSO_ADMIN, ACESSO_OPERACAO, ACESSO_EXECUCAO)
def executar_automacao_api():
    return processar()


@app.route("/sair")
def sair():
    try:
        registrar_log_acesso("logout", "Sessao encerrada com sucesso.")
    except pyodbc.Error:
        app.logger.exception("Nao foi possivel registrar log de logout.")
    session.clear()
    flash("Sessao encerrada com sucesso.", "success")
    return redirect(url_for("index"))


if __name__ == "__main__":
    run_application()
