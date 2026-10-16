"""Execucao de um job em thread: chama a automacao e atualiza o estado do job.

Roda fora da requisicao HTTP; por isso recebe o usuario como snapshot e nao
depende do contexto do Flask.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app_captacao import automacao, consolidacao
from app_captacao.catalogo import regras
from app_captacao.core.config import settings
from app_captacao.core.persistence import logs as logs_repo
from app_captacao.execucao import jobs

logger = logging.getLogger(__name__)

MENSAGEM_FALHA_INESPERADA = "Falha inesperada na automacao; os detalhes foram registrados no log tecnico."
MENSAGEM_NAO_EXECUTADO = "Nao executado: a automacao parou antes deste relatorio."
MOTIVO_ERRO_NA_CONSOLIDACAO = "erro inesperado; os detalhes foram registrados no log tecnico"


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
        "observacao": "Execução em segundo plano concluída.",
    }
    try:
        jobs.update_execution_job(job_id, estado="em_execucao", resumo="Execucao em andamento.")
        resultado = _executar(job_id, tipo, email, senha, relatorios)
    except Exception:
        logger.exception("Falha inesperada no trabalho de execucao %s.", job_id)
        resultado = _resultado_apos_falha(job_id, relatorios, operacao_nome)
        payload_entrada["observacao"] = "Execucao interrompida por falha inesperada."

    try:
        _consolidar_relatorios(job_id, resultado, relatorios)
    except Exception:
        logger.exception("Falha inesperada na consolidacao; o resultado da execucao foi mantido.")

    jobs.finish_execution_job(job_id, resultado)
    logs_repo.registrar_log_operacao(
        responsavel,
        "sucesso" if not resultado.get("falhas") else "erro",
        payload_entrada,
        resultado,
        {"falhas": resultado.get("falhas", [])} if resultado.get("falhas") else None,
    )


def _executar(job_id: str, tipo: str, email: str, senha: str, relatorios: list[dict]) -> dict:
    def on_report_event(evento, relatorio, detalhe):
        relatorio_id = relatorio.get("id") or relatorio.get("id_relatorio")
        if evento == "processando":
            jobs.update_execution_job_item(
                job_id,
                relatorio_id,
                estado="em_execucao",
                mensagem="Executando filtros e aguardando o download.",
            )
        elif evento == "progresso":
            # Arquivo de uma empresa ja salvo: a tela mostra onde, enquanto o resto roda.
            jobs.update_execution_job_item(job_id, relatorio_id, mensagem=detalhe.get("mensagem", ""))
        elif evento == "sucesso":
            jobs.update_execution_job_item(
                job_id,
                relatorio_id,
                estado="baixado",
                mensagem=detalhe.get("mensagem") or "Arquivo confirmado no destino.",
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

    if tipo == "relatorio":
        on_report_event("processando", relatorios[0], {})
        return automacao.executar_relatorio(email, senha, relatorios[0], on_report_event=on_report_event)
    return automacao.executar_relatorios_em_sequencia(email, senha, relatorios, on_report_event=on_report_event)


def _consolidar_relatorios(job_id: str, resultado: dict, relatorios: list[dict]) -> None:
    """Consolidado de cada relatorio baixado com layout conhecido.

    Nunca muda o estado do relatorio: o consolidado (ou o motivo de nao ter saido) entra na
    mensagem, e o arquivo gerado vira o arquivo final mostrado na tela. Relatorio que falhou
    no meio nao e consolidado, para nao parecer completo.
    """
    if not settings.CONSOLIDAR_RELATORIOS:
        return
    por_id = {str(relatorio.get("id") or relatorio.get("id_relatorio")): relatorio for relatorio in relatorios}
    pendentes = []
    for item in resultado.get("itens") or []:
        if item.get("estado") != "baixado" or not item.get("arquivos"):
            continue
        relatorio = por_id.get(str(item.get("relatorio_id")), {"nome": item.get("relatorio_nome", "")})
        executor = regras.executor_do_relatorio(relatorio)
        if consolidacao.suporta(executor):
            pendentes.append((item, executor))

    gerados = nao_gerados = 0
    for indice, (item, executor) in enumerate(pendentes, start=1):
        nome = item.get("relatorio_nome", "")
        jobs.update_execution_job(job_id, resumo=f"Consolidando {nome} ({indice}/{len(pendentes)}).")
        try:
            consolidado = consolidacao.consolidar(executor, nome, item["arquivos"])
        except Exception:
            logger.exception("Falha inesperada ao consolidar o relatorio %s.", nome)
            consolidado = consolidacao.ResultadoConsolidacao(False, motivo=MOTIVO_ERRO_NA_CONSOLIDACAO)

        mensagem = str(item.get("mensagem") or "")
        if consolidado.gerado:
            gerados += 1
            item["arquivos"] = [*item["arquivos"], consolidado.caminho]
            item["caminho_final"] = consolidado.caminho
            conferencia = (
                "conferido com os totais do Sienge" if consolidado.conferido else "sem total do Sienge para conferir"
            )
            item["mensagem"] = (
                f"{mensagem} Consolidado: {Path(consolidado.caminho).name}, "
                f"{consolidado.linhas} linha(s), {conferencia}."
            ).strip()
        else:
            nao_gerados += 1
            item["mensagem"] = f"{mensagem} Consolidado não gerado: {consolidado.motivo}.".strip()

    if pendentes:
        resumo = f"{gerados} consolidado(s)" + (f", {nao_gerados} não gerado(s)" if nao_gerados else "")
        resultado["resumo"] = f"{resultado.get('resumo', '')} {resumo}.".strip()


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
        "resumo": f"{len(sucessos)} relatório(s) baixado(s); {len(falhas)} não baixado(s).",
    }
