"""Aplicacao Flask do AppCaptacao: instancia unica, sessao, usuario atual e registro das rotas."""

from __future__ import annotations

import os
import secrets

from flask import Flask, g, request, session

from app_captacao.core.config import settings  # noqa: F401  (carrega o .env antes de tudo)
from app_captacao.core.config.environment import get_static_path, get_template_path
from app_captacao.core.security.sessao_usuario import carregar_usuario_da_sessao
from app_captacao.core.shared.navegador_local import start_browser_thread
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
    if request.endpoint == "static":
        # Arquivo estatico nao precisa de usuario: evita uma consulta ao banco por asset.
        return
    g.current_user = carregar_usuario_da_sessao(session)
    if g.current_user is None and session.get("user_login"):
        # Usuario inativado ou excluido: a sessao antiga deixa de valer.
        session.clear()


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
