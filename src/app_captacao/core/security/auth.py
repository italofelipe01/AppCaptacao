"""Login local, admin de desenvolvimento e decorators de permissao."""

from __future__ import annotations

import os
from functools import wraps

from flask import flash, g, redirect, url_for
from werkzeug.security import check_password_hash


def verify_password(raw_password: str, stored_password: str) -> bool:
    if not stored_password:
        return False
    try:
        if stored_password.startswith(("pbkdf2:", "scrypt:")):
            return check_password_hash(stored_password, raw_password)
    except ValueError:
        pass
    return stored_password == raw_password


def bootstrap_admin_user(login: str, senha: str) -> dict | None:
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
