"""Usuario autenticado a partir da sessao assinada do Flask.

O banco e a fonte de verdade: usuario inativado ou excluido perde o acesso na
proxima requisicao. Se o banco estiver indisponivel, os dados da sessao
assinada sao usados para nao derrubar quem ja estava autenticado.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from app_captacao.core.persistence import usuarios as usuarios_repo
from app_captacao.core.security import auth
from app_captacao.core.security.perfis import descricao_perfil
from app_captacao.core.shared.texto import normalize_text

logger = logging.getLogger(__name__)


def _usuario_da_sessao(sessao: Mapping[str, Any]) -> dict:
    access_id = int(sessao.get("user_access_id") or 0)
    return {
        "id": int(sessao.get("user_id") or 0),
        "login": normalize_text(sessao.get("user_login")),
        "email": normalize_text(sessao.get("user_email")),
        "area": normalize_text(sessao.get("user_area")),
        "access_id": access_id,
        "perfil": descricao_perfil(access_id),
        "ativo": True,
        "status": "Ativo",
        "data_criacao": normalize_text(sessao.get("user_data_criacao")) or "-",
    }


def carregar_usuario_da_sessao(sessao: Mapping[str, Any]) -> dict | None:
    login = normalize_text(sessao.get("user_login"))
    if not login:
        return None

    user_id = int(sessao.get("user_id") or 0)
    bootstrap = auth.bootstrap_admin_profile()
    if bootstrap and user_id == bootstrap["id"] and login == bootstrap["login"]:
        return bootstrap

    if not user_id:
        return _usuario_da_sessao(sessao)

    try:
        row = usuarios_repo.load_user_by_id(user_id)
    except Exception:
        logger.exception("Banco indisponivel ao carregar o usuario %s; usando os dados da sessao.", login)
        return _usuario_da_sessao(sessao)

    usuario = usuarios_repo.serialize_user(row)
    if not usuario or not usuario["ativo"]:
        return None
    return usuario
