"""Tabela de usuarios do AppCaptacao (USUARIO_TABLE)."""

from __future__ import annotations

from contextlib import closing

import pyodbc
from werkzeug.security import generate_password_hash

from app_captacao.core.config.settings import USUARIO_TABLE
from app_captacao.core.database import sql
from app_captacao.core.security.perfis import descricao_perfil
from app_captacao.core.shared.texto import format_datetime, normalize_text, to_bool


def load_user_by_login(login: str) -> dict | None:
    return sql.fetch_one(
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


def load_user_by_id(user_id: int) -> dict | None:
    return sql.fetch_one(
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


def serialize_user(row: dict | None) -> dict | None:
    if not row:
        return None
    access_id = int(row.get("access_id") or 0)
    return {
        "id": int(row.get("id") or 0),
        "login": normalize_text(row.get("login")),
        "email": normalize_text(row.get("email")),
        "area": normalize_text(row.get("area")),
        "access_id": access_id,
        "perfil": descricao_perfil(access_id),
        "ativo": to_bool(row.get("ativo")),
        "status": "Ativo" if to_bool(row.get("ativo")) else "Inativo",
        "data_criacao": format_datetime(row.get("data_criacao")),
    }


def load_usuarios(filtro_busca: str, filtro_status: str) -> list[dict]:
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

    rows = sql.fetch_all(
        f"""
        SELECT
            u.IdLogin AS id,
            u.Login AS login,
            u.Email AS email,
            u.Area AS area,
            u.IdAcesso AS access_id,
            u.IdAtivo AS ativo,
            u.DataCriacao AS data_criacao
        FROM {USUARIO_TABLE} u
        {where_sql}
        ORDER BY u.Login
        """,
        tuple(params),
    )
    usuarios = []
    for row in rows:
        usuario = serialize_user(row)
        usuario["id_acesso"] = int(row.get("access_id") or 0)
        usuarios.append(usuario)
    return usuarios


def user_duplicate_field(
    connection: pyodbc.Connection,
    login_usuario: str,
    email: str,
    exclude_id: int | None = None,
) -> str | None:
    conditions = ["(LOWER(Login) = LOWER(?) OR LOWER(Email) = LOWER(?))"]
    params: list[object] = [login_usuario, email]
    if exclude_id is not None:
        conditions.append("IdLogin <> ?")
        params.append(exclude_id)

    cursor = connection.cursor()
    cursor.execute(
        f"""
        SELECT TOP 1 Login, Email
        FROM {USUARIO_TABLE} WITH (UPDLOCK, HOLDLOCK)
        WHERE {' AND '.join(conditions)}
        """,
        tuple(params),
    )
    row = cursor.fetchone()
    if not row:
        return None
    if normalize_text(row.Login).lower() == login_usuario.lower():
        return "login"
    return "email"


def criar_usuario(login_usuario: str, email: str, area: str, id_acesso: int, senha: str) -> None:
    """Grava usuario novo com senha em hash scrypt; login ou email repetido vira ValueError."""
    with closing(sql.db_connection()) as connection:
        duplicate_field = user_duplicate_field(connection, login_usuario, email)
        if duplicate_field:
            label = "login" if duplicate_field == "login" else "email"
            raise ValueError(f"Ja existe um usuario com este {label}.")

        cursor = connection.cursor()
        senha_hash = generate_password_hash(senha, method="scrypt")
        if sql.column_is_identity(connection, USUARIO_TABLE, "IdLogin"):
            cursor.execute(
                f"""
                INSERT INTO {USUARIO_TABLE}
                    (Login, Email, Area, Senha, IdAcesso, IdAtivo, DataCriacao)
                VALUES (?, ?, ?, ?, ?, 1, GETDATE())
                """,
                (login_usuario, email, area, senha_hash, id_acesso),
            )
        else:
            id_login = sql.get_next_id(connection, USUARIO_TABLE, "IdLogin")
            cursor.execute(
                f"""
                INSERT INTO {USUARIO_TABLE}
                    (IdLogin, Login, Email, Area, Senha, IdAcesso, IdAtivo, DataCriacao)
                VALUES (?, ?, ?, ?, ?, ?, 1, GETDATE())
                """,
                (id_login, login_usuario, email, area, senha_hash, id_acesso),
            )
        connection.commit()


def atualizar_usuario(
    id_login: int,
    usuario_login: str,
    email: str,
    area: str,
    id_acesso: int,
    senha: str,
    alterado_por: int | None,
) -> None:
    """Atualiza email, area, perfil e, quando informada, a senha. Falhas de regra viram ValueError."""
    with closing(sql.db_connection()) as connection:
        duplicate_field = user_duplicate_field(
            connection,
            usuario_login,
            email,
            exclude_id=id_login,
        )
        if duplicate_field == "email":
            raise ValueError("Ja existe outro usuario com este email.")

        assignments = ["Email = ?", "Area = ?", "IdAcesso = ?"]
        params: list[object] = [email, area, id_acesso]
        if senha:
            assignments.append("Senha = ?")
            params.append(generate_password_hash(senha, method="scrypt"))
        if sql.column_exists(connection, USUARIO_TABLE, "DataAlteracao"):
            assignments.append("DataAlteracao = GETDATE()")
        if sql.column_exists(connection, USUARIO_TABLE, "IdLoginAlteracao") and alterado_por is not None:
            assignments.append("IdLoginAlteracao = ?")
            params.append(alterado_por)
        params.append(id_login)

        cursor = connection.cursor()
        cursor.execute(
            f"UPDATE {USUARIO_TABLE} SET {', '.join(assignments)} WHERE IdLogin = ?",
            tuple(params),
        )
        if cursor.rowcount == 0:
            raise ValueError("Usuario nao encontrado.")
        connection.commit()


def inativar_usuario(id_login: int, alterado_por: int) -> None:
    """Inativa usuario ativo; usuario inexistente ou ja inativo vira ValueError."""
    with closing(sql.db_connection()) as connection:
        assignments = ["IdAtivo = 0"]
        params: list[object] = []
        if sql.column_exists(connection, USUARIO_TABLE, "DataAlteracao"):
            assignments.append("DataAlteracao = GETDATE()")
        if sql.column_exists(connection, USUARIO_TABLE, "IdLoginAlteracao"):
            assignments.append("IdLoginAlteracao = ?")
            params.append(alterado_por)
        params.append(id_login)
        cursor = connection.cursor()
        cursor.execute(
            f"UPDATE {USUARIO_TABLE} SET {', '.join(assignments)} WHERE IdLogin = ? AND IdAtivo = 1",
            tuple(params),
        )
        if cursor.rowcount == 0:
            raise ValueError("Usuario nao encontrado ou ja inativo.")
        connection.commit()


def atualizar_senha(id_login: int, nova_senha: str) -> None:
    sql.execute(
        f"UPDATE {USUARIO_TABLE} SET Senha = ? WHERE IdLogin = ?",
        (generate_password_hash(nova_senha), id_login),
        commit=True,
    )
