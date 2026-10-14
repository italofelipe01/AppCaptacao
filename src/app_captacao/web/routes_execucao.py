"""Rotas de execucao: tela principal, disparo de relatorio/operacao e acompanhamento do job."""

from __future__ import annotations

import threading
import traceback
from copy import deepcopy

from flask import flash, g, jsonify, redirect, render_template, request, url_for

from app_captacao.catalogo import operacao_relatorios as vinculos_repo
from app_captacao.catalogo import operacoes as operacoes_repo
from app_captacao.catalogo import regras
from app_captacao.catalogo import relatorios as relatorios_repo
from app_captacao.core.database import sql
from app_captacao.core.persistence import logs as logs_repo
from app_captacao.core.security.auth import login_required
from app_captacao.core.shared.texto import normalize_text
from app_captacao.execucao import jobs, runner
from app_captacao.web.registro import RegistroRotas

rotas = RegistroRotas()


@rotas.get("/main")
@login_required
def main():
    operacoes = sql.safe_db_call(lambda: operacoes_repo.load_operacoes(""), [])
    relatorios = sql.safe_db_call(relatorios_repo.load_relatorios_disponiveis, [])
    credenciais_execucao = jobs.get_execution_preferences_for_current_session()
    operacao_relatorios = sql.safe_db_call(operacoes_repo.load_operation_report_summaries, {})
    execution_job = jobs.get_current_execution_job()
    resultado_execucao = (
        execution_job.get("resultado")
        if execution_job and execution_job.get("estado") == "concluida"
        else jobs.get_last_execution_result_for_current_session()
    )
    return render_template(
        "main.html",
        operacoes_disponiveis=operacoes,
        relatorios_disponiveis=relatorios,
        credenciais_execucao=credenciais_execucao,
        resultado_execucao=resultado_execucao,
        execution_job=execution_job,
        operacao_relatorios=operacao_relatorios,
    )


@rotas.get("/execucoes/atual")
@login_required
def execucao_atual():
    job = jobs.get_current_execution_job()
    if not job:
        return jsonify({"estado": "inexistente", "itens": []})
    return jsonify(job)


@rotas.post("/processar")
@login_required
def processar():
    email = normalize_text(request.form.get("email"))
    senha = str(request.form.get("senha") or "")
    sharepoint_link = normalize_text(request.form.get("sharepoint_link"))
    modo = normalize_text(request.form.get("modo"))

    if not email or not senha:
        flash("Informe email e senha para a execucao.", "error")
        return redirect(url_for("main"))

    jobs.set_execution_preferences_for_current_session(email, sharepoint_link)
    jobs.clear_execution_result_for_current_session()

    current_job = jobs.get_current_execution_job()
    if current_job and current_job.get("estado") in {"pendente", "em_execucao"}:
        flash("Ja existe uma execucao em andamento para esta sessao.", "error")
        return redirect(url_for("main"))

    try:
        if modo == "completo":
            relatorio_id = int(request.form.get("relatorio") or 0)
            payload = relatorios_repo.montar_payload_execucao(relatorio_id, request.form)
            if not payload:
                flash("Relatorio nao encontrado.", "error")
                return redirect(url_for("main"))

            missing = regras.filtros_obrigatorios_sem_valor(payload)
            if missing:
                flash(f"Preencha os filtros obrigatorios: {', '.join(missing)}.", "error")
                return redirect(url_for("main"))

            payload["sharepoint_link"] = sharepoint_link
            job_id = jobs.create_execution_job("relatorio", [payload])
            threading.Thread(
                target=runner.run_execution_job,
                args=(job_id, "relatorio", email, senha, [payload], deepcopy(g.current_user)),
                daemon=True,
                name=f"appcaptacao-{job_id[:8]}",
            ).start()
            flash("Execucao iniciada. Acompanhe o status de cada etapa abaixo.", "success")
            return redirect(url_for("main"))

        if modo == "parceiros":
            operacao_id = int(request.form.get("operacao") or 0)
            operacao = operacoes_repo.buscar_operacao_ativa(operacao_id)
            if not operacao:
                flash("Selecione uma operacao ativa.", "error")
                return redirect(url_for("main"))
            relatorios = sql.safe_db_call(lambda: vinculos_repo.load_relatorio_operacao_payload(operacao_id), [])
            if not relatorios:
                flash("Nenhum relatorio ativo vinculado a esta operacao.", "error")
                return redirect(url_for("main"))

            for relatorio in relatorios:
                relatorio["sharepoint_link"] = sharepoint_link
                relatorio["operacao_nome"] = operacao.get("nome", "") if operacao else ""
                missing = regras.filtros_obrigatorios_sem_valor(relatorio)
                if missing:
                    flash(
                        f"Operacao '{operacao.get('nome', '')}' (ID {operacao_id}): "
                        f"relatorio '{relatorio.get('nome', '')}' possui filtros obrigatorios sem valor: "
                        f"{', '.join(missing)}. Salve os filtros desta operacao em Acompanhamento.",
                        "error",
                    )
                    return redirect(url_for("main"))

            operacao_nome = operacao.get("nome", "") if operacao else ""
            job_id = jobs.create_execution_job("operacao", relatorios, operacao_nome)
            threading.Thread(
                target=runner.run_execution_job,
                args=(job_id, "operacao", email, senha, relatorios, deepcopy(g.current_user), operacao_nome),
                daemon=True,
                name=f"appcaptacao-{job_id[:8]}",
            ).start()
            flash("Operacao iniciada. Os relatorios serao atualizados individualmente.", "success")
            return redirect(url_for("main"))

        flash("Selecione um modo de execucao valido.", "error")
    except Exception as exc:
        logs_repo.registrar_log_operacao(
            g.current_user["login"],
            "erro",
            {
                "tipo_execucao": modo or "desconhecido",
                "nome_operacao": request.form.get("operacao", ""),
                "nome_relatorio": request.form.get("relatorio", ""),
                "observacao": "Falha durante a execucao.",
            },
            None,
            {
                "mensagem": str(exc),
                "traceback": traceback.format_exc(),
            },
        )
        flash(f"Falha ao executar a automacao: {exc}", "error")

    return redirect(url_for("main"))


@rotas.get("/relatorios/<int:relatorio_id>/filtros-dados")
@login_required
def relatorio_filtros_dados(relatorio_id: int):
    try:
        relatorio = relatorios_repo.buscar_relatorio_com_filtros(relatorio_id)
        if not relatorio:
            return jsonify({"error": "Relatorio nao encontrado."}), 404
        relatorio = relatorios_repo.aplicar_filtros_fixos_relatorio(relatorio)

        filtros = []
        for filtro in relatorio.get("filtros", []):
            clone = dict(filtro)
            clone["opcional"] = regras.eh_filtro_opcional_relatorio(relatorio, filtro)
            if clone.get("automatico"):
                clone["opcional"] = True
            filtros.append(clone)

        return jsonify(
            {
                "relatorio": {
                    "id": relatorio["id"],
                    "nome": relatorio["nome"],
                    "url": relatorio.get("url", ""),
                },
                "filtros": filtros,
            }
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
