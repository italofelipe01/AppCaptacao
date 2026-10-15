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

MENSAGEM_FALHA_INESPERADA = "Falha inesperada na automacao; os detalhes foram registrados no log tecnico."
MENSAGEM_NAO_EXECUTADO = "Nao executado: a automacao parou antes deste relatorio."


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
    payload_entrada = {
        "tipo_execucao": tipo,
        "nome_operacao": operacao_nome,
        "nome_relatorio": relatorios[0].get("nome", "") if tipo == "relatorio" and relatorios else "",
        "observacao": "Execucao em segundo plano concluida.",
    }
    try:
        jobs.update_execution_job(job_id, estado="em_execucao", resumo="Execucao em andamento.")
        resultado = _executar(job_id, tipo, email, senha, relatorios)
    except Exception:
        logger.exception("Falha inesperada no trabalho de execucao %s.", job_id)
        resultado = _resultado_apos_falha(job_id, relatorios, operacao_nome)
        payload_entrada["observacao"] = "Execucao interrompida por falha inesperada."

    jobs.finish_execution_job(job_id, resultado)
    logs_repo.registrar_log_operacao(
        responsavel,
        "sucesso" if not resultado.get("falhas") else "erro",
        payload_entrada,
        resultado,
        {"falhas": resultado.get("falhas", [])} if resultado.get("falhas") else None,
    )


def _executar(job_id: str, tipo: str, email: str, senha: str, relatorios: list[dict]) -> dict:
    if tipo == "relatorio":
        relatorio = relatorios[0]
        jobs.update_execution_job_item(
            job_id,
            relatorio.get("id"),
            estado="em_execucao",
            mensagem="Executando filtros e aguardando o download.",
        )
        return automacao.executar_relatorio(email, senha, relatorio)

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

    return automacao.executar_relatorios_em_sequencia(email, senha, relatorios, on_report_event=on_report_event)


def _resultado_apos_falha(job_id: str, relatorios: list[dict], operacao_nome: str) -> dict:
    """Resultado de uma execucao que parou no meio: o que ja terminou fica como esta.

    Relatorio em andamento vira nao_baixado; os que nem comecaram viram ignorado.
    """
    job = jobs.get_execution_job(job_id)
    itens = (job or {}).get("itens") or [
        {
            "relatorio_id": relatorio.get("id") or relatorio.get("id_relatorio"),
            "relatorio_nome": relatorio.get("nome", ""),
            "operacao_nome": operacao_nome,
            "estado": "pendente",
            "mensagem": "",
            "etapa": "",
            "caminho_final": "",
            "arquivos": [],
        }
        for relatorio in relatorios
    ]
    for item in itens:
        if item.get("estado") == "em_execucao":
            item.update(estado="nao_baixado", etapa="execucao", mensagem=MENSAGEM_FALHA_INESPERADA)
        elif item.get("estado") == "pendente":
            item.update(estado="ignorado", etapa="execucao", mensagem=MENSAGEM_NAO_EXECUTADO)

    sucessos = [item for item in itens if item.get("estado") == "baixado"]
    falhas = [item for item in itens if item.get("estado") != "baixado"]
    return {
        "itens": itens,
        "sucessos": sucessos,
        "falhas": falhas,
        "quantidade_relatorios": len(itens),
        "quantidade_baixados": len(sucessos),
        "quantidade_nao_baixados": len(falhas),
        "resumo": f"{len(sucessos)} relatorio(s) baixado(s); {len(falhas)} nao baixado(s).",
    }
