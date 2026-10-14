"""Autenticacao de usuario de rede Windows (LogonUser).

Implementada, mas ainda nao ligada ao fluxo de /login: o login atual valida a
senha da tabela de usuarios. Ver docs/DECISIONS.md.
"""

from __future__ import annotations

import os

from app_captacao.core.persistence import usuarios as usuarios_repo
from app_captacao.core.security.perfis import descricao_perfil
from app_captacao.core.shared.texto import normalize_text

WIN32SECURITY_IMPORT_ERROR = None
try:
    import win32security
except ImportError as exc:  # pragma: no cover - dependencia opcional fora do Windows corporativo
    win32security = None
    WIN32SECURITY_IMPORT_ERROR = exc


def parse_network_login(login_value: str) -> tuple[str | None, str]:
    login_normalizado = normalize_text(login_value)
    if "\\" in login_normalizado:
        dominio, usuario = login_normalizado.split("\\", 1)
        return normalize_text(dominio) or None, normalize_text(usuario)
    if "@" in login_normalizado:
        return None, login_normalizado
    dominio = normalize_text(os.getenv("NETWORK_AUTH_DOMAIN")) or normalize_text(os.getenv("USERDOMAIN")) or None
    return dominio, login_normalizado


def resolve_app_login_candidates(login_value: str) -> list[str]:
    candidatos: list[str] = []
    login_normalizado = normalize_text(login_value)
    if login_normalizado:
        candidatos.append(login_normalizado)
    if "\\" in login_normalizado:
        candidatos.append(normalize_text(login_normalizado.split("\\", 1)[1]))
    if "@" in login_normalizado:
        candidatos.append(normalize_text(login_normalizado.split("@", 1)[0]))
    return list(dict.fromkeys([item for item in candidatos if item]))


def authenticate_network_user(login_value: str, senha: str) -> dict | None:
    if not login_value or not senha or os.name != "nt" or win32security is None:
        return None

    dominio, usuario = parse_network_login(login_value)
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
            "login_informado": normalize_text(login_value),
            "login_app": resolve_app_login_candidates(login_value)[-1] if resolve_app_login_candidates(login_value) else normalize_text(login_value),
            "dominio": dominio or "",
            "usuario_rede": normalize_text(usuario),
        }
    finally:
        try:
            token.Close()
        except Exception:
            pass


def network_auth_available() -> tuple[bool, str]:
    if os.name != "nt":
        return False, "Autenticacao de rede disponivel apenas no Windows."
    if win32security is None:
        detalhe = f" ({WIN32SECURITY_IMPORT_ERROR})" if WIN32SECURITY_IMPORT_ERROR else ""
        return False, f"Modulo de autenticacao Windows indisponivel{detalhe}"
    return True, ""


def build_network_user(app_login: str, network_identity: dict, row: dict | None = None) -> dict:
    user = usuarios_repo.serialize_user(row) if row else None
    if user:
        return user

    access_id = int(os.getenv("NETWORK_AUTH_DEFAULT_ACCESS_ID", "3") or 3)
    dominio = normalize_text(network_identity.get("dominio"))
    usuario_rede = normalize_text(network_identity.get("usuario_rede")) or app_login
    return {
        "id": int(os.getenv("NETWORK_AUTH_SYNTHETIC_USER_ID", "0") or 0),
        "login": app_login,
        "email": f"{usuario_rede}@{dominio.lower()}.local" if dominio else "",
        "area": os.getenv("NETWORK_AUTH_DEFAULT_AREA", "rede"),
        "access_id": access_id,
        "perfil": descricao_perfil(access_id),
        "ativo": True,
        "status": "Ativo",
        "data_criacao": "-",
        "_network": True,
    }
