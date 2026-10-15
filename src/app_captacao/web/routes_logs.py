"""Rotas de consulta e exportacao dos logs persistidos."""

from __future__ import annotations

from flask import g, jsonify, render_template, request

from app_captacao.core.database import sql
from app_captacao.core.persistence import logs as logs_repo
from app_captacao.core.security.auth import access_required, login_required
from app_captacao.core.security.perfis import ACESSO_ADMINISTRADOR, ACESSO_CADASTRO_OPERACAO
from app_captacao.core.shared.texto import normalize_text
from app_captacao.web.registro import RegistroRotas

rotas = RegistroRotas()


def _aba_permitida() -> str:
    """Aba pedida na URL; a administrativa so existe para o administrador."""
    aba = normalize_text(request.args.get("aba")) or "operacao"
    if aba == "adm" and g.current_user["access_id"] != ACESSO_ADMINISTRADOR:
        return "operacao"
    return aba


def _carregar_registros(aba: str) -> tuple[dict, list[dict]]:
    if aba == "adm":
        filtros = {
            "usuario": normalize_text(request.args.get("usuario")),
            "tipo_evento": normalize_text(request.args.get("tipo_evento")),
            "data_inicio": normalize_text(request.args.get("data_inicio")),
            "data_fim": normalize_text(request.args.get("data_fim")),
        }
        return filtros, sql.safe_db_call(lambda: logs_repo.load_logs_configuracao(filtros), [])

    filtros = {
        "nome_operacao": normalize_text(request.args.get("nome_operacao")),
        "status": normalize_text(request.args.get("status")),
        "responsavel": normalize_text(request.args.get("responsavel")),
        "data_inicio": normalize_text(request.args.get("data_inicio")),
    }
    return filtros, sql.safe_db_call(lambda: logs_repo.load_logs_operacao(filtros), [])


@rotas.get("/logs")
@login_required
@access_required(ACESSO_ADMINISTRADOR, ACESSO_CADASTRO_OPERACAO)
def logs():
    aba = _aba_permitida()
    filtros, registros = _carregar_registros(aba)
    return render_template("logs.html", aba=aba, filtros=filtros, registros=registros)


@rotas.get("/logs/exportar")
@login_required
@access_required(ACESSO_ADMINISTRADOR, ACESSO_CADASTRO_OPERACAO)
def exportar_logs_json():
    aba = _aba_permitida()
    _, dados = _carregar_registros(aba)
    return jsonify({"aba": aba, "registros": dados})
