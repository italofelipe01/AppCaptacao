"""Rotas de consulta e exportacao dos logs persistidos."""

from __future__ import annotations

from flask import g, jsonify, render_template, request

from app_captacao.core.database import sql
from app_captacao.core.persistence import logs as logs_repo
from app_captacao.core.security.auth import access_required, login_required
from app_captacao.core.shared.texto import normalize_text
from app_captacao.web.registro import RegistroRotas

rotas = RegistroRotas()


@rotas.get("/logs")
@login_required
@access_required(1, 2)
def logs():
    aba = normalize_text(request.args.get("aba")) or "operacao"
    if g.current_user["access_id"] != 1 and aba == "adm":
        aba = "operacao"

    if aba == "adm":
        filtros = {
            "usuario": normalize_text(request.args.get("usuario")),
            "tipo_evento": normalize_text(request.args.get("tipo_evento")),
            "data_inicio": normalize_text(request.args.get("data_inicio")),
            "data_fim": normalize_text(request.args.get("data_fim")),
        }
        registros = sql.safe_db_call(lambda: logs_repo.load_logs_configuracao(filtros), [])
    else:
        filtros = {
            "nome_operacao": normalize_text(request.args.get("nome_operacao")),
            "status": normalize_text(request.args.get("status")),
            "responsavel": normalize_text(request.args.get("responsavel")),
            "data_inicio": normalize_text(request.args.get("data_inicio")),
        }
        registros = sql.safe_db_call(lambda: logs_repo.load_logs_operacao(filtros), [])

    return render_template("logs.html", aba=aba, filtros=filtros, registros=registros)


@rotas.get("/logs/exportar")
@login_required
@access_required(1, 2)
def exportar_logs_json():
    aba = normalize_text(request.args.get("aba")) or "operacao"
    if aba == "adm":
        filtros = {
            "usuario": normalize_text(request.args.get("usuario")),
            "tipo_evento": normalize_text(request.args.get("tipo_evento")),
            "data_inicio": normalize_text(request.args.get("data_inicio")),
            "data_fim": normalize_text(request.args.get("data_fim")),
        }
        dados = sql.safe_db_call(lambda: logs_repo.load_logs_configuracao(filtros), [])
    else:
        filtros = {
            "nome_operacao": normalize_text(request.args.get("nome_operacao")),
            "status": normalize_text(request.args.get("status")),
            "responsavel": normalize_text(request.args.get("responsavel")),
            "data_inicio": normalize_text(request.args.get("data_inicio")),
        }
        dados = sql.safe_db_call(lambda: logs_repo.load_logs_operacao(filtros), [])
    return jsonify({"aba": aba, "registros": dados})
