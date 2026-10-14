"""Aplicacao Flask do AppCaptacao: instancia unica, sessao, usuario atual e registro das rotas."""

from __future__ import annotations

import os
import secrets

from flask import Flask, g, session

from app_captacao.core.config import settings  # noqa: F401  (carrega o .env antes de tudo)
from app_captacao.core.config.environment import get_static_path, get_template_path
from app_captacao.core.database import sql
from app_captacao.core.persistence import usuarios as usuarios_repo
from app_captacao.core.security import auth
from app_captacao.core.security.perfis import descricao_perfil
from app_captacao.core.shared.navegador_local import start_browser_thread
from app_captacao.core.shared.texto import normalize_text
from app_captacao.web import (
    routes_acompanhamento,
    routes_auth,
    routes_execucao,
    routes_logs,
    routes_usuarios,
)

app = Flask(
    __name__,
    template_folder=get_template_path(),
    static_folder=get_static_path(),
)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "").strip() or secrets.token_urlsafe(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False


@app.before_request
def load_current_user() -> None:
    g.current_user = None
    user_id = session.get("user_id")
    if user_id:
        try:
            g.current_user = sql.safe_db_call(lambda: usuarios_repo.serialize_user(usuarios_repo.load_user_by_id(int(user_id))), None)
        except Exception:
            g.current_user = None
    if not g.current_user and session.get("user_login"):
        access_id = int(session.get("user_access_id") or 0)
        g.current_user = {
            "id": int(session.get("user_id") or 0),
            "login": normalize_text(session.get("user_login")),
            "email": normalize_text(session.get("user_email")),
            "area": normalize_text(session.get("user_area")),
            "access_id": access_id,
            "perfil": descricao_perfil(access_id),
            "ativo": True,
            "status": "Ativo",
            "data_criacao": normalize_text(session.get("user_data_criacao")) or "-",
        }
    if not g.current_user and session.get("user_login") == os.getenv("DEV_BOOTSTRAP_ADMIN_LOGIN", "admin"):
        g.current_user = auth.bootstrap_admin_user(session.get("user_login", ""), "")


@app.context_processor
def inject_globals() -> dict:
    return {"current_user": g.get("current_user")}


for _modulo_rotas in (
    routes_auth,
    routes_execucao,
    routes_usuarios,
    routes_acompanhamento,
    routes_logs,
):
    _modulo_rotas.rotas.registrar(app)


def run_application(use_waitress: bool = False, open_browser: bool = True) -> None:
    host = os.getenv("APP_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.getenv("APP_PORT", "4732"))
    debug = os.getenv("APP_DEBUG", "false").strip().lower() == "true"

    if open_browser:
        start_browser_thread(host, port)

    if use_waitress:
        from waitress import serve

        serve(app, host=host, port=port)
        return

    app.run(host=host, port=port, debug=debug)
