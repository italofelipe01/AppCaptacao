"""Rotas de gestao de usuarios (somente administrador)."""

from __future__ import annotations

import logging
from typing import Any

from flask import flash, g, redirect, render_template, request, url_for

from app_captacao.core.database import sql
from app_captacao.core.persistence import usuarios as usuarios_repo
from app_captacao.core.security.auth import access_required, login_required
from app_captacao.core.shared.texto import normalize_text
from app_captacao.web import auditoria
from app_captacao.web.registro import RegistroRotas

logger = logging.getLogger(__name__)
rotas = RegistroRotas()


@rotas.get("/usuarios")
@login_required
def usuarios():
    if g.current_user["access_id"] != 1:
        return redirect(url_for("perfil"))

    filtro_busca = normalize_text(request.args.get("busca"))
    filtro_status = normalize_text(request.args.get("status")) or "ativos"
    usuarios_lista = sql.safe_db_call(lambda: usuarios_repo.load_usuarios(filtro_busca, filtro_status), [])

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


@rotas.post("/usuarios")
@login_required
@access_required(1)
def cadastrar_usuario():
    login_usuario = normalize_text(request.form.get("login_usuario"))
    email = normalize_text(request.form.get("email"))
    area = normalize_text(request.form.get("area"))
    raw_id_acesso = normalize_text(request.form.get("id_acesso"))
    senha = str(request.form.get("senha") or "")
    confirmar = str(request.form.get("confirmar_senha") or "")

    modal_params: dict[str, Any] = {
        "modal_tipo": "criar",
        "modal_usuario_login": login_usuario,
        "modal_usuario_email": email,
        "modal_usuario_area": area,
        "modal_usuario_id_acesso": raw_id_acesso,
    }
    if not all([login_usuario, email, area, raw_id_acesso, senha, confirmar]):
        flash("Preencha todos os campos obrigatórios do cadastro.", "error")
        return redirect(url_for("usuarios", **modal_params))
    if senha != confirmar:
        flash("A senha e a confirmação precisam ser iguais.", "error")
        return redirect(url_for("usuarios", **modal_params))

    try:
        id_acesso = int(raw_id_acesso)
    except ValueError:
        id_acesso = 0
    if id_acesso not in {1, 2, 3}:
        flash("Selecione um nível de acesso válido.", "error")
        return redirect(url_for("usuarios", **modal_params))

    try:
        usuarios_repo.criar_usuario(login_usuario, email, area, id_acesso, senha)
        auditoria.log_config("usuario_criacao", f"Usuário {login_usuario} criado.", {"email": email, "area": area})
        flash("Usuário cadastrado.", "success")
        return redirect(url_for("usuarios"))
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("usuarios", **modal_params))
    except Exception:
        logger.exception("Falha ao cadastrar usuario.")
        flash("Não foi possível cadastrar o usuário no banco.", "error")
        return redirect(url_for("usuarios", **modal_params))


@rotas.post("/usuarios/<int:id_login>/editar")
@login_required
@access_required(1)
def editar_usuario(id_login: int):
    email = normalize_text(request.form.get("email"))
    area = normalize_text(request.form.get("area"))
    raw_id_acesso = normalize_text(request.form.get("id_acesso"))
    senha = str(request.form.get("senha") or "")
    confirmar = str(request.form.get("confirmar_senha") or "")
    usuario_login = normalize_text(request.form.get("usuario_login"))

    modal_params: dict[str, Any] = {
        "modal_tipo": "editar",
        "modal_usuario_id": id_login,
        "modal_usuario_login": usuario_login,
        "modal_usuario_email": email,
        "modal_usuario_area": area,
        "modal_usuario_id_acesso": raw_id_acesso,
    }

    if not all([email, area, raw_id_acesso]):
        flash("Preencha e-mail, área e nível de acesso.", "error")
        return redirect(url_for("usuarios", **modal_params))

    if senha != confirmar:
        flash("A nova senha e a confirmação precisam ser iguais.", "error")
        return redirect(url_for("usuarios", **modal_params))

    try:
        id_acesso = int(raw_id_acesso)
    except ValueError:
        id_acesso = 0
    if id_acesso not in {1, 2, 3}:
        flash("Selecione um nível de acesso válido.", "error")
        return redirect(url_for("usuarios", **modal_params))

    try:
        usuarios_repo.atualizar_usuario(
            id_login,
            usuario_login,
            email,
            area,
            id_acesso,
            senha,
            alterado_por=g.current_user["id"] if g.get("current_user") else None,
        )
        auditoria.log_config("usuario_edicao", f"Usuário {id_login} atualizado.")
        flash("Usuário atualizado.", "success")
        return redirect(url_for("usuarios"))
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("usuarios", **modal_params))
    except Exception:
        logger.exception("Falha ao atualizar usuario %s.", id_login)
        flash("Não foi possível atualizar o usuário no banco.", "error")
        return redirect(url_for("usuarios", **modal_params))


@rotas.post("/usuarios/<int:id_login>/inativar")
@login_required
@access_required(1)
def inativar_usuario_route(id_login: int):
    if g.current_user["id"] == id_login:
        flash("Você não pode inativar o próprio usuário.", "error")
        return redirect(url_for("usuarios"))
    try:
        usuarios_repo.inativar_usuario(id_login, alterado_por=g.current_user["id"])
        auditoria.log_config("usuario_inativacao", f"Usuário {id_login} inativado.")
        flash("Usuário inativado.", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    except Exception:
        logger.exception("Falha ao inativar usuario %s.", id_login)
        flash("Não foi possível inativar o usuário no banco.", "error")
    return redirect(url_for("usuarios"))
