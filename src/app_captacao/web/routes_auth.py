"""Rotas de autenticacao no AppCaptacao: login, logout e perfil do usuario."""

from __future__ import annotations

import logging

from flask import flash, g, redirect, render_template, request, session, url_for

from app_captacao.core.database import sql
from app_captacao.core.persistence import usuarios as usuarios_repo
from app_captacao.core.security import auth
from app_captacao.core.security.auth import login_required
from app_captacao.core.shared.texto import normalize_text
from app_captacao.execucao import jobs
from app_captacao.web import auditoria
from app_captacao.web.registro import RegistroRotas

logger = logging.getLogger(__name__)
rotas = RegistroRotas()


@rotas.route("/")
def index():
    if g.get("current_user"):
        return redirect(url_for("main"))
    return render_template("index.html")


@rotas.post("/login")
def login():
    login_value = normalize_text(request.form.get("login"))
    senha = str(request.form.get("senha") or "")
    payload_login = {"login_informado": login_value}

    if not login_value or not senha:
        try:
            auditoria.log_config("login_falha", "Tentativa de login sem preencher login ou senha.", payload_login)
        except Exception:
            pass
        flash("Informe o usuário e a senha para entrar.", "error")
        return redirect(url_for("index"))

    raw_user = None
    login_db_error = None
    try:
        raw_user = usuarios_repo.load_user_by_login(login_value)
    except Exception as exc:
        login_db_error = exc

    bootstrap_user = auth.bootstrap_admin_user(login_value, senha)
    if not raw_user and bootstrap_user:
        session.clear()
        session["user_id"] = bootstrap_user["id"]
        session["user_login"] = bootstrap_user["login"]
        session["user_email"] = bootstrap_user.get("email", "")
        session["user_area"] = bootstrap_user.get("area", "")
        session["user_access_id"] = bootstrap_user.get("access_id", 0)
        session["user_data_criacao"] = bootstrap_user.get("data_criacao", "-")
        try:
            auditoria.log_config("login", "Login realizado com admin local de desenvolvimento.", payload_login)
        except Exception:
            pass
        return redirect(url_for("main"))

    if login_db_error:
        logger.error("Falha ao validar login no banco de dados.", exc_info=login_db_error)
        try:
            auditoria.log_config("login_falha", "Erro ao validar login no banco de dados.", payload_login)
        except Exception:
            pass
        flash("Não foi possível validar o login no banco de dados.", "error")
        return redirect(url_for("index"))

    user = usuarios_repo.serialize_user(raw_user)
    if not raw_user or not user or not user["ativo"]:
        try:
            auditoria.log_config("login_falha", "Usuário inexistente ou inativo.", payload_login)
        except Exception:
            pass
        flash("Usuário ou senha inválidos.", "error")
        return redirect(url_for("index"))

    if not auth.verify_password(senha, normalize_text(raw_user.get("senha"))):
        try:
            auditoria.log_config("login_falha", "Senha inválida.", payload_login)
        except Exception:
            pass
        flash("Usuário ou senha inválidos.", "error")
        return redirect(url_for("index"))

    session.clear()
    session["user_id"] = user["id"]
    session["user_login"] = user["login"]
    session["user_email"] = user.get("email", "")
    session["user_area"] = user.get("area", "")
    session["user_access_id"] = user.get("access_id", 0)
    session["user_data_criacao"] = user.get("data_criacao", "-")
    try:
        auditoria.log_config("login", "Login realizado com sucesso.", payload_login)
    except Exception:
        pass
    flash(f"Olá, {user['login']}.", "success")
    return redirect(url_for("main"))


@rotas.get("/sair")
def sair():
    try:
        if session.get("user_login"):
            auditoria.log_config("logout", f"Logout do usuário {session.get('user_login')}.")
    except Exception:
        pass
    jobs.clear_execution_preferences_for_current_session()
    jobs.clear_execution_result_for_current_session()
    session.clear()
    return redirect(url_for("index"))


@rotas.get("/perfil")
@login_required
def perfil():
    return render_template("perfil.html", perfil_usuario=g.current_user)


@rotas.post("/perfil/senha")
@login_required
def atualizar_minha_senha():
    if g.current_user.get("_bootstrap"):
        flash("Não é possível alterar aqui a senha do usuário de bootstrap.", "error")
        return redirect(url_for("perfil"))

    senha_atual = str(request.form.get("senha_atual") or "")
    nova_senha = str(request.form.get("nova_senha") or "")
    confirmar = str(request.form.get("confirmar_senha") or "")

    raw_user = sql.safe_db_call(lambda: usuarios_repo.load_user_by_login(g.current_user["login"]), None)
    if not raw_user or not auth.verify_password(senha_atual, normalize_text(raw_user.get("senha"))):
        flash("Senha atual incorreta.", "error")
        return redirect(url_for("perfil"))
    if not nova_senha or nova_senha != confirmar:
        flash("A nova senha e a confirmação precisam ser iguais.", "error")
        return redirect(url_for("perfil"))

    try:
        usuarios_repo.atualizar_senha(g.current_user["id"], nova_senha)
    except Exception:
        logger.exception("Falha ao atualizar a senha do usuario %s.", g.current_user["login"])
        flash("Não foi possível atualizar a senha no banco. Tente novamente.", "error")
        return redirect(url_for("perfil"))
    auditoria.log_config("senha_atualizacao", "Usuário trocou a própria senha.")
    flash("Senha atualizada.", "success")
    return redirect(url_for("perfil"))
