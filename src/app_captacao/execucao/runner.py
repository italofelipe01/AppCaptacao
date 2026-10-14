"""Execucao de um job em thread: chama a automacao e atualiza o estado do job.

Roda fora da requisicao HTTP; por isso recebe o usuario como snapshot e nao
depende do contexto do Flask.
"""

from __future__ import annotations

import logging

from app_captacao import automacao
from app_captacao.core.persistence import logs as logs_repo
from app_captacao.execucao import jobs

logger = logging.getLogger(__name__)


def run_execution_job(
    job_id: str,
    tipo: str,
    email: str,
    senha: str,
    relatorios: list[dict],
    user_snapshot: dict,
    operacao_nome: str = "",
) -> None:
    responsavel = str((user_snapshot or {}).get("login") or "")
    jobs.update_execution_job(job_id, estado="em_execucao", resumo="Execucao em andamento.")
    try:
        if tipo == "relatorio":
            relatorio = relatorios[0]
            jobs.update_execution_job_item(
                job_id,
                relatorio.get("id"),
                estado="em_execucao",
                mensagem="Executando filtros e aguardando o download.",
            )
            resultado = automacao.executar_relatorio(email, senha, relatorio)
        else:
            def on_report_event(evento, relatorio, detalhe):
                relatorio_id = relatorio.get("id") or relatorio.get("id_relatorio")
                if evento == "processando":
                    jobs.update_execution_job_item(
                        job_id,
                        relatorio_id,
                        estado="em_execucao",
                        mensagem="Executando filtros e aguardando o download.",
                    )
                elif evento == "sucesso":
                    jobs.update_execution_job_item(
                        job_id,
                        relatorio_id,
                        estado="baixado",
                        mensagem="Arquivo confirmado no destino.",
                        caminho_final=detalhe.get("caminho_final", ""),
                        arquivos=detalhe.get("arquivos", []),
                    )
                elif evento == "erro":
                    jobs.update_execution_job_item(
                        job_id,
                        relatorio_id,
                        estado=detalhe.get("estado", "nao_baixado"),
                        mensagem=detalhe.get("mensagem", "Falha na execucao."),
                        etapa=detalhe.get("etapa", "execucao"),
                    )

            resultado = automacao.executar_relatorios_em_sequencia(
                email,
                senha,
                relatorios,
                on_report_event=on_report_event,
            )

        jobs.finish_execution_job(job_id, resultado)
        logs_repo.registrar_log_operacao(
            responsavel,
            "sucesso" if not resultado.get("falhas") else "erro",
            {
                "tipo_execucao": tipo,
                "nome_operacao": operacao_nome,
                "nome_relatorio": relatorios[0].get("nome", "") if tipo == "relatorio" else "",
                "observacao": "Execucao em segundo plano concluida.",
            },
            resultado,
            {"falhas": resultado.get("falhas", [])} if resultado.get("falhas") else None,
        )
    except Exception as exc:
        logger.exception("Falha inesperada no trabalho de execucao %s.", job_id)
        itens = []
        for relatorio in relatorios:
            itens.append(
                {
                    "relatorio_id": relatorio.get("id") or relatorio.get("id_relatorio"),
                    "relatorio_nome": relatorio.get("nome", ""),
                    "operacao_nome": operacao_nome,
                    "estado": "ignorado",
                    "mensagem": str(exc),
                    "etapa": "execucao",
                    "caminho_final": "",
                    "arquivos": [],
                }
            )
        jobs.finish_execution_job(
            job_id,
            {
                "itens": itens,
                "falhas": itens,
                "sucessos": [],
                "quantidade_relatorios": len(itens),
                "quantidade_baixados": 0,
                "quantidade_nao_baixados": len(itens),
                "resumo": f"0 relatorios baixados; {len(itens)} nao baixados.",
            },
        )
