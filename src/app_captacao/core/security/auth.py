"""Login local, admin de desenvolvimento e decorators de permissao."""

from __future__ import annotations

import hmac
import os
from functools import wraps

from flask import flash, g, redirect, url_for
from werkzeug.security import check_password_hash


def verify_password(raw_password: str, stored_password: str) -> bool:
    """Hash werkzeug ou senha legada em texto puro (tabela compartilhada com outro sistema)."""
    if not stored_password:
        return False
    if stored_password.startswith(("pbkdf2:", "scrypt:")):
        try:
            return check_password_hash(stored_password, raw_password)
        except ValueError:
            # Hash corrompido nao cai para a comparacao em texto puro.
            return False
    return hmac.compare_digest(stored_password.encode("utf-8"), raw_password.encode("utf-8"))


def bootstrap_admin_profile() -> dict | None:
    """Admin local de desenvolvimento; so existe quando habilitado e com hash de senha definido."""
    enabled = os.getenv("DEV_BOOTSTRAP_ADMIN_ENABLED", "false").strip().lower() == "true"
    password_hash = os.getenv("DEV_BOOTSTRAP_ADMIN_PASSWORD_HASH", "").strip()
    if not enabled or not password_hash:
        return None

    return {
        "id": int(os.getenv("DEV_BOOTSTRAP_ADMIN_ID", "999999")),
        "login": os.getenv("DEV_BOOTSTRAP_ADMIN_LOGIN", "admin"),
        "email": os.getenv("DEV_BOOTSTRAP_ADMIN_EMAIL", "admin@local.test"),
        "area": os.getenv("DEV_BOOTSTRAP_ADMIN_AREA", "performance"),
        "access_id": int(os.getenv("DEV_BOOTSTRAP_ADMIN_ACCESS_ID", "1")),
        "perfil": "Administrador",
        "ativo": True,
        "status": "Ativo",
        "data_criacao": "-",
        "_bootstrap": True,
    }


def bootstrap_admin_user(login: str, senha: str) -> dict | None:
    profile = bootstrap_admin_profile()
    if not profile or login != profile["login"]:
        return None
    password_hash = os.getenv("DEV_BOOTSTRAP_ADMIN_PASSWORD_HASH", "").strip()
    try:
        if not check_password_hash(password_hash, senha):
            return None
    except ValueError:
        return None
    return profile


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
