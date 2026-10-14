"""
AppCaptacao - interface Flask para automacao e administracao.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import subprocess
import threading
import time
import traceback
import webbrowser
from contextlib import closing
from datetime import datetime
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pyodbc
from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

WIN32SECURITY_IMPORT_ERROR = None
try:
    import win32security
except ImportError as exc:  # pragma: no cover - dependencia opcional fora do Windows corporativo
    win32security = None
    WIN32SECURITY_IMPORT_ERROR = exc

from app_core.app_config import get_static_path, get_template_path, initialize_environment
from services.automacao_service import (
    acao_exige_valor,
    executar_relatorio,
    executar_relatorios_em_sequencia,
)
from services.relatorio_action_service import eh_filtro_opcional_relatorio
from services.relatorio_service import (
    UNIDADES_SELECAO_CAMPO,
    UNIDADES_SELECAO_VALOR,
    aplicar_filtros_fixos_relatorio,
    buscar_relatorio_com_filtros,
    montar_payload_execucao,
)

initialize_environment()

USUARIO_TABLE = os.getenv("USUARIO_TABLE", "dbo.CapRecursoUsuario")
ACESSO_TABLE = os.getenv("ACESSO_TABLE", "dbo.CapRecursoAcesso")
OPERACAO_TABLE = os.getenv("OPERACAO_TABLE", "dbo.CapRecursoOperacoes")
RELATORIO_TABLE = os.getenv("RELATORIO_TABLE", "dbo.CapRecursoRelatorio")
RELATORIO_X_OPERACAO_TABLE = os.getenv("RELATORIO_X_OPERACAO_TABLE", "dbo.CapRecursoRelatorio_X_Operacao")
FILTRO_CATALOGO_TABLE = os.getenv("FILTRO_CATALOGO_TABLE", "dbo.CapRecursoFiltro")
FILTRO_X_OPERACAO_TABLE = os.getenv("FILTRO_X_OPERACAO_TABLE", "dbo.CapRecursoFiltro_X_Operacao")
LOG_CONFIG_TABLE = os.getenv("LOG_CONFIG_TABLE", "dbo.CapRecursoLogConfiguracao")
LOG_OPERACAO_TABLE = os.getenv("LOG_OPERACAO_TABLE", "dbo.CapRecursoLogOperacao")

app = Flask(
    __name__,
    template_folder=get_template_path(),
    static_folder=get_static_path(),
)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "").strip() or secrets.token_urlsafe(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False

_execution_preferences_cache: dict[str, dict[str, str]] = {}
_execution_results_cache: dict[str, dict] = {}


def _get_execution_preferences_cache_key() -> str | None:
    user_id = session.get("user_id")
    if user_id:
        return f"user:{user_id}"

    user_login = _normalize_text(session.get("user_login"))
    if user_login:
        return f"login:{user_login.lower()}"
    return None


def get_execution_preferences_for_current_session() -> dict[str, str]:
    cache_key = _get_execution_preferences_cache_key()
    if not cache_key:
        return {"email": "", "sharepoint_link": ""}

    stored = _execution_preferences_cache.get(cache_key, {})
    return {
        "email": _normalize_text(stored.get("email")),
        "sharepoint_link": _normalize_text(stored.get("sharepoint_link")),
    }


def set_execution_preferences_for_current_session(email: str, sharepoint_link: str) -> None:
    cache_key = _get_execution_preferences_cache_key()
    if not cache_key:
        return

    _execution_preferences_cache[cache_key] = {
        "email": _normalize_text(email),
        "sharepoint_link": _normalize_text(sharepoint_link),
    }


def clear_execution_preferences_for_current_session() -> None:
    cache_key = _get_execution_preferences_cache_key()
    if not cache_key:
        return
    _execution_preferences_cache.pop(cache_key, None)


def clear_execution_result_for_current_session() -> None:
    cache_key = _get_execution_preferences_cache_key()
    if cache_key:
        _execution_results_cache.pop(cache_key, None)


def get_last_execution_result_for_current_session() -> dict | None:
    cache_key = _get_execution_preferences_cache_key()
    if not cache_key:
        return None
    return _execution_results_cache.get(cache_key)


def set_last_execution_result_for_current_session(result: dict) -> None:
    cache_key = _get_execution_preferences_cache_key()
    if cache_key:
        _execution_results_cache[cache_key] = result


def _wait_for_server(host: str, port: int, timeout_seconds: int = 15) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def _get_browser_host(host: str) -> str:
    normalized_host = (host or "").strip()
    if normalized_host in {"", "0.0.0.0", "::"}:
        return "127.0.0.1"
    return normalized_host


def _build_launch_url(host: str, port: int) -> str:
    browser_host = _get_browser_host(host)
    launch_url = (os.getenv("APP_LAUNCH_URL", "").strip() or "/")
    parsed = urlsplit(launch_url)
    if parsed.scheme and parsed.netloc:
        return launch_url

    path = parsed.path or "/"
    if not path.startswith("/"):
        path = f"/{path}"

    return urlunsplit(("http", f"{browser_host}:{port}", path, parsed.query, parsed.fragment))


def _get_chrome_path() -> str | None:
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


def _open_url_in_browser(target_url: str) -> bool:
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


def _open_browser_when_ready(host: str, port: int) -> None:
    target_url = _build_launch_url(host, port)
    if not _wait_for_server(host, port):
        return
    _open_url_in_browser(target_url)


def start_browser_thread(host: str, port: int) -> threading.Thread:
    browser_thread = threading.Thread(
        target=_open_browser_when_ready,
        args=(host, port),
        daemon=True,
    )
    browser_thread.start()
    return browser_thread


def _db_connection() -> pyodbc.Connection:
    driver = os.getenv("DB_DRIVER", "SQL Server")
    extra_params = os.getenv("DB_EXTRA_PARAMS", "").strip()
    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={os.getenv('DB_HOST', '')}",
        f"DATABASE={os.getenv('DB_DATABASE', os.getenv('DB_SCHEMA', ''))}",
        f"UID={os.getenv('DB_USER', '')}",
        f"PWD={os.getenv('DB_PASSWORD', '')}",
    ]
    if not extra_params and driver.lower() != "sql server":
        extra_params = "TrustServerCertificate=yes"
    if extra_params:
        parts.extend([part.strip() for part in extra_params.split(";") if part.strip()])
    timeout = int(os.getenv("DB_TIMEOUT", "5"))
    return pyodbc.connect(";".join(parts) + ";", timeout=timeout)


def _execute(query: str, params: tuple = (), fetch: bool = False, commit: bool = False) -> list[dict]:
    with closing(_db_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(query, params)
        rows: list[dict] = []
        if fetch:
            columns = [column[0] for column in cursor.description or []]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        if commit:
            connection.commit()
        return rows


def _fetch_one(query: str, params: tuple = ()) -> dict | None:
    rows = _execute(query, params, fetch=True)
    return rows[0] if rows else None


def _fetch_all(query: str, params: tuple = ()) -> list[dict]:
    return _execute(query, params, fetch=True)


def _split_table_name(table_name: str) -> tuple[str, str]:
    parts = [part.strip("[] ") for part in str(table_name or "").split(".") if part.strip()]
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    return "dbo", parts[0]


def _column_exists(connection: pyodbc.Connection, table_name: str, column_name: str) -> bool:
    schema, table = _split_table_name(table_name)
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


def _get_filter_value_column(connection: pyodbc.Connection) -> str | None:
    for column_name in ("Valor", "ValorPadrao", "ValorFiltro"):
        if _column_exists(connection, FILTRO_X_OPERACAO_TABLE, column_name):
            return column_name
    return None


def _format_filter_value(value: object, tipo_campo_valor: str = "") -> str:
    if value is None:
        return ""
    if str(tipo_campo_valor or "").strip().upper() == "CLICK":
        return ""
    if hasattr(value, "strftime") and str(tipo_campo_valor or "").strip().upper() == "DATE":
        return value.strftime("%Y-%m-%d")
    return str(value)


def _get_next_id(connection: pyodbc.Connection, table_name: str, id_column: str) -> int:
    cursor = connection.cursor()
    cursor.execute(
        f"SELECT ISNULL(MAX({id_column}), 0) + 1 AS ProximoId "
        f"FROM {table_name} WITH (UPDLOCK, HOLDLOCK)"
    )
    row = cursor.fetchone()
    return int(row.ProximoId if row and row.ProximoId is not None else 1)


def _safe_db_call(loader, default):
    try:
        return loader()
    except Exception:
        app.logger.exception("Falha ao acessar o banco de dados.")
        return default


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _to_bool(value: object) -> bool:
    return str(value or "").strip() in {"1", "true", "True"}


def _format_datetime(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M")
    try:
        return datetime.fromisoformat(str(value)).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(value)


def _verify_password(raw_password: str, stored_password: str) -> bool:
    if not stored_password:
        return False
    try:
        if stored_password.startswith(("pbkdf2:", "scrypt:")):
            return check_password_hash(stored_password, raw_password)
    except ValueError:
        pass
    return stored_password == raw_password


def _parse_network_login(login_value: str) -> tuple[str | None, str]:
    login_normalizado = _normalize_text(login_value)
    if "\\" in login_normalizado:
        dominio, usuario = login_normalizado.split("\\", 1)
        return _normalize_text(dominio) or None, _normalize_text(usuario)
    if "@" in login_normalizado:
        return None, login_normalizado
    dominio = _normalize_text(os.getenv("NETWORK_AUTH_DOMAIN")) or _normalize_text(os.getenv("USERDOMAIN")) or None
    return dominio, login_normalizado


def _resolve_app_login_candidates(login_value: str) -> list[str]:
    candidatos: list[str] = []
    login_normalizado = _normalize_text(login_value)
    if login_normalizado:
        candidatos.append(login_normalizado)
    if "\\" in login_normalizado:
        candidatos.append(_normalize_text(login_normalizado.split("\\", 1)[1]))
    if "@" in login_normalizado:
        candidatos.append(_normalize_text(login_normalizado.split("@", 1)[0]))
    return list(dict.fromkeys([item for item in candidatos if item]))


def _authenticate_network_user(login_value: str, senha: str) -> dict | None:
    if not login_value or not senha or os.name != "nt" or win32security is None:
        return None

    dominio, usuario = _parse_network_login(login_value)
    try:
        token = win32security.LogonUser(
            usuario,
            dominio,
            senha,
            win32security.LOGON32_LOGON_NETWORK,
            win32security.LOGON32_PROVIDER_DEFAULT,
        )
    except Exception:
        return None

    try:
        return {
            "login_informado": _normalize_text(login_value),
            "login_app": _resolve_app_login_candidates(login_value)[-1] if _resolve_app_login_candidates(login_value) else _normalize_text(login_value),
            "dominio": dominio or "",
            "usuario_rede": _normalize_text(usuario),
        }
    finally:
        try:
            token.Close()
        except Exception:
            pass


def _network_auth_available() -> tuple[bool, str]:
    if os.name != "nt":
        return False, "Autenticacao de rede disponivel apenas no Windows."
    if win32security is None:
        detalhe = f" ({WIN32SECURITY_IMPORT_ERROR})" if WIN32SECURITY_IMPORT_ERROR else ""
        return False, f"Modulo de autenticacao Windows indisponivel{detalhe}"
    return True, ""


def _build_network_user(app_login: str, network_identity: dict, row: dict | None = None) -> dict:
    user = _serialize_user(row) if row else None
    if user:
        return user

    access_id = int(os.getenv("NETWORK_AUTH_DEFAULT_ACCESS_ID", "3") or 3)
    dominio = _normalize_text(network_identity.get("dominio"))
    usuario_rede = _normalize_text(network_identity.get("usuario_rede")) or app_login
    return {
        "id": int(os.getenv("NETWORK_AUTH_SYNTHETIC_USER_ID", "0") or 0),
        "login": app_login,
        "email": f"{usuario_rede}@{dominio.lower()}.local" if dominio else "",
        "area": os.getenv("NETWORK_AUTH_DEFAULT_AREA", "rede"),
        "access_id": access_id,
        "perfil": {1: "Administrador", 2: "Usuario com cadastro de operacao", 3: "Usuario de execucao"}.get(access_id, "Usuario"),
        "ativo": True,
        "status": "Ativo",
        "data_criacao": "-",
        "_network": True,
    }


def _bootstrap_admin_user(login: str, senha: str) -> dict | None:
    enabled = os.getenv("DEV_BOOTSTRAP_ADMIN_ENABLED", "false").strip().lower() == "true"
    if not enabled:
        return None

    expected_login = os.getenv("DEV_BOOTSTRAP_ADMIN_LOGIN", "admin")
    password_hash = os.getenv("DEV_BOOTSTRAP_ADMIN_PASSWORD_HASH", "")
    if login != expected_login:
        return None
    if password_hash and not check_password_hash(password_hash, senha):
        return None

    return {
        "id": int(os.getenv("DEV_BOOTSTRAP_ADMIN_ID", "999999")),
        "login": expected_login,
        "email": os.getenv("DEV_BOOTSTRAP_ADMIN_EMAIL", "admin@local.test"),
        "area": os.getenv("DEV_BOOTSTRAP_ADMIN_AREA", "performance"),
        "access_id": int(os.getenv("DEV_BOOTSTRAP_ADMIN_ACCESS_ID", "1")),
        "perfil": "Administrador",
        "ativo": True,
        "status": "Ativo",
        "data_criacao": "-",
        "_bootstrap": True,
    }


def _log_config(evento: str, detalhe: str, payload: dict | None = None) -> None:
    current_user = g.get("current_user")
    if not current_user:
        return
    try:
        _execute(
            f"""
            INSERT INTO {LOG_CONFIG_TABLE} (Usuario, TipoEvento, DataEvento, Detalhe, PayloadJson)
            VALUES (?, ?, GETDATE(), ?, ?)
            """,
            (
                current_user["login"],
                evento,
                detalhe,
                json.dumps(payload or {}, ensure_ascii=True),
            ),
            commit=True,
        )
    except Exception:
        app.logger.warning("Nao foi possivel registrar log de configuracao.", exc_info=True)


def _log_operacao(status: str, payload_entrada: dict, payload_resultado: dict | None = None, erro: dict | None = None) -> None:
    current_user = g.get("current_user")
    try:
        _execute(
            f"""
            INSERT INTO {LOG_OPERACAO_TABLE}
                (NomeOperacao, TipoExecucao, NomeRelatorio, Status, Responsavel, Atualizacao, Observacao,
                 PayloadEntradaJson, PayloadResultadoJson, ErroJson)
            VALUES (?, ?, ?, ?, ?, GETDATE(), ?, ?, ?, ?)
            """,
            (
                payload_entrada.get("nome_operacao", ""),
                payload_entrada.get("tipo_execucao", ""),
                payload_entrada.get("nome_relatorio", ""),
                status,
                current_user["login"] if current_user else "",
                payload_entrada.get("observacao", ""),
                json.dumps(payload_entrada, ensure_ascii=True),
                json.dumps(payload_resultado or {}, ensure_ascii=True) if payload_resultado is not None else None,
                json.dumps(erro or {}, ensure_ascii=True) if erro is not None else None,
            ),
            commit=True,
        )
    except Exception:
        app.logger.warning("Nao foi possivel registrar log de operacao.", exc_info=True)


def _load_user_by_login(login: str) -> dict | None:
    return _fetch_one(
        f"""
        SELECT TOP 1
            u.IdLogin AS id,
            u.Login AS login,
            u.Senha AS senha,
            u.Email AS email,
            u.Area AS area,
            u.IdAcesso AS access_id,
            u.IdAtivo AS ativo
        FROM {USUARIO_TABLE} u
        WHERE u.Login = ?
        """,
        (login,),
    )


def _load_user_by_id(user_id: int) -> dict | None:
    return _fetch_one(
        f"""
        SELECT TOP 1
            u.IdLogin AS id,
            u.Login AS login,
            u.Email AS email,
            u.Area AS area,
            u.IdAcesso AS access_id,
            u.IdAtivo AS ativo,
            u.DataCriacao AS data_criacao
        FROM {USUARIO_TABLE} u
        WHERE u.IdLogin = ?
        """,
        (user_id,),
    )


def _serialize_user(row: dict | None) -> dict | None:
    if not row:
        return None
    access_id = int(row.get("access_id") or 0)
    return {
        "id": int(row.get("id") or 0),
        "login": _normalize_text(row.get("login")),
        "email": _normalize_text(row.get("email")),
        "area": _normalize_text(row.get("area")),
        "access_id": access_id,
        "perfil": {1: "Administrador", 2: "Usuario com cadastro de operacao", 3: "Usuario de execucao"}.get(access_id, "Usuario"),
        "ativo": _to_bool(row.get("ativo")),
        "status": "Ativo" if _to_bool(row.get("ativo")) else "Inativo",
        "data_criacao": _format_datetime(row.get("data_criacao")),
    }


def _load_operacoes_ativas() -> list[dict]:
    rows = _fetch_all(
        f"""
        SELECT
            IdCapRecursoOperacoes AS id,
            NomeOperacao AS nome,
            IdAtivo AS ativo,
            DataCriacao AS data_criacao
        FROM {OPERACAO_TABLE}
        WHERE IdAtivo = 1
        ORDER BY NomeOperacao
        """
    )
    return [
        {
            "id": int(row["id"]),
            "nome": _normalize_text(row["nome"]),
            "ativo": _to_bool(row["ativo"]),
            "status": "Ativo" if _to_bool(row["ativo"]) else "Inativo",
            "data_criacao": _format_datetime(row.get("data_criacao")),
        }
        for row in rows
    ]


def _load_relatorios_disponiveis() -> list[dict]:
    rows = _fetch_all(
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
            "nome": _normalize_text(row["nome"]),
            "url": _normalize_text(row["url"]),
        }
        for row in rows
    ]


def _load_operation_report_summaries() -> dict[int, list[dict]]:
    rows = _fetch_all(
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
                "nome": _normalize_text(row["relatorio_nome"]),
            }
        )
    return summaries


def _load_usuarios(filtro_busca: str, filtro_status: str) -> list[dict]:
    conditions = []
    params: list[object] = []

    if filtro_busca:
        like = f"%{filtro_busca}%"
        conditions.append("(u.Login LIKE ? OR u.Email LIKE ? OR u.Area LIKE ?)")
        params.extend([like, like, like])

    if filtro_status == "ativos":
        conditions.append("u.IdAtivo = 1")
    elif filtro_status == "inativos":
        conditions.append("u.IdAtivo = 0")

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    rows = _fetch_all(
        f"""
        SELECT
            u.IdLogin AS id,
            u.Login AS login,
            u.Email AS email,
            u.Area AS area,
            u.IdAcesso AS id_acesso,
            u.IdAtivo AS ativo,
            u.DataCriacao AS data_criacao,
            COALESCE(a.NomeAcesso, a.Descricao, a.Perfil, 'Usuario') AS perfil
        FROM {USUARIO_TABLE} u
        LEFT JOIN {ACESSO_TABLE} a
            ON a.IdAcesso = u.IdAcesso
        {where_sql}
        ORDER BY u.Login
        """,
        tuple(params),
    )
    usuarios = []
    for row in rows:
        usuario = _serialize_user(row)
        usuario["id_acesso"] = int(row.get("id_acesso") or 0)
        usuarios.append(usuario)
    return usuarios


def _load_operacoes(filtro_nome: str) -> list[dict]:
    if filtro_nome:
        rows = _fetch_all(
            f"""
            SELECT
                IdCapRecursoOperacoes AS id,
                NomeOperacao AS nome,
                IdAtivo AS ativo,
                DataCriacao AS data_criacao
            FROM {OPERACAO_TABLE}
            WHERE IdAtivo = 1 AND NomeOperacao LIKE ?
            ORDER BY NomeOperacao
            """,
            (f"%{filtro_nome}%",),
        )
    else:
        rows = _fetch_all(
            f"""
            SELECT
                IdCapRecursoOperacoes AS id,
                NomeOperacao AS nome,
                IdAtivo AS ativo,
                DataCriacao AS data_criacao
            FROM {OPERACAO_TABLE}
            WHERE IdAtivo = 1
            ORDER BY NomeOperacao
            """
        )
    return [
        {
            "id": int(row["id"]),
            "nome": _normalize_text(row["nome"]),
            "ativo": _to_bool(row["ativo"]),
            "status": "Ativo" if _to_bool(row["ativo"]) else "Inativo",
            "data_criacao": _format_datetime(row.get("data_criacao")),
        }
        for row in rows
    ]


def _load_relatorios_operacao(operacao_id: int) -> list[dict]:
    with closing(_db_connection()) as connection:
        coluna_valor = _get_filter_value_column(connection)
        coluna_relatorio_existe = _column_exists(connection, FILTRO_X_OPERACAO_TABLE, "IdCapRecursoRelatorio")
        valor_select = f"fo.{coluna_valor} AS valor" if coluna_valor else "CAST('' AS varchar(255)) AS valor"
        filtro_relatorio_sql = "AND fo.IdCapRecursoRelatorio = ?" if coluna_relatorio_existe else ""

        rows = _execute(
            f"""
            SELECT
                rxo.IdCapRecursoRelatorioOperacao AS id_relatorio_operacao,
                rxo.IdCapRecursoRelatorio AS id_relatorio,
                r.NomeRelatorio AS nome_relatorio
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
            relatorio_nome = _normalize_text(row["nome_relatorio"])
            params = [operacao_id]
            if coluna_relatorio_existe:
                params.append(relatorio_id)
            params.append(relatorio_id)
            filtros = _execute(
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
                    "filtros": [
                        {
                            "id_filtro": int(filtro["id_filtro"]),
                            "nome_filtro": _normalize_text(filtro["nome_filtro"]),
                            "campo_identificador": _normalize_text(filtro["campo_identificador"]),
                            "valor": (
                                UNIDADES_SELECAO_VALOR
                                if relatorio_nome.strip().lower() == "unidades"
                                and _normalize_text(filtro["campo_identificador"]).lower() == UNIDADES_SELECAO_CAMPO
                                else _format_filter_value(filtro["valor"], filtro["tipo_campo_valor"])
                            ),
                            "automatico": (
                                relatorio_nome.strip().lower() == "unidades"
                                and _normalize_text(filtro["campo_identificador"]).lower() == UNIDADES_SELECAO_CAMPO
                            ),
                            "valor_fixo": (
                                UNIDADES_SELECAO_VALOR
                                if relatorio_nome.strip().lower() == "unidades"
                                and _normalize_text(filtro["campo_identificador"]).lower() == UNIDADES_SELECAO_CAMPO
                                else ""
                            ),
                            "tipo_campo_valor": (
                                "CLICK"
                                if relatorio_nome.strip().lower() == "unidades"
                                and _normalize_text(filtro["campo_identificador"]).lower() == UNIDADES_SELECAO_CAMPO
                                else _normalize_text(filtro["tipo_campo_valor"])
                            ),
                        }
                        for filtro in filtros
                    ],
                }
            )
        return relatorios


def _load_relatorio_operacao_payload(operacao_id: int) -> list[dict]:
    rows = _fetch_all(
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
    with closing(_db_connection()) as connection:
        coluna_valor = _get_filter_value_column(connection)
        coluna_relatorio_existe = _column_exists(connection, FILTRO_X_OPERACAO_TABLE, "IdCapRecursoRelatorio")
        valor_select = f"{coluna_valor} AS valor" if coluna_valor else "CAST('' AS varchar(255)) AS valor"
        for row in rows:
            relatorio = buscar_relatorio_com_filtros(int(row["id_relatorio"])) or {
            "id": int(row["id_relatorio"]),
            "nome": _normalize_text(row["nome_relatorio"]),
            "url": _normalize_text(row["url_relatorio"]),
            "filtros": [],
        }

            where_relatorio = "AND IdCapRecursoRelatorio = ?" if coluna_relatorio_existe else ""
            params = [operacao_id]
            if coluna_relatorio_existe:
                params.append(int(row["id_relatorio"]))
            filtro_rows = _execute(
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
                int(filtro_row["id_filtro"]): _normalize_text(filtro_row["valor"])
                for filtro_row in filtro_rows
            }

            filtros_execucao = []
            for filtro in relatorio.get("filtros", []):
                clone = dict(filtro)
                clone["valor"] = valores.get(int(clone.get("id") or 0), "")
                filtros_execucao.append(clone)

            relatorio["id_relatorio"] = int(row["id_relatorio"])
            relatorio["id_relatorio_operacao"] = int(row["id_relatorio_operacao"])
            relatorio["filtros"] = filtros_execucao
            relatorios_execucao.append(relatorio)
    return relatorios_execucao


def _operation_name_exists(connection: pyodbc.Connection, nome_operacao: str, exclude_id: int | None = None) -> bool:
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


def _insert_operation_report_link(
    connection: pyodbc.Connection,
    operacao_id: int,
    relatorio_id: int,
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
    if cursor.fetchone().Total:
        raise ValueError("Este relatorio ja esta vinculado a operacao.")

    relatorio = buscar_relatorio_com_filtros(relatorio_id)
    if not relatorio:
        raise ValueError(f"Relatorio {relatorio_id} nao encontrado ou inativo.")

    proximo_id = _get_next_id(connection, RELATORIO_X_OPERACAO_TABLE, "IdCapRecursoRelatorioOperacao")
    possui_login_criacao = _column_exists(connection, RELATORIO_X_OPERACAO_TABLE, "IdLoginCriacao")
    colunas = [
        "IdCapRecursoRelatorioOperacao",
        "IdCapRecursoRelatorio",
        "IdCapRecursoOperacoes",
        "IdAtivo",
        "DataCriacao",
    ]
    valores_sql = ["?", "?", "?", "1", "GETDATE()"]
    params: list[object] = [proximo_id, relatorio_id, operacao_id]
    if possui_login_criacao and g.get("current_user"):
        colunas.append("IdLoginCriacao")
        valores_sql.append("?")
        params.append(g.current_user["id"])
    cursor.execute(
        f"INSERT INTO {RELATORIO_X_OPERACAO_TABLE} ({', '.join(colunas)}) "
        f"VALUES ({', '.join(valores_sql)})",
        tuple(params),
    )

    coluna_valor = _get_filter_value_column(connection)
    coluna_relatorio_existe = _column_exists(connection, FILTRO_X_OPERACAO_TABLE, "IdCapRecursoRelatorio")
    coluna_vinculo_existe = _column_exists(
        connection, FILTRO_X_OPERACAO_TABLE, "IdCapRecursoRelatorioOperacao"
    )
    possui_login_criacao_filtro = _column_exists(connection, FILTRO_X_OPERACAO_TABLE, "IdLoginCriacao")

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
        if possui_login_criacao_filtro and g.get("current_user"):
            colunas_filtro.append("IdLoginCriacao")
            valores_filtro_sql.append("?")
            params_filtro.append(g.current_user["id"])
        cursor.execute(
            f"INSERT INTO {FILTRO_X_OPERACAO_TABLE} ({', '.join(colunas_filtro)}) "
            f"VALUES ({', '.join(valores_filtro_sql)})",
            tuple(params_filtro),
        )
    return proximo_id


def _inativar_relatorio_operacao(connection: pyodbc.Connection, operacao_id: int, relatorio_id: int) -> bool:
    cursor = connection.cursor()

    set_relatorio = []
    params_relatorio: list[object] = []
    if _column_exists(connection, RELATORIO_X_OPERACAO_TABLE, "DataAlteracao"):
        set_relatorio.append("DataAlteracao = GETDATE()")
    if _column_exists(connection, RELATORIO_X_OPERACAO_TABLE, "IdLoginAlteracao") and g.get("current_user"):
        set_relatorio.append("IdLoginAlteracao = ?")
        params_relatorio.append(g.current_user["id"])
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
    if _column_exists(connection, FILTRO_X_OPERACAO_TABLE, "DataAlteracao"):
        set_filtros.append("DataAlteracao = GETDATE()")
    if _column_exists(connection, FILTRO_X_OPERACAO_TABLE, "IdLoginAlteracao") and g.get("current_user"):
        set_filtros.append("IdLoginAlteracao = ?")
        params_filtros.append(g.current_user["id"])
    params_filtros.append(operacao_id)

    if _column_exists(connection, FILTRO_X_OPERACAO_TABLE, "IdCapRecursoRelatorioOperacao"):
        where_filtros = f"""
          AND IdCapRecursoRelatorioOperacao IN (
              SELECT IdCapRecursoRelatorioOperacao
              FROM {RELATORIO_X_OPERACAO_TABLE}
              WHERE IdCapRecursoOperacoes = ?
                AND IdCapRecursoRelatorio = ?
          )
        """
        params_filtros.extend([operacao_id, relatorio_id])
    elif _column_exists(connection, FILTRO_X_OPERACAO_TABLE, "IdCapRecursoRelatorio"):
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


def _required_filter_messages(relatorio: dict) -> list[str]:
    missing = []
    for filtro in relatorio.get("filtros", []):
        valor = _normalize_text(filtro.get("valor"))
        if eh_filtro_opcional_relatorio(relatorio, filtro):
            continue
        if acao_exige_valor(filtro.get("acao")) and not valor:
            missing.append(_normalize_text(filtro.get("nome")) or f"Filtro {filtro.get('id')}")
    return missing


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not g.get("current_user"):
            return redirect(url_for("index"))
        return view(*args, **kwargs)

    return wrapper


def access_required(*allowed_access_ids: int):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            current_user = g.get("current_user")
            if not current_user:
                return redirect(url_for("index"))
            if current_user["access_id"] not in allowed_access_ids:
                flash("Voce nao possui permissao para acessar esta pagina.", "error")
                return redirect(url_for("main"))
            return view(*args, **kwargs)

        return wrapper

    return decorator


@app.before_request
def load_current_user() -> None:
    g.current_user = None
    user_id = session.get("user_id")
    if user_id:
        try:
            g.current_user = _safe_db_call(lambda: _serialize_user(_load_user_by_id(int(user_id))), None)
        except Exception:
            g.current_user = None
    if not g.current_user and session.get("user_login"):
        access_id = int(session.get("user_access_id") or 0)
        g.current_user = {
            "id": int(session.get("user_id") or 0),
            "login": _normalize_text(session.get("user_login")),
            "email": _normalize_text(session.get("user_email")),
            "area": _normalize_text(session.get("user_area")),
            "access_id": access_id,
            "perfil": {1: "Administrador", 2: "Usuario com cadastro de operacao", 3: "Usuario de execucao"}.get(access_id, "Usuario"),
            "ativo": True,
            "status": "Ativo",
            "data_criacao": _normalize_text(session.get("user_data_criacao")) or "-",
        }
    if not g.current_user and session.get("user_login") == os.getenv("DEV_BOOTSTRAP_ADMIN_LOGIN", "admin"):
        g.current_user = _bootstrap_admin_user(session.get("user_login", ""), "")


@app.context_processor
def inject_globals() -> dict:
    return {"current_user": g.get("current_user")}


@app.route("/")
def index():
    if g.get("current_user"):
        return redirect(url_for("main"))
    return render_template("index.html")


@app.post("/login")
def login():
    login_value = _normalize_text(request.form.get("login"))
    senha = str(request.form.get("senha") or "")
    payload_login = {"login_informado": login_value}

    if not login_value or not senha:
        try:
            _log_config("login_falha", "Tentativa de login sem preencher login ou senha.", payload_login)
        except Exception:
            pass
        flash("Informe login e senha para entrar.", "error")
        return redirect(url_for("index"))

    raw_user = None
    login_db_error = None
    try:
        raw_user = _load_user_by_login(login_value)
    except Exception as exc:
        login_db_error = exc

    bootstrap_user = _bootstrap_admin_user(login_value, senha)
    if not raw_user and bootstrap_user:
        session.clear()
        session["user_id"] = bootstrap_user["id"]
        session["user_login"] = bootstrap_user["login"]
        session["user_email"] = bootstrap_user.get("email", "")
        session["user_area"] = bootstrap_user.get("area", "")
        session["user_access_id"] = bootstrap_user.get("access_id", 0)
        session["user_data_criacao"] = bootstrap_user.get("data_criacao", "-")
        try:
            _log_config("login", "Login realizado com admin local de desenvolvimento.", payload_login)
        except Exception:
            pass
        return redirect(url_for("main"))

    if login_db_error:
        app.logger.exception("Falha ao validar login no banco de dados.", exc_info=login_db_error)
        try:
            _log_config("login_falha", "Erro ao validar login no banco de dados.", payload_login)
        except Exception:
            pass
        flash("Nao foi possivel validar o login no banco de dados.", "error")
        return redirect(url_for("index"))

    user = _serialize_user(raw_user)
    if not raw_user or not user or not user["ativo"]:
        try:
            _log_config("login_falha", "Usuario inexistente ou inativo.", payload_login)
        except Exception:
            pass
        flash("Usuario ou senha invalidos.", "error")
        return redirect(url_for("index"))

    if not _verify_password(senha, _normalize_text(raw_user.get("senha"))):
        try:
            _log_config("login_falha", "Senha invalida.", payload_login)
        except Exception:
            pass
        flash("Usuario ou senha invalidos.", "error")
        return redirect(url_for("index"))

    session.clear()
    session["user_id"] = user["id"]
    session["user_login"] = user["login"]
    session["user_email"] = user.get("email", "")
    session["user_area"] = user.get("area", "")
    session["user_access_id"] = user.get("access_id", 0)
    session["user_data_criacao"] = user.get("data_criacao", "-")
    try:
        _log_config("login", "Login realizado com sucesso.", payload_login)
    except Exception:
        pass
    flash(f"Login realizado com sucesso. Bem-vindo, {user['login']}.", "success")
    return redirect(url_for("main"))


@app.get("/main")
@login_required
def main():
    operacoes = _safe_db_call(_load_operacoes_ativas, [])
    relatorios = _safe_db_call(_load_relatorios_disponiveis, [])
    credenciais_execucao = get_execution_preferences_for_current_session()
    operacao_relatorios = _safe_db_call(_load_operation_report_summaries, {})
    return render_template(
        "main.html",
        operacoes_disponiveis=operacoes,
        relatorios_disponiveis=relatorios,
        credenciais_execucao=credenciais_execucao,
        resultado_execucao=get_last_execution_result_for_current_session(),
        operacao_relatorios=operacao_relatorios,
    )


@app.post("/processar")
@login_required
def processar():
    email = _normalize_text(request.form.get("email"))
    senha = str(request.form.get("senha") or "")
    sharepoint_link = _normalize_text(request.form.get("sharepoint_link"))
    modo = _normalize_text(request.form.get("modo"))

    if not email or not senha:
        flash("Informe email e senha para a execucao.", "error")
        return redirect(url_for("main"))

    set_execution_preferences_for_current_session(email, sharepoint_link)
    clear_execution_result_for_current_session()

    try:
        if modo == "completo":
            relatorio_id = int(request.form.get("relatorio") or 0)
            payload = montar_payload_execucao(relatorio_id, request.form)
            if not payload:
                flash("Relatorio nao encontrado.", "error")
                return redirect(url_for("main"))

            missing = _required_filter_messages(payload)
            if missing:
                flash(f"Preencha os filtros obrigatorios: {', '.join(missing)}.", "error")
                return redirect(url_for("main"))

            payload["sharepoint_link"] = sharepoint_link
            resultado = executar_relatorio(email, senha, payload)
            set_last_execution_result_for_current_session(resultado)
            _log_operacao(
                "sucesso" if resultado.get("quantidade_baixados") else "erro",
                {
                    "tipo_execucao": "relatorio",
                    "nome_relatorio": payload.get("nome", ""),
                    "observacao": "Execucao individual concluida.",
                },
                resultado,
                None if resultado.get("quantidade_baixados") else {"mensagem": resultado.get("mensagem", "")},
            )
            flash(resultado.get("resumo", "Execucao concluida."), "success" if resultado.get("quantidade_baixados") else "error")
            return redirect(url_for("main"))

        if modo == "parceiros":
            operacao_id = int(request.form.get("operacao") or 0)
            operacao = _fetch_one(
                f"SELECT NomeOperacao AS nome FROM {OPERACAO_TABLE} "
                "WHERE IdCapRecursoOperacoes = ? AND IdAtivo = 1",
                (operacao_id,),
            )
            if not operacao:
                flash("Selecione uma operacao ativa.", "error")
                return redirect(url_for("main"))
            relatorios = _safe_db_call(lambda: _load_relatorio_operacao_payload(operacao_id), [])
            if not relatorios:
                flash("Nenhum relatorio ativo vinculado a esta operacao.", "error")
                return redirect(url_for("main"))

            for relatorio in relatorios:
                relatorio["sharepoint_link"] = sharepoint_link
                relatorio["operacao_nome"] = operacao.get("nome", "") if operacao else ""
                missing = _required_filter_messages(relatorio)
                if missing:
                    flash(
                        f"Relatorio '{relatorio.get('nome', '')}' possui filtros obrigatorios sem valor: {', '.join(missing)}.",
                        "error",
                    )
                    return redirect(url_for("main"))

            resultado = executar_relatorios_em_sequencia(email, senha, relatorios)
            resultado["operacao_nome"] = operacao.get("nome", "") if operacao else ""
            set_last_execution_result_for_current_session(resultado)
            _log_operacao(
                "sucesso" if not resultado.get("falhas") else "erro",
                {
                    "tipo_execucao": "operacao",
                    "nome_operacao": operacao.get("nome", ""),
                    "observacao": "Execucao em sequencia concluida.",
                },
                resultado,
                {"falhas": resultado.get("falhas", [])} if resultado.get("falhas") else None,
            )
            flash(resultado.get("resumo", "Execucao da operacao concluida."), "success" if not resultado.get("falhas") else "error")
            return redirect(url_for("main"))

        flash("Selecione um modo de execucao valido.", "error")
    except Exception as exc:
        _log_operacao(
            "erro",
            {
                "tipo_execucao": modo or "desconhecido",
                "nome_operacao": request.form.get("operacao", ""),
                "nome_relatorio": request.form.get("relatorio", ""),
                "observacao": "Falha durante a execucao.",
            },
            None,
            {
                "mensagem": str(exc),
                "traceback": traceback.format_exc(),
            },
        )
        flash(f"Falha ao executar a automacao: {exc}", "error")

    return redirect(url_for("main"))


@app.get("/perfil")
@login_required
def perfil():
    return render_template("perfil.html", perfil_usuario=g.current_user)


@app.post("/perfil/senha")
@login_required
def atualizar_minha_senha():
    if g.current_user.get("_bootstrap"):
        flash("Nao e possivel alterar a senha do usuario bootstrap por aqui.", "error")
        return redirect(url_for("perfil"))

    senha_atual = str(request.form.get("senha_atual") or "")
    nova_senha = str(request.form.get("nova_senha") or "")
    confirmar = str(request.form.get("confirmar_senha") or "")

    raw_user = _safe_db_call(lambda: _load_user_by_login(g.current_user["login"]), None)
    if not raw_user or not _verify_password(senha_atual, _normalize_text(raw_user.get("senha"))):
        flash("Senha atual invalida.", "error")
        return redirect(url_for("perfil"))
    if not nova_senha or nova_senha != confirmar:
        flash("A nova senha e a confirmacao precisam coincidir.", "error")
        return redirect(url_for("perfil"))

    _safe_db_call(
        lambda: _execute(
            f"UPDATE {USUARIO_TABLE} SET Senha = ? WHERE IdLogin = ?",
            (generate_password_hash(nova_senha), g.current_user["id"]),
            commit=True,
        ),
        None,
    )
    _log_config("senha_atualizacao", "Usuario atualizou a propria senha.")
    flash("Senha atualizada com sucesso.", "success")
    return redirect(url_for("perfil"))


@app.get("/usuarios")
@login_required
def usuarios():
    if g.current_user["access_id"] != 1:
        return redirect(url_for("perfil"))

    filtro_busca = _normalize_text(request.args.get("busca"))
    filtro_status = _normalize_text(request.args.get("status")) or "ativos"
    usuarios_lista = _safe_db_call(lambda: _load_usuarios(filtro_busca, filtro_status), [])

    return render_template(
        "usuarios.html",
        usuarios_lista=usuarios_lista,
        filtro_busca=filtro_busca,
        filtro_status=filtro_status,
        modal_tipo=request.args.get("modal_tipo"),
        modal_usuario_id=request.args.get("modal_usuario_id"),
        modal_usuario_login=request.args.get("modal_usuario_login"),
        modal_usuario_email=request.args.get("modal_usuario_email"),
        modal_usuario_area=request.args.get("modal_usuario_area"),
        modal_usuario_id_acesso=request.args.get("modal_usuario_id_acesso"),
    )


@app.post("/usuarios")
@login_required
@access_required(1)
def cadastrar_usuario():
    login_usuario = _normalize_text(request.form.get("login_usuario"))
    email = _normalize_text(request.form.get("email"))
    area = _normalize_text(request.form.get("area"))
    id_acesso = int(request.form.get("id_acesso") or 0)
    senha = str(request.form.get("senha") or "")
    confirmar = str(request.form.get("confirmar_senha") or "")

    if not login_usuario or not email or not area or not id_acesso:
        flash("Preencha todos os campos obrigatorios.", "error")
        return redirect(url_for("usuarios", modal_tipo="criar"))
    if senha != confirmar:
        flash("Senha e confirmacao nao conferem.", "error")
        return redirect(url_for("usuarios", modal_tipo="criar"))

    try:
        _execute(
            f"""
            INSERT INTO {USUARIO_TABLE} (Login, Email, Area, Senha, IdAcesso, IdAtivo, DataCriacao)
            VALUES (?, ?, ?, ?, ?, 1, GETDATE())
            """,
            (login_usuario, email, area, generate_password_hash(senha), id_acesso),
            commit=True,
        )
        _log_config("usuario_criacao", f"Usuario {login_usuario} criado.", {"email": email, "area": area})
        flash("Usuario cadastrado com sucesso.", "success")
        return redirect(url_for("usuarios"))
    except Exception as exc:
        flash(f"Nao foi possivel cadastrar o usuario: {exc}", "error")
        return redirect(url_for("usuarios", modal_tipo="criar"))


@app.post("/usuarios/<int:id_login>/editar")
@login_required
@access_required(1)
def editar_usuario(id_login: int):
    email = _normalize_text(request.form.get("email"))
    area = _normalize_text(request.form.get("area"))
    id_acesso = int(request.form.get("id_acesso") or 0)
    senha = str(request.form.get("senha") or "")
    confirmar = str(request.form.get("confirmar_senha") or "")

    if senha and senha != confirmar:
        flash("A nova senha e a confirmacao nao conferem.", "error")
        return redirect(
            url_for(
                "usuarios",
                modal_tipo="editar",
                modal_usuario_id=id_login,
                modal_usuario_login=request.form.get("usuario_login", ""),
                modal_usuario_email=email,
                modal_usuario_area=area,
                modal_usuario_id_acesso=id_acesso,
            )
        )

    try:
        if senha:
            _execute(
                f"UPDATE {USUARIO_TABLE} SET Email = ?, Area = ?, IdAcesso = ?, Senha = ? WHERE IdLogin = ?",
                (email, area, id_acesso, generate_password_hash(senha), id_login),
                commit=True,
            )
        else:
            _execute(
                f"UPDATE {USUARIO_TABLE} SET Email = ?, Area = ?, IdAcesso = ? WHERE IdLogin = ?",
                (email, area, id_acesso, id_login),
                commit=True,
            )
        _log_config("usuario_edicao", f"Usuario {id_login} atualizado.")
        flash("Usuario atualizado com sucesso.", "success")
        return redirect(url_for("usuarios"))
    except Exception as exc:
        flash(f"Nao foi possivel atualizar o usuario: {exc}", "error")
        return redirect(url_for("usuarios"))


@app.post("/usuarios/<int:id_login>/inativar")
@login_required
@access_required(1)
def inativar_usuario_route(id_login: int):
    if g.current_user["id"] == id_login:
        flash("Voce nao pode inativar o proprio usuario.", "error")
        return redirect(url_for("usuarios"))
    try:
        _execute(
            f"UPDATE {USUARIO_TABLE} SET IdAtivo = 0 WHERE IdLogin = ?",
            (id_login,),
            commit=True,
        )
        _log_config("usuario_inativacao", f"Usuario {id_login} inativado.")
        flash("Usuario inativado com sucesso.", "success")
    except Exception as exc:
        flash(f"Nao foi possivel inativar o usuario: {exc}", "error")
    return redirect(url_for("usuarios"))


@app.get("/acompanhamento")
@login_required
@access_required(1, 2)
def acompanhamento():
    filtro_nome = _normalize_text(request.args.get("nome_operacao"))
    operacoes = _safe_db_call(lambda: _load_operacoes(filtro_nome), [])
    relatorios_disponiveis = _safe_db_call(_load_relatorios_disponiveis, [])
    return render_template(
        "acompanhamento.html",
        operacoes=operacoes,
        relatorios_disponiveis=relatorios_disponiveis,
        filtro_nome=filtro_nome,
        modal_tipo=request.args.get("modal_tipo"),
        modal_operacao_id=request.args.get("modal_operacao_id"),
        modal_operacao_nome=request.args.get("modal_operacao_nome"),
    )


@app.post("/acompanhamento/operacoes")
@login_required
@access_required(1, 2)
def criar_operacao_route():
    nome_operacao = _normalize_text(request.form.get("nome_operacao"))
    relatorios_ids_raw = request.form.getlist("id_relatorio")
    relatorios_ids: list[int] = []
    for value in relatorios_ids_raw:
        try:
            relatorio_id = int(value)
        except (TypeError, ValueError):
            continue
        if relatorio_id > 0 and relatorio_id not in relatorios_ids:
            relatorios_ids.append(relatorio_id)
    if not nome_operacao:
        flash("Informe o nome da operacao.", "error")
        return redirect(url_for("acompanhamento", modal_tipo="criar"))
    if not relatorios_ids:
        flash("Selecione pelo menos um relatorio para criar a operacao.", "error")
        return redirect(url_for("acompanhamento", modal_tipo="criar"))
    try:
        with closing(_db_connection()) as connection:
            if _operation_name_exists(connection, nome_operacao):
                raise ValueError("Ja existe uma operacao ativa com este nome.")
            operacao_id = _get_next_id(connection, OPERACAO_TABLE, "IdCapRecursoOperacoes")
            colunas = ["IdCapRecursoOperacoes", "NomeOperacao", "IdAtivo", "DataCriacao"]
            valores = ["?", "?", "1", "GETDATE()"]
            params: list[object] = [operacao_id, nome_operacao]
            if _column_exists(connection, OPERACAO_TABLE, "IdLoginCriacao") and g.get("current_user"):
                colunas.append("IdLoginCriacao")
                valores.append("?")
                params.append(g.current_user["id"])
            connection.cursor().execute(
                f"INSERT INTO {OPERACAO_TABLE} ({', '.join(colunas)}) VALUES ({', '.join(valores)})",
                tuple(params),
            )
            for relatorio_id in relatorios_ids:
                _insert_operation_report_link(connection, operacao_id, relatorio_id)
            connection.commit()
        _log_config(
            "operacao_criacao",
            f"Operacao {nome_operacao} criada com {len(relatorios_ids)} relatorio(s).",
            {"operacao_id": operacao_id, "relatorios": relatorios_ids},
        )
        flash("Operacao criada com sucesso e ja esta disponivel para execucao.", "success")
    except Exception as exc:
        flash(f"Nao foi possivel criar a operacao: {exc}", "error")
        return redirect(url_for("acompanhamento", modal_tipo="criar"))
    return redirect(url_for("acompanhamento"))


@app.post("/acompanhamento/operacoes/<int:operacao_id>/editar")
@login_required
@access_required(1, 2)
def editar_operacao_route(operacao_id: int):
    nome_operacao = _normalize_text(request.form.get("nome_operacao"))
    if not nome_operacao:
        flash("Informe um nome valido para a operacao.", "error")
        return redirect(url_for("acompanhamento"))
    try:
        with closing(_db_connection()) as connection:
            if _operation_name_exists(connection, nome_operacao, exclude_id=operacao_id):
                raise ValueError("Ja existe uma operacao ativa com este nome.")
            connection.cursor().execute(
                f"UPDATE {OPERACAO_TABLE} SET NomeOperacao = ? WHERE IdCapRecursoOperacoes = ?",
                (nome_operacao, operacao_id),
            )
            connection.commit()
        _log_config("operacao_edicao", f"Operacao {operacao_id} atualizada.", {"nome_operacao": nome_operacao})
        flash("Operacao atualizada com sucesso.", "success")
    except Exception as exc:
        flash(f"Nao foi possivel atualizar a operacao: {exc}", "error")
    return redirect(url_for("acompanhamento"))


@app.post("/acompanhamento/operacoes/<int:operacao_id>/inativar")
@login_required
@access_required(1, 2)
def inativar_operacao_route(operacao_id: int):
    try:
        _execute(
            f"UPDATE {OPERACAO_TABLE} SET IdAtivo = 0 WHERE IdCapRecursoOperacoes = ?",
            (operacao_id,),
            commit=True,
        )
        _log_config("operacao_inativacao", f"Operacao {operacao_id} inativada.")
        flash("Operacao inativada com sucesso.", "success")
    except Exception as exc:
        flash(f"Nao foi possivel inativar a operacao: {exc}", "error")
    return redirect(url_for("acompanhamento"))


@app.get("/acompanhamento/operacoes/<int:operacao_id>/relatorios/dados")
@login_required
@access_required(1, 2)
def relatorios_operacao_dados(operacao_id: int):
    try:
        return jsonify(
            {
                "relatorios_disponiveis": _load_relatorios_disponiveis(),
                "relatorios_operacao": _load_relatorios_operacao(operacao_id),
            }
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.post("/acompanhamento/operacoes/<int:operacao_id>/relatorios")
@login_required
@access_required(1, 2)
def adicionar_relatorio_operacao(operacao_id: int):
    relatorio_id = int(request.form.get("id_relatorio") or 0)
    if not relatorio_id:
        flash("Selecione um relatorio.", "error")
        return redirect(
            url_for(
                "acompanhamento",
                modal_tipo="relatorios",
                modal_operacao_id=operacao_id,
                modal_operacao_nome=request.form.get("operacao_nome", ""),
            )
        )
    try:
        with closing(_db_connection()) as connection:
            _insert_operation_report_link(connection, operacao_id, relatorio_id)
            connection.commit()
        _log_config("operacao_relatorio_vinculo", f"Relatorio {relatorio_id} vinculado a operacao {operacao_id}.")
        flash("Relatorio vinculado com sucesso.", "success")
    except Exception as exc:
        flash(f"Nao foi possivel vincular o relatorio: {exc}", "error")

    return redirect(
        url_for(
            "acompanhamento",
            modal_tipo="relatorios",
            modal_operacao_id=operacao_id,
            modal_operacao_nome=request.form.get("operacao_nome", ""),
        )
    )


@app.post("/acompanhamento/operacoes/<int:operacao_id>/filtros")
@login_required
@access_required(1, 2)
def atualizar_filtros_operacao(operacao_id: int):
    relatorio_id = int(request.form.get("id_relatorio") or 0)
    ids_filtro = request.form.getlist("id_filtro")
    valores = request.form.getlist("valor")
    try:
        with closing(_db_connection()) as connection:
            coluna_valor = _get_filter_value_column(connection)
            if not coluna_valor:
                raise ValueError("A tabela de filtros da operacao nao possui coluna de valor configurada.")
            coluna_relatorio_existe = _column_exists(connection, FILTRO_X_OPERACAO_TABLE, "IdCapRecursoRelatorio")
            possui_login_alteracao = _column_exists(connection, FILTRO_X_OPERACAO_TABLE, "IdLoginAlteracao")
            possui_data_alteracao = _column_exists(connection, FILTRO_X_OPERACAO_TABLE, "DataAlteracao")

            for filtro_id, valor in zip(ids_filtro, valores):
                params = [_normalize_text(valor)]
                set_extra = ""
                if possui_data_alteracao:
                    set_extra += ", DataAlteracao = GETDATE()"
                if possui_login_alteracao and g.get("current_user"):
                    set_extra += ", IdLoginAlteracao = ?"
                    params.append(g.current_user["id"])
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
        _log_config("operacao_filtros_atualizacao", f"Filtros atualizados para operacao {operacao_id}.")
        flash("Filtros atualizados com sucesso.", "success")
    except Exception as exc:
        flash(f"Nao foi possivel atualizar os filtros: {exc}", "error")

    return redirect(
        url_for(
            "acompanhamento",
            modal_tipo="relatorios",
            modal_operacao_id=operacao_id,
            modal_operacao_nome=request.form.get("operacao_nome", ""),
        )
    )


@app.post("/acompanhamento/operacoes/<int:operacao_id>/relatorios/remover")
@login_required
@access_required(1, 2)
def remover_relatorio_operacao(operacao_id: int):
    relatorio_id = int(request.form.get("id_relatorio") or 0)
    if not relatorio_id:
        flash("Relatorio invalido para exclusao do vinculo.", "error")
        return redirect(
            url_for(
                "acompanhamento",
                modal_tipo="relatorios",
                modal_operacao_id=operacao_id,
                modal_operacao_nome=request.form.get("operacao_nome", ""),
            )
        )

    try:
        with closing(_db_connection()) as connection:
            cursor = connection.cursor()
            cursor.execute(
                f"SELECT COUNT(1) AS Total FROM {RELATORIO_X_OPERACAO_TABLE} "
                "WHERE IdCapRecursoOperacoes = ? AND IdAtivo = 1",
                (operacao_id,),
            )
            if int(cursor.fetchone().Total or 0) <= 1:
                flash("A operacao deve manter pelo menos um relatorio ativo.", "error")
                return redirect(
                    url_for(
                        "acompanhamento",
                        modal_tipo="relatorios",
                        modal_operacao_id=operacao_id,
                        modal_operacao_nome=request.form.get("operacao_nome", ""),
                    )
                )
            removido = _inativar_relatorio_operacao(connection, operacao_id, relatorio_id)
            connection.commit()

        if removido:
            _log_config("operacao_relatorio_desvinculo", f"Relatorio {relatorio_id} desvinculado da operacao {operacao_id}.")
            flash("Relatorio desvinculado com sucesso.", "success")
        else:
            flash("Este relatorio nao esta mais vinculado a operacao.", "error")
    except Exception as exc:
        flash(f"Nao foi possivel desvincular o relatorio: {exc}", "error")

    return redirect(
        url_for(
            "acompanhamento",
            modal_tipo="relatorios",
            modal_operacao_id=operacao_id,
            modal_operacao_nome=request.form.get("operacao_nome", ""),
        )
    )


@app.get("/relatorios/<int:relatorio_id>/filtros-dados")
@login_required
def relatorio_filtros_dados(relatorio_id: int):
    try:
        relatorio = buscar_relatorio_com_filtros(relatorio_id)
        if not relatorio:
            return jsonify({"error": "Relatorio nao encontrado."}), 404
        relatorio = aplicar_filtros_fixos_relatorio(relatorio)

        filtros = []
        for filtro in relatorio.get("filtros", []):
            clone = dict(filtro)
            clone["opcional"] = eh_filtro_opcional_relatorio(relatorio, filtro)
            if clone.get("automatico"):
                clone["opcional"] = True
            filtros.append(clone)

        return jsonify(
            {
                "relatorio": {
                    "id": relatorio["id"],
                    "nome": relatorio["nome"],
                    "url": relatorio.get("url", ""),
                },
                "filtros": filtros,
            }
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.get("/logs")
@login_required
@access_required(1, 2)
def logs():
    aba = _normalize_text(request.args.get("aba")) or "operacao"
    if g.current_user["access_id"] != 1 and aba == "adm":
        aba = "operacao"

    if aba == "adm":
        filtros = {
            "usuario": _normalize_text(request.args.get("usuario")),
            "tipo_evento": _normalize_text(request.args.get("tipo_evento")),
            "data_inicio": _normalize_text(request.args.get("data_inicio")),
            "data_fim": _normalize_text(request.args.get("data_fim")),
        }
        registros = _safe_db_call(lambda: _load_logs_configuracao(filtros), [])
    else:
        filtros = {
            "nome_operacao": _normalize_text(request.args.get("nome_operacao")),
            "status": _normalize_text(request.args.get("status")),
            "responsavel": _normalize_text(request.args.get("responsavel")),
            "data_inicio": _normalize_text(request.args.get("data_inicio")),
        }
        registros = _safe_db_call(lambda: _load_logs_operacao(filtros), [])

    return render_template("logs.html", aba=aba, filtros=filtros, registros=registros)


def _load_logs_configuracao(filtros: dict) -> list[dict]:
    conditions = []
    params: list[object] = []
    if filtros["usuario"]:
        conditions.append("Usuario LIKE ?")
        params.append(f"%{filtros['usuario']}%")
    if filtros["tipo_evento"]:
        conditions.append("TipoEvento = ?")
        params.append(filtros["tipo_evento"])
    if filtros["data_inicio"]:
        conditions.append("CAST(DataEvento AS date) >= ?")
        params.append(filtros["data_inicio"])
    if filtros["data_fim"]:
        conditions.append("CAST(DataEvento AS date) <= ?")
        params.append(filtros["data_fim"])

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = _fetch_all(
        f"""
        SELECT Usuario, TipoEvento, DataEvento, Detalhe, PayloadJson
        FROM {LOG_CONFIG_TABLE}
        {where_sql}
        ORDER BY DataEvento DESC
        """,
        tuple(params),
    )
    return [
        {
            "usuario": _normalize_text(row.get("Usuario")),
            "evento": _normalize_text(row.get("TipoEvento")),
            "data_evento": _format_datetime(row.get("DataEvento")),
            "detalhe": _normalize_text(row.get("Detalhe")),
            "payload_json": _normalize_text(row.get("PayloadJson")),
        }
        for row in rows
    ]


def _load_logs_operacao(filtros: dict) -> list[dict]:
    conditions = []
    params: list[object] = []
    if filtros["nome_operacao"]:
        conditions.append("NomeOperacao LIKE ?")
        params.append(f"%{filtros['nome_operacao']}%")
    if filtros["status"]:
        conditions.append("Status = ?")
        params.append(filtros["status"])
    if filtros["responsavel"]:
        conditions.append("Responsavel LIKE ?")
        params.append(f"%{filtros['responsavel']}%")
    if filtros["data_inicio"]:
        conditions.append("CAST(Atualizacao AS date) >= ?")
        params.append(filtros["data_inicio"])

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = _fetch_all(
        f"""
        SELECT
            NomeOperacao,
            TipoExecucao,
            NomeRelatorio,
            Status,
            Responsavel,
            Atualizacao,
            Observacao,
            PayloadEntradaJson,
            PayloadResultadoJson,
            ErroJson
        FROM {LOG_OPERACAO_TABLE}
        {where_sql}
        ORDER BY Atualizacao DESC
        """,
        tuple(params),
    )

    registros = []
    for row in rows:
        entrada_json = _normalize_text(row.get("PayloadEntradaJson"))
        entrada = {}
        if entrada_json:
            try:
                entrada = json.loads(entrada_json)
            except json.JSONDecodeError:
                entrada = {}
        registros.append(
            {
                "nome_operacao": _normalize_text(row.get("NomeOperacao")),
                "tipo_execucao": _normalize_text(row.get("TipoExecucao")),
                "nome_relatorio": _normalize_text(row.get("NomeRelatorio")),
                "status": _normalize_text(row.get("Status")),
                "responsavel": _normalize_text(row.get("Responsavel")),
                "atualizacao": _format_datetime(row.get("Atualizacao")),
                "observacao": _normalize_text(row.get("Observacao")),
                "empresa": entrada.get("empresa") if isinstance(entrada.get("empresa"), list) else None,
                "empreendimento": entrada.get("empreendimento") if isinstance(entrada.get("empreendimento"), list) else None,
                "filtros_resumo": entrada.get("filtros"),
                "payload_entrada_json": entrada_json,
                "payload_resultado_json": _normalize_text(row.get("PayloadResultadoJson")),
                "erro_json": _normalize_text(row.get("ErroJson")),
            }
        )
    return registros


@app.get("/logs/exportar")
@login_required
@access_required(1, 2)
def exportar_logs_json():
    aba = _normalize_text(request.args.get("aba")) or "operacao"
    if aba == "adm":
        filtros = {
            "usuario": _normalize_text(request.args.get("usuario")),
            "tipo_evento": _normalize_text(request.args.get("tipo_evento")),
            "data_inicio": _normalize_text(request.args.get("data_inicio")),
            "data_fim": _normalize_text(request.args.get("data_fim")),
        }
        dados = _safe_db_call(lambda: _load_logs_configuracao(filtros), [])
    else:
        filtros = {
            "nome_operacao": _normalize_text(request.args.get("nome_operacao")),
            "status": _normalize_text(request.args.get("status")),
            "responsavel": _normalize_text(request.args.get("responsavel")),
            "data_inicio": _normalize_text(request.args.get("data_inicio")),
        }
        dados = _safe_db_call(lambda: _load_logs_operacao(filtros), [])
    return jsonify({"aba": aba, "registros": dados})


@app.get("/sair")
def sair():
    try:
        if session.get("user_login"):
            _log_config("logout", f"Logout do usuario {session.get('user_login')}.")
    except Exception:
        pass
    clear_execution_preferences_for_current_session()
    clear_execution_result_for_current_session()
    session.clear()
    return redirect(url_for("index"))


def run_application(use_waitress: bool = False) -> None:
    host = os.getenv("APP_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.getenv("APP_PORT", "4732"))
    debug = os.getenv("APP_DEBUG", "false").strip().lower() == "true"

    start_browser_thread(host, port)

    if use_waitress:
        from waitress import serve

        serve(app, host=host, port=port)
        return

    app.run(host=host, port=port, debug=debug)
