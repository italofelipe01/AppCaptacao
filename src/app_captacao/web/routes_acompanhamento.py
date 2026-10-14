"""Rotas de Acompanhamento: cadastro de operacoes, vinculos com relatorios e valores de filtro."""

from __future__ import annotations

from flask import flash, g, jsonify, redirect, render_template, request, url_for

from app_captacao.catalogo import operacao_relatorios as vinculos_repo
from app_captacao.catalogo import operacoes as operacoes_repo
from app_captacao.catalogo import relatorios as relatorios_repo
from app_captacao.core.database import sql
from app_captacao.core.security.auth import access_required, login_required
from app_captacao.core.shared.texto import normalize_text
from app_captacao.web import auditoria
from app_captacao.web.registro import RegistroRotas

rotas = RegistroRotas()


def _usuario_id() -> int | None:
    current_user = g.get("current_user")
    return current_user["id"] if current_user else None


def _redirecionar_modal_relatorios(operacao_id: int):
    return redirect(
        url_for(
            "acompanhamento",
            modal_tipo="relatorios",
            modal_operacao_id=operacao_id,
            modal_operacao_nome=request.form.get("operacao_nome", ""),
        )
    )


@rotas.get("/acompanhamento")
@login_required
@access_required(1, 2)
def acompanhamento():
    filtro_nome = normalize_text(request.args.get("nome_operacao"))
    operacoes = sql.safe_db_call(lambda: operacoes_repo.load_operacoes(filtro_nome), [])
    relatorios_disponiveis = sql.safe_db_call(relatorios_repo.load_relatorios_disponiveis, [])
    return render_template(
        "acompanhamento.html",
        operacoes=operacoes,
        relatorios_disponiveis=relatorios_disponiveis,
        filtro_nome=filtro_nome,
        modal_tipo=request.args.get("modal_tipo"),
        modal_operacao_id=request.args.get("modal_operacao_id"),
        modal_operacao_nome=request.args.get("modal_operacao_nome"),
    )


@rotas.post("/acompanhamento/operacoes")
@login_required
@access_required(1, 2)
def criar_operacao_route():
    nome_operacao = normalize_text(request.form.get("nome_operacao"))
    relatorios_ids_raw = request.form.getlist("id_relatorio")
    relatorios_ids: list[int] = []
    for value in relatorios_ids_raw:
        try:
            relatorio_id = int(value)
        except (TypeError, ValueError):
            continue
        if relatorio_id > 0 and relatorio_id not in relatorios_ids:
            relatorios_ids.append(relatorio_id)
    if not nome_operacao:
        flash("Informe o nome da operacao.", "error")
        return redirect(url_for("acompanhamento", modal_tipo="criar"))
    if not relatorios_ids:
        flash("Selecione pelo menos um relatorio para criar a operacao.", "error")
        return redirect(url_for("acompanhamento", modal_tipo="criar"))
    try:
        operacao_id = operacoes_repo.criar_operacao(nome_operacao, relatorios_ids, _usuario_id())
        auditoria.log_config(
            "operacao_criacao",
            f"Operacao {nome_operacao} criada com {len(relatorios_ids)} relatorio(s).",
            {"operacao_id": operacao_id, "relatorios": relatorios_ids},
        )
        flash("Operacao criada com sucesso e ja esta disponivel para execucao.", "success")
    except Exception as exc:
        flash(f"Nao foi possivel criar a operacao: {exc}", "error")
        return redirect(url_for("acompanhamento", modal_tipo="criar"))
    return redirect(url_for("acompanhamento"))


@rotas.post("/acompanhamento/operacoes/<int:operacao_id>/editar")
@login_required
@access_required(1, 2)
def editar_operacao_route(operacao_id: int):
    nome_operacao = normalize_text(request.form.get("nome_operacao"))
    if not nome_operacao:
        flash("Informe um nome valido para a operacao.", "error")
        return redirect(url_for("acompanhamento"))
    try:
        operacoes_repo.renomear_operacao(operacao_id, nome_operacao)
        auditoria.log_config("operacao_edicao", f"Operacao {operacao_id} atualizada.", {"nome_operacao": nome_operacao})
        flash("Operacao atualizada com sucesso.", "success")
    except Exception as exc:
        flash(f"Nao foi possivel atualizar a operacao: {exc}", "error")
    return redirect(url_for("acompanhamento"))


@rotas.post("/acompanhamento/operacoes/<int:operacao_id>/inativar")
@login_required
@access_required(1, 2)
def inativar_operacao_route(operacao_id: int):
    try:
        operacoes_repo.inativar_operacao(operacao_id)
        auditoria.log_config("operacao_inativacao", f"Operacao {operacao_id} inativada.")
        flash("Operacao inativada com sucesso.", "success")
    except Exception as exc:
        flash(f"Nao foi possivel inativar a operacao: {exc}", "error")
    return redirect(url_for("acompanhamento"))


@rotas.get("/acompanhamento/operacoes/<int:operacao_id>/relatorios/dados")
@login_required
@access_required(1, 2)
def relatorios_operacao_dados(operacao_id: int):
    try:
        return jsonify(
            {
                "relatorios_disponiveis": relatorios_repo.load_relatorios_disponiveis(),
                "relatorios_operacao": vinculos_repo.load_relatorios_operacao(operacao_id),
            }
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@rotas.post("/acompanhamento/operacoes/<int:operacao_id>/relatorios")
@login_required
@access_required(1, 2)
def adicionar_relatorio_operacao(operacao_id: int):
    relatorio_id = int(request.form.get("id_relatorio") or 0)
    if not relatorio_id:
        flash("Selecione um relatorio.", "error")
        return _redirecionar_modal_relatorios(operacao_id)
    try:
        vinculos_repo.vincular_relatorio(operacao_id, relatorio_id, _usuario_id())
        auditoria.log_config("operacao_relatorio_vinculo", f"Relatorio {relatorio_id} vinculado a operacao {operacao_id}.")
        flash("Relatorio vinculado com sucesso.", "success")
    except Exception as exc:
        flash(f"Nao foi possivel vincular o relatorio: {exc}", "error")

    return _redirecionar_modal_relatorios(operacao_id)


@rotas.post("/acompanhamento/operacoes/<int:operacao_id>/filtros")
@login_required
@access_required(1, 2)
def atualizar_filtros_operacao(operacao_id: int):
    relatorio_id = int(request.form.get("id_relatorio") or 0)
    ids_filtro = request.form.getlist("id_filtro")
    valores = request.form.getlist("valor")
    try:
        vinculos_repo.atualizar_valores_filtros(operacao_id, relatorio_id, ids_filtro, valores, _usuario_id())
        auditoria.log_config("operacao_filtros_atualizacao", f"Filtros atualizados para operacao {operacao_id}.")
        flash("Filtros atualizados com sucesso.", "success")
    except Exception as exc:
        flash(f"Nao foi possivel atualizar os filtros: {exc}", "error")

    return _redirecionar_modal_relatorios(operacao_id)


@rotas.post("/acompanhamento/operacoes/<int:operacao_id>/relatorios/remover")
@login_required
@access_required(1, 2)
def remover_relatorio_operacao(operacao_id: int):
    relatorio_id = int(request.form.get("id_relatorio") or 0)
    if not relatorio_id:
        flash("Relatorio invalido para exclusao do vinculo.", "error")
        return _redirecionar_modal_relatorios(operacao_id)

    try:
        removido = vinculos_repo.desvincular_relatorio(operacao_id, relatorio_id, _usuario_id())
        if removido:
            auditoria.log_config("operacao_relatorio_desvinculo", f"Relatorio {relatorio_id} desvinculado da operacao {operacao_id}.")
            flash("Relatorio desvinculado com sucesso.", "success")
        else:
            flash("Este relatorio nao esta mais vinculado a operacao.", "error")
    except vinculos_repo.OperacaoSemRelatorioError as exc:
        flash(str(exc), "error")
    except Exception as exc:
        flash(f"Nao foi possivel desvincular o relatorio: {exc}", "error")

    return _redirecionar_modal_relatorios(operacao_id)
