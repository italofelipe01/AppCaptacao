"""Logs persistidos: configuracao (acoes administrativas) e operacao (execucoes).

A gravacao esta pausada por padrao; APP_SAVE_LOGS=true reativa.
"""

from __future__ import annotations

import json
import logging

from app_captacao.core.config.settings import LOG_CONFIG_TABLE, LOG_OPERACAO_TABLE, SAVE_LOGS
from app_captacao.core.database import sql
from app_captacao.core.shared.texto import format_datetime, normalize_text

logger = logging.getLogger(__name__)


def registrar_log_configuracao(
    usuario_login: str,
    evento: str,
    detalhe: str,
    payload: dict | None = None,
) -> None:
    if not SAVE_LOGS:
        return
    if not usuario_login:
        return
    try:
        sql.execute(
            f"""
            INSERT INTO {LOG_CONFIG_TABLE} (Usuario, TipoEvento, DataEvento, Detalhe, PayloadJson)
            VALUES (?, ?, GETDATE(), ?, ?)
            """,
            (
                usuario_login,
                evento,
                detalhe,
                json.dumps(payload or {}, ensure_ascii=True),
            ),
            commit=True,
        )
    except Exception:
        logger.warning("Nao foi possivel registrar log de configuracao.", exc_info=True)


def registrar_log_operacao(
    responsavel: str,
    status: str,
    payload_entrada: dict,
    payload_resultado: dict | None = None,
    erro: dict | None = None,
) -> None:
    if not SAVE_LOGS:
        return
    try:
        sql.execute(
            f"""
            INSERT INTO {LOG_OPERACAO_TABLE}
                (NomeOperacao, TipoExecucao, NomeRelatorio, Status, Responsavel, Atualizacao, Observacao,
                 PayloadEntradaJson, PayloadResultadoJson, ErroJson)
            VALUES (?, ?, ?, ?, ?, GETDATE(), ?, ?, ?, ?)
            """,
            (
                payload_entrada.get("nome_operacao", ""),
                payload_entrada.get("tipo_execucao", ""),
                payload_entrada.get("nome_relatorio", ""),
                status,
                responsavel or "",
                payload_entrada.get("observacao", ""),
                json.dumps(payload_entrada, ensure_ascii=True),
                json.dumps(payload_resultado or {}, ensure_ascii=True) if payload_resultado is not None else None,
                json.dumps(erro or {}, ensure_ascii=True) if erro is not None else None,
            ),
            commit=True,
        )
    except Exception:
        logger.warning("Nao foi possivel registrar log de operacao.", exc_info=True)


def load_logs_configuracao(filtros: dict) -> list[dict]:
    if not SAVE_LOGS:
        return []
    conditions = []
    params: list[object] = []
    if filtros["usuario"]:
        conditions.append("Usuario LIKE ?")
        params.append(f"%{filtros['usuario']}%")
    if filtros["tipo_evento"]:
        conditions.append("TipoEvento = ?")
        params.append(filtros["tipo_evento"])
    if filtros["data_inicio"]:
        conditions.append("CAST(DataEvento AS date) >= ?")
        params.append(filtros["data_inicio"])
    if filtros["data_fim"]:
        conditions.append("CAST(DataEvento AS date) <= ?")
        params.append(filtros["data_fim"])

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = sql.fetch_all(
        f"""
        SELECT Usuario, TipoEvento, DataEvento, Detalhe, PayloadJson
        FROM {LOG_CONFIG_TABLE}
        {where_sql}
        ORDER BY DataEvento DESC
        """,
        tuple(params),
    )
    return [
        {
            "usuario": normalize_text(row.get("Usuario")),
            "evento": normalize_text(row.get("TipoEvento")),
            "data_evento": format_datetime(row.get("DataEvento")),
            "detalhe": normalize_text(row.get("Detalhe")),
            "payload_json": normalize_text(row.get("PayloadJson")),
        }
        for row in rows
    ]


def load_logs_operacao(filtros: dict) -> list[dict]:
    if not SAVE_LOGS:
        return []
    conditions = []
    params: list[object] = []
    if filtros["nome_operacao"]:
        conditions.append("NomeOperacao LIKE ?")
        params.append(f"%{filtros['nome_operacao']}%")
    if filtros["status"]:
        conditions.append("Status = ?")
        params.append(filtros["status"])
    if filtros["responsavel"]:
        conditions.append("Responsavel LIKE ?")
        params.append(f"%{filtros['responsavel']}%")
    if filtros["data_inicio"]:
        conditions.append("CAST(Atualizacao AS date) >= ?")
        params.append(filtros["data_inicio"])

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = sql.fetch_all(
        f"""
        SELECT
            NomeOperacao,
            TipoExecucao,
            NomeRelatorio,
            Status,
            Responsavel,
            Atualizacao,
            Observacao,
            PayloadEntradaJson,
            PayloadResultadoJson,
            ErroJson
        FROM {LOG_OPERACAO_TABLE}
        {where_sql}
        ORDER BY Atualizacao DESC
        """,
        tuple(params),
    )

    registros = []
    for row in rows:
        entrada_json = normalize_text(row.get("PayloadEntradaJson"))
        entrada = {}
        if entrada_json:
            try:
                entrada = json.loads(entrada_json)
            except json.JSONDecodeError:
                entrada = {}
        registros.append(
            {
                "nome_operacao": normalize_text(row.get("NomeOperacao")),
                "tipo_execucao": normalize_text(row.get("TipoExecucao")),
                "nome_relatorio": normalize_text(row.get("NomeRelatorio")),
                "status": normalize_text(row.get("Status")),
                "responsavel": normalize_text(row.get("Responsavel")),
                "atualizacao": format_datetime(row.get("Atualizacao")),
                "observacao": normalize_text(row.get("Observacao")),
                "empresa": entrada.get("empresa") if isinstance(entrada.get("empresa"), list) else None,
                "empreendimento": entrada.get("empreendimento") if isinstance(entrada.get("empreendimento"), list) else None,
                "filtros_resumo": entrada.get("filtros"),
                "payload_entrada_json": entrada_json,
                "payload_resultado_json": normalize_text(row.get("PayloadResultadoJson")),
                "erro_json": normalize_text(row.get("ErroJson")),
            }
        )
    return registros
